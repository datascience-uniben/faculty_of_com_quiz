import streamlit as st
import pandas as pd
import random
import time
import os
import base64
import requests
import json
from datetime import datetime
from io import StringIO

# -------------------------------
# PAGE CONFIGURATION (MUST BE FIRST)
# -------------------------------
st.set_page_config(
    page_title="Faculty of Computing Quiz Competition",
    page_icon="uniben.png",  # 🌟 UPDATED: Browser favicon set to local uniben logo
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GITHUB REPOSITORY STORAGE PARAMETERS ---
REPO_OWNER = "datascience-uniben"       
REPO_NAME = "faculty_of_com_quiz"   
SCORES_FILE = "scores.csv"
ROUNDS_FILE = "completed_rounds.csv"
TEAMS_FILE = "team.csv"
USERS_FILE = "users.csv"  
LOGO_FILE = "uniben.png"  
BRANCH = "main"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

BASE_SUBJECTS = {
    "Nigeria Current Affairs": "affairs",
    "General Computing & ICT": "ICT",
    "Data Processing": "dataProcessing",
    "General Mathematics": "mathematics"
}

# -------------------------------
# GITHUB API REMOTE STORAGE ENGINES
# -------------------------------
def push_file_to_github(file_path, dataframe, commit_message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    csv_string = dataframe.to_csv(index=False)
    encoded_content = base64.b64encode(csv_string.encode("utf-8")).decode("utf-8")
    
    response = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    file_sha = response.json().get("sha") if response.status_code == 200 else None

    payload = {
        "message": commit_message,
        "content": encoded_content,
        "branch": BRANCH
    }
    if file_sha:
        payload["sha"] = file_sha

    put_response = requests.put(url, headers=HEADERS, data=json.dumps(payload))
    return put_response.status_code in [200, 201]

def load_allowed_teams():
    url_teams = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TEAMS_FILE}"
    try:
        res = requests.get(url_teams, headers=HEADERS, params={"ref": BRANCH})
        if res.status_code == 200:
            content = base64.b64decode(res.json()["content"]).decode("utf-8")
            df = pd.read_csv(StringIO(content))
            team_col = [col for col in df.columns if 'team' in col.lower()]
            if team_col:
                return [str(name).strip() for name in df[team_col[0]].dropna().unique()]
            return [str(name).strip() for name in df.iloc[:, 0].dropna().unique()]
    except Exception:
        pass
    return ["A", "B", "C", "D", "E", "F"]

ALL_TEAMS = load_allowed_teams()

def get_base64_image(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

@st.cache_data(ttl=10) 
def load_questions(file_name):
    try:
        df = pd.read_csv(file_name, encoding="cp1252")
        return df.to_dict(orient="records")
    except Exception:
        return [{
            "question": f"⚠️ Missing File Notice: Please upload '{file_name}' to repository.",
            "optiona": "Opt A", "optionb": "Opt B", "optionc": "Opt C", "optiond": "Opt D", "optione": "Opt E", "answer": "A"
        }]

def sync_scores_from_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{SCORES_FILE}"
    res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        df = pd.read_csv(StringIO(content))
        return dict(zip(df["Team"].astype(str), df["Total Score"]))
    return {team: 0 for team in ALL_TEAMS}

def sync_rounds_from_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{ROUNDS_FILE}"
    res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        return pd.read_csv(StringIO(content)).values.tolist()
    return []

def fetch_users_from_github_live():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{USERS_FILE}"
    res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        df = pd.read_csv(StringIO(content))
        
        df.columns = [str(col).strip().lower() for col in df.columns]
        
        if "username" in df.columns and "password" in df.columns and "team" in df.columns and "is_logged_in" in df.columns:
            df["username"] = df["username"].astype(str).str.strip()
            df["password"] = df["password"].astype(str).str.strip()
            df["team"] = df["team"].astype(str).str.strip()
            df["is_logged_in"] = pd.to_numeric(df["is_logged_in"], errors="coerce").fillna(0).astype(int)
            return df
    return pd.DataFrame(columns=["username", "password", "team", "is_logged_in"])

def update_user_login_status(username, status_code):
    all_users = fetch_users_from_github_live()
    if not all_users.empty and "username" in all_users.columns:
        mask = all_users["username"].str.lower() == username.lower()
        if mask.any():
            all_users.loc[mask, "is_logged_in"] = int(status_code)
            push_file_to_github(USERS_FILE, all_users, f"Session Update: {username} state -> {status_code}")

# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "user_team" not in st.session_state:
    st.session_state.user_team = None  
if "scores" not in st.session_state:
    st.session_state.scores = sync_scores_from_github()
if "completed_rounds" not in st.session_state:
    st.session_state.completed_rounds = sync_rounds_from_github()
if "used_questions" not in st.session_state:
    st.session_state.used_questions = []
if "round_score" not in st.session_state:
    st.session_state.round_score = 0
if "timer_active" not in st.session_state:
    st.session_state.timer_active = False
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "current_question" not in st.session_state:
    st.session_state.current_question = None
if "round_team" not in st.session_state:
    st.session_state.round_team = None
if "round_subject" not in st.session_state:
    st.session_state.round_subject = None
if "active_round_num" not in st.session_state:
    st.session_state.active_round_num = 1
if "question_pool" not in st.session_state:
    st.session_state.question_pool = []

# -------------------------------
# PHASE 1: LOGIN AUTHENTICATION ROUTINE
# -------------------------------
if not st.session_state.authenticated:
    col_a, col_b, col_c = st.columns([1, 1.5, 1])
    with col_b:
        st.write("")
        st.write("")
        
        # Branded Portal Login Title Header Row
        col_l_log, col_l_txt = st.columns([1, 4.5])
        with col_l_log:
            if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=60)
        with col_l_txt:
            st.markdown("<h2 style='margin-top: 5px;'>Faculty Quiz Portal</h2>", unsafe_allow_html=True)
            
        with st.form("login_form", clear_on_submit=False):
            input_username = st.text_input("Username").strip()
            input_password = st.text_input("Password", type="password").strip()
            submit_login = st.form_submit_button("Log In", use_container_width=True, type="primary")
            
            if submit_login:
                if not input_username or not input_password:
                    st.error("Please enter both username and password fields.")
                else:
                    with st.spinner("Verifying device concurrency restrictions..."):
                        users_df = fetch_users_from_github_live()
                        
                        if not users_df.empty:
                            matched_user = users_df[
                                (users_df["username"].str.lower() == input_username.lower()) & 
                                (users_df["password"] == input_password)
                            ]
                            
                            if not matched_user.empty:
                                current_login_state = matched_user.iloc[0]["is_logged_in"]
                                assigned_team = matched_user.iloc[0]["team"]
                                actual_username = matched_user.iloc[0]["username"]
                                
                                if current_login_state == 1 and str(assigned_team).lower() not in ["all", "admin", "superadmin"]:
                                    st.error(f"🚫 Login Blocked: Someone from '{assigned_team}' is already logged into the hardware system elsewhere.")
                                else:
                                    st.session_state.authenticated = True
                                    st.session_state.current_user = actual_username
                                    st.session_state.user_team = assigned_team
                                    
                                    if str(assigned_team).lower() not in ["all", "admin", "superadmin"]:
                                        update_user_login_status(actual_username, 1)
                                        
                                    st.success(f"Access Granted! Welcome, {actual_username}.")
                                    time.sleep(0.5)
                                    st.rerun()
                            else:
                                st.error("❌ Invalid Username or Password. Please try again.")
                        else:
                            st.error("⚠️ Error: Unable to fetch the user credential records file from GitHub repository.")
    st.stop()  

# -------------------------------
# PHASE 2: EXECUTABLE QUIZ APPLICATION ENGINE
# -------------------------------
# 🌟 UPDATED: Responsive Branded Main Header Grid Layout Row
col_logo, col_title = st.columns([1, 14])
with col_logo:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=70)
    else:
        st.write("🏆")
