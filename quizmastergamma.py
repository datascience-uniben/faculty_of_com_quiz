import streamlit as st
import pandas as pd
import random
import time
import os
import base64
from datetime import datetime

# -------------------------------
# PAGE CONFIGURATION (MUST BE FIRST)
# -------------------------------
st.set_page_config(
    page_title="Faculty of Computing Quiz Competition",
    page_icon="🏆",
    layout="wide",  # Expands the window to use the full width of the screen
    initial_sidebar_state="expanded"
)

# -------------------------------
# CONFIGURATION & FILE DICTIONARIES
# -------------------------------
BASE_SUBJECTS = {
    "Nigeria Current Affairs": "affairs",
    "General Computing & ICT": "ICT",
    "Data Processing": "dataProcessing",
    "General Mathematics": "mathematics"
}

TEAMS_FILE = "team.csv"
SCORES_FILE = "scores.csv"
ROUNDS_FILE = "completed_rounds.csv"
LOGO_FILE = "logo.png"

def load_allowed_teams():
    if os.path.exists(TEAMS_FILE):
        try:
            df = pd.read_csv(TEAMS_FILE)
            team_col = [col for col in df.columns if 'team' in col.lower()]
            if team_col:
                return [str(name).strip() for name in df[team_col[0]].dropna().unique()]
            else:
                return [str(name).strip() for name in df.iloc[:, 0].dropna().unique()]
        except Exception:
            return ["A", "B", "C", "D", "E", "F"]
    return ["A", "B", "C", "D", "E", "F"]

ALL_TEAMS = load_allowed_teams()

