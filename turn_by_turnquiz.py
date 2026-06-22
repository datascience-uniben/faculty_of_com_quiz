import streamlit as st
import pandas as pd
import random
import time
import os
import base64
import requests
import json
from datetime import datetime

# -------------------------------
# PAGE CONFIGURATION (MUST BE FIRST)
# -------------------------------
st.set_page_config(
    page_title="Faculty of Computing Quiz Competition",
    page_icon="uniben.png",  
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GITHUB REPOSITORY STORAGE PARAMETERS ---
REPO_OWNER = "datascience-uniben"       
REPO_NAME = "faculty_of_com_quiz"   
SCORES_FILE = "scores.csv"
ROUNDS_FILE = "completed_rounds.csv"
TEAMS_FILE = "team.csv"
LOGO_FILE = "uniben.png"  
BRANCH = "main"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# 🌟 UPDATED: Contains both required subject categories
BASE_SUBJECTS = {
    "Nigeria Current Affairs": "affairs",
    "General Computing & ICT": "ICT"
}

# -------------------------------
# GITHUB API REMOTE STORAGE ENGINES
# -------------------------------
def push_file_to_github(file_path, dataframe, commit_message):
    """Pushes a pandas DataFrame safely into the repository using the GitHub API."""
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
    if os.path.exists(TEAMS_FILE):
        try:
            df = pd.read_csv(TEAMS_FILE)
            team_col = [col for col in df.columns if 'team' in col.lower()]
            return [str(name).strip() for name in df[team_col[0]].dropna().unique()] if team_col else [str(name).strip() for name in df.iloc[:, 0].dropna().unique()]
        except Exception:
            return ["A", "B", "C", "D", "E", "F"]
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
        from io import StringIO
        df = pd.read_csv(StringIO(content))
        return dict(zip(df["Team"].astype(str), df["Total Score"]))
    return {team: 0 for team in ALL_TEAMS}

def sync_rounds_from_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{ROUNDS_FILE}"
    res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        from io import StringIO
        return pd.read_csv(StringIO(content)).values.tolist()
    return []

# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------
if "scores" not in st.session_state:
    st.session_state.scores = sync_scores_from_github()
if "completed_rounds" not in st.session_state:
    st.session_state.completed_rounds = sync_rounds_from_github()
if "used_questions" not in st.session_state:
    st.session_state.used_questions = []
if "round_score" not in st.session_state:
    st.session_state.round_score = 0
if "round_active" not in st.session_state:
    st.session_state.round_active = False
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
if "questions_answered_this_round" not in st.session_state:
    st.session_state.questions_answered_this_round = 0
if "has_drawn_question" not in st.session_state:
    st.session_state.has_drawn_question = False
if "question_start_time" not in st.session_state:
    st.session_state.question_start_time = None

# -------------------------------
# CORE GAME ENGINE OPERATIONS
# -------------------------------
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

def draw_random_question():
    """Picks one random question, removes it entirely from the pool, and logs the 30s timer start."""
    if st.session_state.question_pool:
        q = st.session_state.question_pool.pop()
        st.session_state.used_questions.append(q['question'])
        st.session_state.current_question = q
        st.session_state.has_drawn_question = True
        st.session_state.question_start_time = time.time()  # Start the 30-second stopwatch
    else:
        st.session_state.current_question = None

def start_turn_round(selected_team, selected_subject, round_number):
    st.session_state.round_active = True
    st.session_state.round_score = 0
    st.session_state.questions_answered_this_round = 0
    st.session_state.round_team = selected_team
    st.session_state.round_subject = selected_subject
    st.session_state.active_round_num = round_number
    st.session_state.has_drawn_question = False
    st.session_state.current_question = None
    st.session_state.question_start_time = None
    
    set_question_pool(selected_subject, round_number)

def terminate_active_round():
    if st.session_state.round_active:
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

        st.session_state.round_active = False
        st.session_state.current_question = None
        st.session_state.round_team = None
        st.session_state.round_subject = None
        st.session_state.questions_answered_this_round = 0
        st.session_state.has_drawn_question = False
        st.session_state.question_start_time = None

# -------------------------------
# USER INTERFACE SETUP
# -------------------------------
col_logo, col_title = st.columns([1, 14])
with col_logo:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=70)
    else:
        st.write("🏆")
with col_title:
    st.markdown("<h1 style='margin-top: -5px;'>Faculty of Computing Quiz Competition</h1>", unsafe_allow_html=True)

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
if eligible_teams:
    st.sidebar.markdown(f"**Qualified for this stage:** `{', '.join(eligible_teams)}`")
    chosen_team = st.sidebar.selectbox("Select Active Team", eligible_teams)
else:
    st.sidebar.error("No eligible teams found.")
    chosen_team = None

chosen_subject = st.sidebar.selectbox("Choose Subject Area", list(BASE_SUBJECTS.keys()))

is_already_played = False
if chosen_team:
    for row in st.session_state.completed_rounds:
        if str(row[0]) == str(chosen_team) and str(row[1]) == str(chosen_subject) and str(row[2]) == f"Round {current_round_id}":
            is_already_played = True

if is_already_played:
    st.sidebar.error(f"🚫 {chosen_team} has already completed {chosen_subject} for Round {current_round_id}!")

if st.sidebar.button("🚀 Open Turn-Based Session", disabled=(st.session_state.round_active or is_already_played or not chosen_team)):
    start_turn_round(chosen_team, chosen_subject, current_round_id)
    st.rerun()