with col_title:
    st.markdown("<h1 style='margin-top: -5px;'>Faculty of Computing Quiz Competition</h1>", unsafe_allow_html=True)

def set_question_pool(subject_key, round_number):
    target_csv = f"{BASE_SUBJECTS[subject_key]}{round_number}.csv"
    raw_questions = load_questions(target_csv)
    cleaned_pool = []
    
    if not raw_questions:
        st.session_state.question_pool = []
        return

    sample_q = raw_questions[0]
    headers = [str(k).strip() for k in sample_q.keys()]
    headers_lower = [h.lower() for h in headers]

    def get_csv_value(row, possible_names):
        for p in possible_names:
            if p.lower() in headers_lower:
                return row.get(headers[headers_lower.index(p.lower())], "N/A")
        return "N/A"

    for q in raw_questions:
        standardized_q = {
            'question': get_csv_value(q, ['question', 'q', 'text']),
            'optiona': get_csv_value(q, ['optiona', 'option a', 'a']),
            'optionb': get_csv_value(q, ['optionb', 'option b', 'b']),
            'optionc': get_csv_value(q, ['optionc', 'option c', 'c']),
            'optiond': get_csv_value(q, ['optiond', 'option d', 'd']),
            'optione': get_csv_value(q, ['optione', 'option e', 'e']),
            'answer': str(get_csv_value(q, ['answer', 'correct', 'ans'])).strip()
        }
        cleaned_pool.append(standardized_q)
        
    random.shuffle(cleaned_pool)
    st.session_state.question_pool = cleaned_pool
    st.session_state.used_questions = []