def get_base64_image(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

# -------------------------------
# QUESTION LOADER
# -------------------------------
@st.cache_data
def load_questions(file_name):
    try:
        df = pd.read_csv(file_name, encoding="cp1252")
        return df.to_dict(orient="records")
    except UnicodeDecodeError:
        df = pd.read_csv(file_name, encoding="utf-8", errors="replace")
        return df.to_dict(orient="records")
    except FileNotFoundError:
        return [{
            "question": f"⚠️ Missing File Notice: Please create '{file_name}' to load questions.",
            "optiona": "Option A", "optionb": "Option B", "optionc": "Option C",
            "optiond": "Option D", "optione": "Option E", "answer": "A"
        }]

# -------------------------------
# PERSISTENCE METHODS
# -------------------------------
def save_scores():
    pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"]).to_csv(SCORES_FILE, index=False)

def load_scores():
    if os.path.exists(SCORES_FILE):
        df = pd.read_csv(SCORES_FILE)
        file_scores = dict(zip(df["Team"].astype(str), df["Total Score"]))
        return {team: file_scores.get(team, 0) for team in ALL_TEAMS}
    return {team: 0 for team in ALL_TEAMS}

def save_completed_rounds():
    pd.DataFrame(st.session_state.completed_rounds, columns=["Team", "Subject", "Bracket Stage"]).to_csv(ROUNDS_FILE, index=False)

def load_completed_rounds():
    if os.path.exists(ROUNDS_FILE):
        df = pd.read_csv(ROUNDS_FILE)
        return df.values.tolist()
    return []

# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------
if "scores" not in st.session_state:
    st.session_state.scores = load_scores()
if "completed_rounds" not in st.session_state:
    st.session_state.completed_rounds = load_completed_rounds()
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
# CORE ENGINE WORKFLOWS
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

    def get_csv_value(row, possible_names, default="N/A"):
        for p in possible_names:
            if p.lower() in headers_lower:
                idx = headers_lower.index(p.lower())
                return row.get(headers[idx], default)
        return default

    for q in raw_questions:
        standardized_q = {
            'question': get_csv_value(q, ['question', 'questions', 'q', 'text']),
            'optiona': get_csv_value(q, ['optiona', 'option a', 'a', 'opt a', 'choice a', 'option 1', 'opt1']),
            'optionb': get_csv_value(q, ['optionb', 'option b', 'b', 'opt b', 'choice b', 'option 2', 'opt2']),
            'optionc': get_csv_value(q, ['optionc', 'option c', 'c', 'opt c', 'choice c', 'option 3', 'opt3']),
            'optiond': get_csv_value(q, ['optiond', 'option d', 'd', 'opt d', 'choice d', 'option 4', 'opt4']),
            'optione': get_csv_value(q, ['optione', 'option e', 'e', 'opt e', 'choice e', 'option 5', 'opt5']),
            'answer': str(get_csv_value(q, ['answer', 'correct', 'correct answer', 'ans'], 'A')).strip()
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
        
        round_log_entry = [team, subject, f"Round {r_num}"]
        
        if round_log_entry not in st.session_state.completed_rounds:
            st.session_state.scores[team] += st.session_state.round_score
            st.session_state.completed_rounds.append(round_log_entry)
            save_scores()
            save_completed_rounds()
        
        st.session_state.timer_active = False
        st.session_state.current_question = None
        st.session_state.round_team = None
        st.session_state.round_subject = None

# -------------------------------
# STREAMLIT USER INTERFACE
# -------------------------------
st.title("🏆 Faculty of Computing Quiz Competition")

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

is_already_played = [chosen_team, chosen_subject, f"Round {current_round_id}"] in st.session_state.completed_rounds if chosen_team else False

if is_already_played:
    st.sidebar.error(f"🚫 {chosen_team} has already attempted {chosen_subject} for Round {current_round_id}!")

st.sidebar.info(f"📁 Target Question File: `{BASE_SUBJECTS[chosen_subject]}{current_round_id}.csv`")

if st.sidebar.button("🚀 Start 3-Minute Round", disabled=(st.session_state.timer_active or is_already_played or not chosen_team)):
    start_timer(chosen_team, chosen_subject, current_round_id)
    st.rerun()

# --- GAMEPLAY INTERACTION ---
if st.session_state.timer_active and st.session_state.round_team:
    elapsed = time.time() - st.session_state.start_time
    remaining = max(0, 180 - int(elapsed))
    
    if remaining <= 0:
        terminate_active_round()
        st.error("⏰ Time's Up!")
        if st.button("Proceed to Results"):
            st.rerun()
    else:
        st.markdown(f"### 🎯 Team **{st.session_state.round_team}** is playing **{st.session_state.round_subject}** (Round {st.session_state.active_round_num})!")
        
        # Real-time dashboard progress metrics
        st.progress(remaining / 180)
        st.info(f"⏳ Time Remaining: **{remaining}** seconds | Points Captured: **{st.session_state.round_score}**")
        
        q = st.session_state.current_question
        if q:
            st.write(f"**Question:** {q['question']}")
            options = [
                f"A: {q.get('optiona','N/A')}", 
                f"B: {q.get('optionb','N/A')}", 
                f"C: {q.get('optionc','N/A')}", 
                f"D: {q.get('optiond','N/A')}", 
                f"E: {q.get('optione','N/A')}"
            ]
            
            choice = st.radio("Options", options, index=None, key="current_options_radio")
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Submit Answer", type="primary"):
                    if choice:
                        user_letter = choice[0]
                        if user_letter.upper() == str(q['answer']).strip().upper():
                            st.session_state.round_score += 1
                            st.toast("Correct! 🎉", icon="✅")
                        else:
                            st.toast(f"Wrong! Correct was {q['answer']}", icon="❌")
                        set_next_question()
                        st.rerun()
                    else:
                        st.warning("Please pick an option!")
            with col2:
                if st.button("⏭️ Skip Question"):
                    set_next_question()
                    st.rerun()
        else:
            st.warning("No more questions available in this category pool.")
            if st.button("End Round Early"):
                terminate_active_round()
                st.rerun()
                
        # Heartbeat sync delay loop for live visual countdown updates
        time.sleep(0.1)
        st.rerun()

# --- STANDINGS & SCOREBOARD DISPLAY ---
st.write("---")
st.subheader("📊 Live Leaderboard")

scores_df = pd.DataFrame(list(st.session_state.scores.items()), columns=["Team", "Total Score"])
scores_df = scores_df[scores_df["Team"].isin(ALL_TEAMS)]
scores_df = scores_df.sort_values(by="Total Score", ascending=False).reset_index(drop=True)
st.dataframe(scores_df.set_index("Team"), use_container_width=True)

if st.session_state.completed_rounds:
    with st.expander("📝 View Match Logs (Completed Rounds)"):
        logs_df = pd.DataFrame(st.session_state.completed_rounds, columns=["Team", "Subject Area", "Bracket Stage"])
        st.table(logs_df[logs_df["Team"].isin(ALL_TEAMS)])

# -------------------------------
# CSS FOOTER ARCHITECTURE (WIDE-SCREEN OPTIMIZED)
# -------------------------------
st.markdown("""
    <style>
    .quiz-footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0e1117;
        color: #e2e8f0;
        
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: center;
        
        padding: 15px 40px;
        font-size: 22px;
        font-weight: 600;
        border-top: 2px solid #262730;
        z-index: 999;
    }
    .footer-text-center {
        text-align: center;
        grid-column: 2;
        max-width: 1000px;
    }
    .footer-logo-right {
        grid-column: 3;
        justify-self: end;
    }
    .footer-logo-right img {
        height: 45px;
        width: auto;
        object-fit: contain;
    }
    .main .block-container {
        padding-bottom: 140px !important;
        max-width: 95% !important;
    }
    </style>
    """, unsafe_allow_html=True)

current_year = datetime.now().year
total_completed = len(st.session_state.completed_rounds)
logo_base64 = get_base64_image(LOGO_FILE)

logo_container = f'<div class="footer-logo-right"><img src="data:image/png;base64,{logo_base64}" alt="Logo"></div>' if logo_base64 else '<div class="footer-logo-right"></div>'

footer_html = f"""
    <div class="quiz-footer">
        <div class="footer-left-spacer"></div>
        <div class="footer-text-center">
            Faculty of Computing Inter-department Quiz Competition • {current_year} • 📊 Completed Match Rounds Tally: {total_completed}
        </div>
        {logo_container}
    </div>
"""
st.markdown(footer_html, unsafe_allow_html=True)