# --- GAMEPLAY INTERACTION PANELS ---
if st.session_state.round_active and st.session_state.round_team:
    st.markdown(f"### 🎯 Team **{st.session_state.round_team}** Turn Session — {st.session_state.round_subject} (Round {st.session_state.active_round_num})")
    
    # Visual Tracking Metrics for Turn Rounds
    c1, c2 = st.columns(2)
    c1.metric(label="Questions Attempted", value=f"{st.session_state.questions_answered_this_round} / 4")
    c2.metric(label="Points Earned This Turn", value=f"{st.session_state.round_score} pts")
    
    st.write("---")

    # Flow State Check: Team needs to pick/draw a question first
    if not st.session_state.has_drawn_question:
        st.info("💡 Ready for your turn? Click the button below to draw a random question. You will have **30 seconds** to answer it.")
        if st.button("🎲 Draw Next Question", type="primary"):
            draw_random_question()
            st.rerun()
            
    else:
        # Calculate Remaining Time for the active question
        elapsed_time = time.time() - st.session_state.question_start_time
        remaining_seconds = max(0, 30 - int(elapsed_time))
        
        # Check if the 30-second timer has run out
        if remaining_seconds <= 0:
            st.toast("⏰ Time ran out for this question!", icon="❌")
            st.session_state.questions_answered_this_round += 1
            st.session_state.has_drawn_question = False
            st.session_state.current_question = None
            
            if st.session_state.questions_answered_this_round >= 4:
                terminate_active_round()
                st.info("Turn closed out automatically.")
            st.rerun()
            
        else:
            # Render remaining time warning
            st.progress(remaining_seconds / 30)
            if remaining_seconds <= 10:
                st.error(f"⏰ **Time Remaining: {remaining_seconds} seconds! Hurry up!**")
            else:
                st.warning(f"⏳ Time Remaining: **{remaining_seconds}** seconds")

            q = st.session_state.current_question
            if q:
                st.markdown(f"#### **Question Context:**\n> {q['question']}")
                options = [f"A: {q.get('optiona','N/A')}", f"B: {q.get('optionb','N/A')}", f"C: {q.get('optionc','N/A')}", f"D: {q.get('optiond','N/A')}", f"E: {q.get('optione','N/A')}"]
                choice = st.radio("Choose Your Team's Definitive Answer:", options, index=None, key=f"q_{st.session_state.questions_answered_this_round}")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Submit Answer", type="primary"):
                        if choice:
                            # Check accuracy
                            if choice[0].upper() == str(q['answer']).strip().upper():
                                st.session_state.round_score += 1
                                st.toast("Correct! 🎉", icon="✅")
                            else:
                                st.toast(f"Wrong! Correct was {q['answer']}", icon="❌")
                            
                            # Increment progressive tracking indices
                            st.session_state.questions_answered_this_round += 1
                            st.session_state.has_drawn_question = False
                            st.session_state.current_question = None
                            
                            # If 4 questions are met, close out the team's dashboard automatically
                            if st.session_state.questions_answered_this_round >= 4:
                                terminate_active_round()
                                st.success("🎉 Target of 4 questions reached! Turn metrics recorded.")
                                time.sleep(1.5)
                            st.rerun()
                        else:
                            st.warning("Please select an option before committing!")
                with col2:
                    if st.button("⏭️ Skip / Burn Question"):
                        st.session_state.questions_answered_this_round += 1
                        st.session_state.has_drawn_question = False
                        st.session_state.current_question = None
                        
                        if st.session_state.questions_answered_this_round >= 4:
                            terminate_active_round()
                            st.info("Turn closed out following a skipped submission limit.")
                            time.sleep(1.5)
                        st.rerun()
            else:
                st.warning("Category question pool completely depleted.")
                if st.button("Force Complete Turn Session"):
                    terminate_active_round()
                    st.rerun()
                    
            # Small heartbeat pause to force Streamlit to rerun and dynamically update the countdown bar
            time.sleep(0.1)
            st.rerun()

# --- STANDINGS SCREEN DISPLAY ---
st.write("---")
st.subheader("📊 Live Leaderboard")
scores_df = pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"])
scores_df = scores_df[scores_df["Team"].isin(ALL_TEAMS)].sort_values(by="Total Score", ascending=False).reset_index(drop=True)
st.dataframe(scores_df.set_index("Team"), use_container_width=True)

if st.sidebar.button("🔄 Sync with Faculty QUIZ Data"):
    st.session_state.scores = sync_scores_from_github()
    st.session_state.completed_rounds = sync_rounds_from_github()
    st.rerun()

# --- FOOTER FORMATTING ---
st.markdown("""<style>.quiz-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #e2e8f0; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 15px 40px; font-size: 22px; font-weight: 600; border-top: 2px solid #262730; z-index: 999; } .footer-text-center { text-align: center; grid-column: 2; max-width: 1000px; } .footer-logo-right { grid-column: 3; justify-self: end; } .footer-logo-right img { height: 45px; width: auto; object-fit: contain; } .main .block-container { padding-bottom: 140px !important; max-width: 95% !important; }</style>""", unsafe_allow_html=True)
logo_base64 = get_base64_image(LOGO_FILE)
logo_container = f'<div class="footer-logo-right"><img src="data:image/png;base64,{logo_base64}" alt="Logo"></div>' if logo_base64 else '<div class="footer-logo-right"></div>'
st.markdown(f'<div class="quiz-footer"><div class="footer-left-spacer"></div><div class="footer-text-center">Faculty of Computing Inter-department Quiz Competition • {datetime.now().year} • 📊 Completed Match Rounds Tally: {len(st.session_state.completed_rounds)}</div>{logo_container}</div>', unsafe_allow_html=True)