def set_next_question():
    if st.session_state.question_pool:
        q = st.session_state.question_pool.pop()
        st.session_state.used_questions.append(q['question'])
        st.session_state.current_question = q
    else:
        st.session_state.current_question = None

def start_timer(selected_team, selected_subject, round_number):
    st.session_state.start_time = time.time()
    st.session_state.timer_active = True
    st.session_state.round_score = 0
    st.session_state.round_team = selected_team
    st.session_state.round_subject = selected_subject
    st.session_state.active_round_num = round_number
    
    set_question_pool(selected_subject, round_number)
    set_next_question()

def terminate_active_round():
    if st.session_state.timer_active:
        team = st.session_state.round_team
        subject = st.session_state.round_subject
        r_num = st.session_state.active_round_num
        
        round_log_entry = [team, subject, f"Round {r_num}", int(st.session_state.round_score)]
        
        st.session_state.scores = sync_scores_from_github()
        st.session_state.completed_rounds = sync_rounds_from_github()
        
        existing_runs = [[str(row[0]), str(row[1]), str(row[2])] for row in st.session_state.completed_rounds]
        if [team, subject, f"Round {r_num}"] not in existing_runs:
            st.session_state.scores[team] = st.session_state.scores.get(team, 0) + st.session_state.round_score
            st.session_state.completed_rounds.append(round_log_entry)
            
            df_scores_push = pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"])
            df_rounds_push = pd.DataFrame(st.session_state.completed_rounds, columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
            
            push_file_to_github(SCORES_FILE, df_scores_push, f"Update total scores: {team}")
            push_file_to_github(ROUNDS_FILE, df_rounds_push, f"Log match activity entry: {team}")
            st.toast("Scores uploaded to GitHub repository! 🚀", icon="✅")

        st.session_state.timer_active = False
        st.session_state.current_question = None
        st.session_state.round_team = None
        st.session_state.round_subject = None

# --- UI CONTROLS SIDEBAR ---
st.sidebar.markdown(f"👤 Logged in Department: **{st.session_state.user_team}**")

if st.sidebar.button("🔒 Sign Out of Session", use_container_width=True):
    if str(st.session_state.user_team).lower() not in ["all", "admin", "superadmin"]:
        update_user_login_status(st.session_state.current_user, 0)
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.session_state.user_team = None
    st.rerun()

sorted_standings = sorted(st.session_state.scores.items(), key=lambda x: x[1], reverse=True)
ranked_team_list = [team for team, score in sorted_standings if team in ALL_TEAMS]

st.sidebar.header("Tournament Progression Panel")
total_teams_count = len(ALL_TEAMS)
stage_configurations = {
    f"Round 1: Preliminary (All {total_teams_count} Teams)": {"round": 1, "cutoff": total_teams_count},
    "Round 2: Quarter-Final (Best 5)": {"round": 2, "cutoff": min(5, total_teams_count)},
    "Round 3: Semi-Final (Best 4)": {"round": 3, "cutoff": min(4, total_teams_count)},
    "Round 4: Third-Place Playoff (Best 3)": {"round": 4, "cutoff": min(3, total_teams_count)},
    "Round 5: Grand Finale (Best 2)": {"round": 5, "cutoff": min(2, total_teams_count)}
}

selected_stage_label = st.sidebar.selectbox("Active Match Bracket", list(stage_configurations.keys()))
current_round_id = stage_configurations[selected_stage_label]["round"]
allowed_count = stage_configurations[selected_stage_label]["cutoff"]

eligible_teams = ranked_team_list[:allowed_count]

if str(st.session_state.user_team).lower() in ["all", "admin", "superadmin"]:
    filtered_teams = eligible_teams
else:
    filtered_teams = [team for team in eligible_teams if str(team).lower() == str(st.session_state.user_team).lower()]

if filtered_teams:
    if len(filtered_teams) == 1:
        st.sidebar.info(f"📍 Context locked to your department: **{filtered_teams[0]}**")
        chosen_team = filtered_teams[0]
    else:
        chosen_team = st.sidebar.selectbox("Select Active Team", filtered_teams)
else:
    if str(st.session_state.user_team).lower() not in ["all", "admin", "superadmin"]:
        st.sidebar.error(f"❌ Your department ({st.session_state.user_team}) did not qualify for this bracket level.")
    else:
        st.sidebar.error("No eligible tournament teams found.")
    chosen_team = None

chosen_subject = st.sidebar.selectbox("Choose Subject Area", list(BASE_SUBJECTS.keys()))

is_already_played = False
if chosen_team:
    for row in st.session_state.completed_rounds:
        if str(row[0]) == str(chosen_team) and str(row[1]) == str(chosen_subject) and str(row[2]) == f"Round {current_round_id}":
            is_already_played = True

if is_already_played:
    st.sidebar.error(f"🚫 {chosen_team} has already completed {chosen_subject} for Round {current_round_id}!")

if st.sidebar.button("🚀 Start 2-Minute Round", disabled=(st.session_state.timer_active or is_already_played or not chosen_team)):
    start_timer(chosen_team, chosen_subject, current_round_id)
    st.rerun()

# --- GAMEPLAY RUNTIME BLOCKS ---
if st.session_state.timer_active and st.session_state.round_team:
    elapsed = time.time() - st.session_state.start_time
    remaining = max(0, 120 - int(elapsed))
    
    if remaining <= 0:
        terminate_active_round()
        st.error("⏰ Time has expired!")
        if st.button("Proceed to Global Results"):
            st.rerun()
    else:
        st.markdown(f"### 🎯 Team **{st.session_state.round_team}** is playing **{st.session_state.round_subject}** (Round {st.session_state.active_round_num})!")
        st.progress(remaining / 120)
        st.info(f"⏳ Time Remaining: **{remaining}** seconds | Points Captured: **{st.session_state.round_score}**")
        
        q = st.session_state.current_question
        if q:
            st.write(f"**Question:** {q['question']}")
            options = [f"A: {q.get('optiona','N/A')}", f"B: {q.get('optionb','N/A')}", f"C: {q.get('optionc','N/A')}", f"D: {q.get('optiond','N/A')}", f"E: {q.get('optione','N/A')}"]
            choice = st.radio("Options", options, index=None, key="current_options_radio")
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Submit Answer", type="primary"):
                    if choice:
                        if choice[0].upper() == str(q['answer']).strip().upper():
                            st.session_state.round_score += 1
                            st.toast("Correct! 🎉", icon="✅")
                        else:
                            st.toast(f"Wrong! Correct was {q['answer']}", icon="❌")
                        set_next_question()
                        st.rerun()
                    else:
                        st.warning("Select an option!")
            with col2:
                if st.button("⏭️ Skip Question"):
                    set_next_question()
                    st.rerun()
        else:
            st.warning("Category question pool depleted.")
            if st.button("End Round Early"):
                terminate_active_round()
                st.rerun()
                
        time.sleep(0.1)
        st.rerun()

# --- STANDINGS SCREEN DISPLAY ---
st.write("---")
st.subheader("📊 Live Leaderboard")
scores_df = pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"])
scores_df = scores_df[scores_df["Team"].isin(ALL_TEAMS)].sort_values(by="Total Score", ascending=False).reset_index(drop=True)
st.dataframe(scores_df.set_index("Team"), use_container_width=True)

if st.sidebar.button("🔄 Sync with GitHub Data"):
    st.session_state.scores = sync_scores_from_github()
    st.session_state.completed_rounds = sync_rounds_from_github()
    st.rerun()

# --- FOOTER FORMATTING ---
st.markdown("""<style>.quiz-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #e2e8f0; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 15px 40px; font-size: 22px; font-weight: 600; border-top: 2px solid #262730; z-index: 999; } .footer-text-center { text-align: center; grid-column: 2; max-width: 1000px; } .footer-logo-right { grid-column: 3; justify-self: end; } .footer-logo-right img { height: 45px; width: auto; object-fit: contain; } .main .block-container { padding-bottom: 140px !important; max-width: 95% !important; }</style>""", unsafe_allow_html=True)
logo_base64 = get_base64_image(LOGO_FILE)
logo_container = f'<div class="footer-logo-right"><img src="data:image/png;base64,{logo_base64}" alt="Logo"></div>' if logo_base64 else '<div class="footer-logo-right"></div>'
st.markdown(f'<div class="quiz-footer"><div class="footer-left-spacer"></div><div class="footer-text-center">Faculty of Computing Inter-department Quiz Competition • {datetime.now().year} • 📊 Completed Match Rounds Tally: {len(st.session_state.completed_rounds)}</div>{logo_container}</div>', unsafe_allow_html=True)
