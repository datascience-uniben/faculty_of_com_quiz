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
TAKEN_QUESTIONS_FILE = "taken_questions.csv" 
LOGO_FILE = "uniben.png"  
BRANCH = "main"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

BASE_SUBJECTS = {
    "Nigeria Current Affairs": "affairs",
    "General Computing & ICT": "ICT"
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
    if os.path.exists(TEAMS_FILE):
        try:
            df = pd.read_csv(TEAMS_FILE)
            team_col = [col for col in df.columns if 'team' in col.lower()]
            teams = [str(name).strip() for name in df[team_col[0]].dropna().unique()] if team_col else [str(name).strip() for name in df.iloc[:, 0].dropna().unique()]
            if teams:
                return teams
        except Exception:
            pass
    return ["A", "B", "C", "D", "E", "F"]

ALL_TEAMS = load_allowed_teams()

def get_base64_image(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

@st.cache_data(ttl=5) 
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
        try:
            df = pd.read_csv(StringIO(content))
            if df.empty or "Team" not in df.columns:
                return {team: 0 for team in ALL_TEAMS}
            return dict(zip(df["Team"].astype(str), df["Total Score"]))
        except (pd.errors.EmptyDataError, KeyError):
            return {team: 0 for team in ALL_TEAMS}
    return {team: 0 for team in ALL_TEAMS}

def sync_rounds_from_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{ROUNDS_FILE}"
    res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        try:
            return pd.read_csv(StringIO(content)).values.tolist()
        except pd.errors.EmptyDataError:
            return []
    return []

def sync_taken_questions_from_github():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TAKEN_QUESTIONS_FILE}"
    res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        try:
            df = pd.read_csv(StringIO(content))
            if "question" in df.columns:
                return df["question"].dropna().astype(str).tolist()
            return []
        except (pd.errors.EmptyDataError, ValueError):
            return []
    return []

# -------------------------------
# INTERLEAVED STATE INITIALIZATION
# -------------------------------
if "scores" not in st.session_state:
    st.session_state.scores = sync_scores_from_github()
if "completed_rounds" not in st.session_state:
    st.session_state.completed_rounds = sync_rounds_from_github()
if "stage_active" not in st.session_state:
    st.session_state.stage_active = False
if "current_stage_teams" not in st.session_state:
    st.session_state.current_stage_teams = []
if "team_rotation_index" not in st.session_state:
    st.session_state.team_rotation_index = 0
if "team_question_counts" not in st.session_state:
    st.session_state.team_question_counts = {}  
if "stage_running_scores" not in st.session_state:
    st.session_state.stage_running_scores = {}
if "current_question" not in st.session_state:
    st.session_state.current_question = None
if "has_drawn_question" not in st.session_state:
    st.session_state.has_drawn_question = False
if "question_start_time" not in st.session_state:
    st.session_state.question_start_time = None
if "stage_round_num" not in st.session_state:
    st.session_state.stage_round_num = 1
if "stage_subject" not in st.session_state:
    st.session_state.stage_subject = None
if "question_pool" not in st.session_state:
    st.session_state.question_pool = []

# -------------------------------
# ROUND ROBIN OPERATIONS ENGINE
# -------------------------------
def advance_to_next_team():
    teams = st.session_state.current_stage_teams
    start_idx = st.session_state.team_rotation_index
    
    round_limits = {1: 4, 2: 5, 3: 6, 4: 7, 5: 8}
    total_needed = round_limits.get(st.session_state.stage_round_num, 4)
    
    all_done = all(st.session_state.team_question_counts.get(t, 0) >= total_needed for t in teams)
    if all_done:
        terminate_interleaved_stage()
        return

    for i in range(len(teams)):
        next_idx = (start_idx + 1 + i) % len(teams)
        target_team = teams[next_idx]
        if st.session_state.team_question_counts.get(target_team, 0) < total_needed:
            st.session_state.team_rotation_index = next_idx
            st.session_state.has_drawn_question = False
            st.session_state.current_question = None
            st.session_state.question_start_time = None
            return

def draw_interleaved_question():
    if st.session_state.question_pool:
        q = st.session_state.question_pool.pop()
        st.session_state.current_question = q
        st.session_state.has_drawn_question = True
        st.session_state.question_start_time = time.time()
        
        globally_taken = sync_taken_questions_from_github()
        if q['question'] not in globally_taken:
            globally_taken.append(q['question'])
            df_taken = pd.DataFrame(globally_taken, columns=["question"])
            
            if st.session_state.current_stage_teams and st.session_state.team_rotation_index < len(st.session_state.current_stage_teams):
                current_active_team = st.session_state.current_stage_teams[st.session_state.team_rotation_index]
            else:
                current_active_team = "Unknown"
                
            push_file_to_github(TAKEN_QUESTIONS_FILE, df_taken, f"Marked used by: {current_active_team}")
    else:
        st.session_state.current_question = None

def terminate_interleaved_stage():
    st.session_state.scores = sync_scores_from_github()
    st.session_state.completed_rounds = sync_rounds_from_github()
    
    r_num = st.session_state.stage_round_num
    subject = st.session_state.stage_subject
    bracket_label = f"Round {r_num} Tie-Breaker" if r_num == 5 else f"Round {r_num}"
    
    for team, pts in st.session_state.stage_running_scores.items():
        existing_runs = [[str(row[0]), str(row[1]), str(row[2])] for row in st.session_state.completed_rounds]
        if [team, subject, bracket_label] not in existing_runs:
            st.session_state.scores[team] = st.session_state.scores.get(team, 0) + pts
            st.session_state.completed_rounds.append([team, subject, bracket_label, int(pts)])
            
    df_scores_push = pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"])
    df_rounds_push = pd.DataFrame(st.session_state.completed_rounds, columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
    
    push_file_to_github(SCORES_FILE, df_scores_push, f"Batch Update Scores Round {r_num}")
    push_file_to_github(ROUNDS_FILE, df_rounds_push, f"Batch Log Round {r_num} Entries")
    
    st.session_state.stage_active = False
    st.session_state.current_question = None
    st.session_state.has_drawn_question = False
    st.success("🎉 Stage bracket complete! Standings pushed to GitHub database.")
    time.sleep(2.0)

def initialize_stage_pool(subject_key, round_number, qualified_teams):
    target_csv = f"{BASE_SUBJECTS[subject_key]}{round_number}.csv"
    raw_questions = load_questions(target_csv)
    globally_taken_questions = sync_taken_questions_from_github()
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
        q_text = str(get_csv_value(q, ['question', 'q', 'text'])).strip()
        if q_text in globally_taken_questions or q_text == "_initialization_placeholder_":
            continue

        standardized_q = {
            'question': q_text,
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
    
    st.session_state.stage_active = True
    st.session_state.current_stage_teams = qualified_teams
    st.session_state.team_rotation_index = 0
    st.session_state.stage_subject = subject_key
    st.session_state.stage_round_num = round_number
    st.session_state.team_question_counts = {team: 0 for team in qualified_teams}
    st.session_state.stage_running_scores = {team: 0 for team in qualified_teams}
    st.session_state.has_drawn_question = False
    st.session_state.current_question = None

# -------------------------------
# USER INTERFACE SETUP
# -------------------------------
col_logo, col_title = st.columns([1, 14])
with col_logo:
    if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=70)
    else: st.write("🏆")
with col_title:
    st.markdown("<h1 style='margin-top: -5px;'>Faculty of Computing Quiz Competition</h1>", unsafe_allow_html=True)

for team in ALL_TEAMS:
    if team not in st.session_state.scores:
        st.session_state.scores[team] = 0

sorted_standings = sorted(st.session_state.scores.items(), key=lambda x: x[1], reverse=True)
ranked_team_list = [team for team, score in sorted_standings if team in ALL_TEAMS]

st.sidebar.header("Tournament Progression Panel")
total_teams_count = len(ALL_TEAMS)
stage_configurations = {
    f"Round 1: Preliminary (All {total_teams_count} Teams)": {"round": 1, "cutoff": total_teams_count},
    "Round 2: Quarter-Final (Best 5)": {"round": 2, "cutoff": min(5, total_teams_count)},
    "Round 3: Semi-Final (Best 4)": {"round": 3, "cutoff": min(4, total_teams_count)},
    "Round 4: Third-Place Playoff (Best 3)": {"round": 4, "cutoff": min(3, total_teams_count)},
    "💥 Round 5: Grand Final": {"round": 5, "cutoff": total_teams_count}
}

selected_stage_label = st.sidebar.selectbox("Active Match Bracket", list(stage_configurations.keys()), disabled=st.session_state.stage_active)
current_round_id = stage_configurations[selected_stage_label]["round"]
allowed_count = stage_configurations[selected_stage_label]["cutoff"]

eligible_teams = ranked_team_list[:allowed_count] if current_round_id != 5 else ALL_TEAMS
chosen_subject = st.sidebar.selectbox("Choose Subject Area", list(BASE_SUBJECTS.keys()), disabled=st.session_state.stage_active)

if st.sidebar.button("🚀 Initialize Interleaved Stage Round", disabled=st.session_state.stage_active):
    initialize_stage_pool(chosen_subject, current_round_id, eligible_teams)
    st.rerun()

# --- INTERLEAVED GAMEPLAY MATRIX PANEL ---
if st.session_state.stage_active:
    if not st.session_state.current_stage_teams:
        st.error("⚠️ No eligible teams evaluated for this bracket stage. Force resetting.")
        st.session_state.stage_active = False
        st.rerun()
        
    if st.session_state.team_rotation_index >= len(st.session_state.current_stage_teams):
        st.session_state.team_rotation_index = 0

    current_team = st.session_state.current_stage_teams[st.session_state.team_rotation_index]
    
    round_limits = {1: 4, 2: 5, 3: 6, 4: 7, 5: 8}
    total_draw_limit = round_limits.get(st.session_state.stage_round_num, 4)
    
    st.markdown(f"### 🎯 Match Matrix Active: **{st.session_state.stage_subject} (Round {st.session_state.stage_round_num})**")
    
    cols_matrix = st.columns(len(st.session_state.current_stage_teams))
    for index, t_name in enumerate(st.session_state.current_stage_teams):
        with cols_matrix[index]:
            is_active_marker = "👉 " if t_name == current_team else ""
            q_count = st.session_state.team_question_counts.get(t_name, 0)
            s_score = st.session_state.stage_running_scores.get(t_name, 0)
            st.metric(
                label=f"{is_active_marker}Team {t_name}", 
                value=f"{q_count} / {total_draw_limit} Qs",
                delta=f"{s_score} Points"
            )

    st.write("---")
    st.markdown(f"#### 🎭 Current Active Slot: **Team {current_team}** (Question #{st.session_state.team_question_counts.get(current_team, 0) + 1})")

    if not st.session_state.has_drawn_question:
        if st.button(f"🎲 Draw Random Question for Team {current_team}", type="primary"):
            draw_interleaved_question()
            st.rerun()
    else:
        elapsed_time = time.time() - st.session_state.question_start_time
        remaining_seconds = max(0, 30 - int(elapsed_time))
        
        if remaining_seconds <= 0:
            st.toast("⏰ Time ran out for this question!", icon="❌")
            st.session_state.team_question_counts[current_team] = st.session_state.team_question_counts.get(current_team, 0) + 1
            advance_to_next_team()
            st.rerun()
        else:
            st.progress(remaining_seconds / 30)
            if remaining_seconds <= 10:
                st.error(f"⏰ **Time Remaining: {remaining_seconds} seconds!**")
            else:
                st.warning(f"⏳ Time Remaining: **{remaining_seconds}** seconds")

            q = st.session_state.current_question
            if q:
                st.markdown(f"#### **Question Context:**\n> {q['question']}")
                options = [f"A: {q.get('optiona','N/A')}", f"B: {q.get('optionb','N/A')}", f"C: {q.get('optionc','N/A')}", f"D: {q.get('optiond','N/A')}", f"E: {q.get('optione','N/A')}"]
                choice = st.radio("Choose Your Team's Definitive Answer:", options, index=None, key=f"interleaved_{current_team}_{st.session_state.team_question_counts.get(current_team, 0)}")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Submit Answer", type="primary"):
                        if choice:
                            if choice[0].upper() == str(q['answer']).strip().upper():
                                st.session_state.stage_running_scores[current_team] = st.session_state.stage_running_scores.get(current_team, 0) + 1
                                st.toast("Correct! 🎉", icon="✅")
                            else:
                                st.toast(f"Wrong! Correct was {q['answer']}", icon="❌")
                            
                            st.session_state.team_question_counts[current_team] = st.session_state.team_question_counts.get(current_team, 0) + 1
                            advance_to_next_team()
                            st.rerun()
                        else:
                            st.warning("Please select an option before committing!")
                with col2:
                    if st.button("⏭️ Skip / Burn Question"):
                        st.session_state.team_question_counts[current_team] = st.session_state.team_question_counts.get(current_team, 0) + 1
                        advance_to_next_team()
                        st.rerun()
            else:
                st.warning("Question pool completely depleted. Skipping turn forward.")
                st.session_state.team_question_counts[current_team] = st.session_state.team_question_counts.get(current_team, 0) + 1
                advance_to_next_team()
                st.rerun()
            
            time.sleep(0.1)
            st.rerun()
                
    if st.sidebar.button("🚨 Force Terminate Current Stage"):
        st.session_state.stage_active = False
        st.rerun()

# --- STANDINGS SCREEN DISPLAY (DYNAMICAL ACCORDING TO TEAM PRESENCE) ---
st.write("---")
st.subheader("📊 Live Leaderboard Standings")
scores_df = pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"])

# Filter dynamically: show only teams configured/running in the specific round bracket
visible_teams = st.session_state.current_stage_teams if st.session_state.stage_active else eligible_teams
scores_df = scores_df[scores_df["Team"].isin(visible_teams)].sort_values(by="Total Score", ascending=False).reset_index(drop=True)

if not scores_df.empty and len(scores_df) > 1:
    lowest_score = scores_df.iloc[-1]["Total Score"]
    elimination_candidates = scores_df[scores_df["Total Score"] == lowest_score]["Team"].tolist()
    st.error(f"⚠️ **Bottom Tier Elimination Risk:** Team(s) `{', '.join(elimination_candidates)}` are at the bottom of the standings board ({lowest_score} pts).")

st.dataframe(scores_df.set_index("Team"), use_container_width=True)

if st.sidebar.button("🔄 Sync with Faculty QUIZ Data"):
    st.session_state.scores = sync_scores_from_github()
    st.session_state.completed_rounds = sync_rounds_from_github()
    st.rerun()

# --- FOOTER FORMATTING ---
st.markdown("""<style>.quiz-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #e2e8f0; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 15px 40px; font-size: 22px; font-weight: 600; border-top: 2px solid #262730; z-index: 999; } .footer-text-center { text-align: center; grid-column: 2; max-width: 1000px; } .footer-logo-right { grid-column: 3; justify-self: end; } .footer-logo-right img { height: 45px; width: auto; object-fit: contain; } .main .block-container { padding-bottom: 140px !important; max-width: 95% !important; }</style>""", unsafe_allow_html=True)
logo_base64 = get_base64_image(LOGO_FILE)
logo_container = f'<div class="footer-logo-right"><img src="data:image/png;base64,{logo_base64}" alt="Logo"></div>' if logo_base64 else '<div class="footer-logo-right"></div>'
st.markdown(f'<div class="quiz-footer"><div class="footer-left-spacer"></div><div class="footer-text-center">Faculty of Computing Inter-department Quiz Competition • 2026 • 📊 Completed Match Rounds Tally: {len(st.session_state.completed_rounds)}</div>{logo_container}</div>', unsafe_allow_html=True)
