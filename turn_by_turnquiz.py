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
        if q_text in globally_taken_questions or q_text ==
