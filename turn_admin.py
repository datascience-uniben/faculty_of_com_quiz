import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import os  
from datetime import datetime
from io import StringIO

# Set page configuration (MUST BE FIRST)
st.set_page_config(
    page_title="Faculty Quiz Admin Portal",
    page_icon="uniben.png",  
    layout="wide"
)

# --- REPOSITORY PATH CONSTANTS ---
REPO_OWNER = "datascience-uniben"       
REPO_NAME = "faculty_of_com_quiz"   
SCORES_FILE = "scores.csv"
ROUNDS_FILE = "completed_rounds.csv"
TEAMS_FILE = "team.csv"
USERS_FILE = "users.csv"  
TAKEN_QUESTIONS_FILE = "taken_questions.csv" 
LOGO_FILE = "uniben.png"
BRANCH = "main"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

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

col_adm_logo, col_adm_title = st.columns([1, 14])
with col_adm_logo:
    if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=70)
with col_adm_title:
    st.markdown("<h1 style='margin-top: -5px;'>Faculty of Computing Quiz Competition — Admin Dashboard</h1>", unsafe_allow_html=True)

def load_dashboard_data_from_github():
    url_scores = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{SCORES_FILE}"
    res_scores = requests.get(url_scores, headers=HEADERS, params={"ref": BRANCH})
    
    if res_scores.status_code == 200:
        content = base64.b64decode(res_scores.json()["content"]).decode("utf-8")
        try:
            df_scores = pd.read_csv(StringIO(content))
            df_scores.columns = [str(c).strip().lower() for c in df_scores.columns]
            team_header = "team" if "team" in df_scores.columns else df_scores.columns[0]
            score_header = "total score" if "total score" in df_scores.columns else df_scores.columns[1]
            df_scores = df_scores.rename(columns={team_header: "Team", score_header: "Total Score"})
            df_scores["Team"] = df_scores["Team"].astype(str)
        except pd.errors.EmptyDataError:
            df_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
    else:
        df_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
    
    existing_teams = df_scores["Team"].tolist() if not df_scores.empty else []
    missing = [{"Team": t, "Total Score": 0} for t in ALL_TEAMS if t not in existing_teams]
    if missing:
        df_scores = pd.concat([df_scores, pd.DataFrame(missing)], ignore_index=True)
        
    df_scores = df_scores[df_scores["Team"].isin(ALL_TEAMS)]
    df_scores = df_scores.sort_values(by="Total Score", ascending=False).reset_index(drop=True)
    
    url_rounds = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{ROUNDS_FILE}"
    res_rounds = requests.get(url_rounds, headers=HEADERS, params={"ref": BRANCH})
    
    if res_rounds.status_code == 200:
        content = base64.b64decode(res_rounds.json()["content"]).decode("utf-8")
        try:
            df_rounds = pd.read_csv(StringIO(content))
        except pd.errors.EmptyDataError:
            df_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
    else:
        df_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
        
    return df_scores, df_rounds

# Sidebar selectors mirroring the exact filtered tracking criteria logic
st.sidebar.header("Active Round View Filter")
total_teams_count = len(ALL_TEAMS)
stage_configurations = {
    "Round 1: Preliminary": {"round": 1, "cutoff": total_teams_count},
    "Round 2: Quarter-Final": {"round": 2, "cutoff": min(5, total_teams_count)},
    "Round 3: Semi-Final": {"round": 3, "cutoff": min(4, total_teams_count)},
    "Round 4: Third-Place Playoff": {"round": 4, "cutoff": min(3, total_teams_count)},
    "💥 Round 5: Sudden Death": {"round": 5, "cutoff": total_teams_count}
}
selected_adm_label = st.sidebar.selectbox("Filter Metrics View", list(stage_configurations.keys()))
current_round_id = stage_configurations[selected_adm_label]["round"]
allowed_count = stage_configurations[selected_adm_label]["cutoff"]

@st.fragment(run_every=4.0) 
def render_live_monitoring_view():
    df_scores, df_rounds = load_dashboard_data_from_github()
    ranked_teams = df_scores["Team"].tolist()

    st.subheader("🏁 Interleaved Match Elimination Tracker")
    stages_meta = [
        {"title": "Round 1 (All Teams)", "cutoff": len(ALL_TEAMS)},
        {"title": "Round 2 (Top 5)", "cutoff": 5},
        {"title": "Round 3 (Top 4)", "cutoff": 4},
        {"title": "Round 4 (Top 3)", "cutoff": 3},
        {"title": "💥 Round 5 (Sudden Death)", "cutoff": len(ALL_TEAMS)}
    ]
    
    cols = st.columns(5)
    for i, stage in enumerate(stages_meta):
        with cols[i]:
            cutoff = stage["cutoff"]
            if len(ranked_teams) >= cutoff and i != 4:
                borderline_team = ranked_teams[cutoff - 1]
                st.metric(label=stage["title"], value="Active Bracket", delta=f"Cutoff: Team {borderline_team}")
            else:
                st.metric(label=stage["title"], value="Sudden-Death Ready" if i==4 else "Calculating...")
                
    st.write("---")
    
    col1, col2 = st.columns([1, 1.4], gap="large")
    
    with col1:
        st.subheader(f"🏆 Leaderboard ({selected_adm_label})")
        
        # Adjust leaderboard row tracking to filter on teams remaining for this round choice
        current_cutoff = allowed_count if current_round_id != 5 else len(ALL_TEAMS)
        round_visible_teams = ranked_teams[:current_cutoff]
        filtered_scores_df = df_scores[df_scores["Team"].isin(round_visible_teams)].copy().reset_index(drop=True)
        
        if not filtered_scores_df.empty and len(filtered_scores_df) > 1:
            st.success(f"⭐ **Current Leader:** Team {filtered_scores_df.iloc[0]['Team']} ({filtered_scores_df.iloc[0]['Total Score']} pts)")
            st.error(f"🚨 **Bottom Tier (Removal Zone):** Team {filtered_scores_df.iloc[-1]['Team']} ({filtered_scores_df.iloc[-1]['Total Score']} pts)")
            
        st.dataframe(
            filtered_scores_df.set_index("Team"), 
            use_container_width=True,
            column_config={"Total Score": st.column_config.NumberColumn(format="%d Points")}
        )
        
    with col2:
        st.subheader("📊 Category Performance Tracking Matrix")
        df_rounds.columns = [str(c).strip().lower() for c in df_rounds.columns]
        
        team_col = "team" if "team" in df_rounds.columns else (df_rounds.columns[0] if not df_rounds.empty else None)
        subject_col = "subject" if "subject" in df_rounds.columns else (df_rounds.columns[1] if not df_rounds.empty else None)
        stage_col = "bracket stage" if "bracket stage" in df_rounds.columns else (df_rounds.columns[2] if not df_rounds.empty else None)
        score_col = "points scored" if "points scored" in df_rounds.columns else (df_rounds.columns[3] if not df_rounds.empty else None)

        matrix_data = []
        for team in round_visible_teams:
            team_logs = df_rounds[df_rounds[team_col].astype(str).str.lower() == str(team).lower()] if team_col else pd.DataFrame()
            
            def extract_cell(round_str, category_keyword):
                if team_logs.empty or not subject_col or not stage_col or not score_col: 
                    return "⏳ Pending"
                
                match_rows = team_logs[
                    (team_logs[stage_col].astype(str).str.lower() == round_str.lower()) & 
                    (team_logs[subject_col].astype(str).str.lower().str.contains(category_keyword.lower()))
                ]
                
                if not match_rows.empty:
                    if "round 1" in round_str.lower(): max_score = 4
                    elif "round 2" in round_str.lower(): max_score = 5
                    elif "round 3" in round_str.lower(): max_score = 6
                    elif "round 4" in round_str.lower(): max_score = 7
                    elif "round 5" in round_str.lower(): max_score = 8
                    else: max_score = 4
                    
                    return f"✅ Done ({match_rows.iloc[0][score_col]}/{max_score} pts)"
                return "⏳ Pending"

            total_pts = df_scores[df_scores["Team"] == team]["Total Score"].values[0] if not df_scores[df_scores["Team"] == team].empty else 0
            
            matrix_data.append({
                "Team": team, 
                "R1: Affairs": extract_cell("Round 1", "Affairs"), 
                "R1: Computing": extract_cell("Round 1", "Computing"),
                "R2: Affairs": extract_cell("Round 2", "Affairs"), 
                "R2: Computing": extract_cell("Round 2", "Computing"),
                "R3: Affairs": extract_cell("Round 3", "Affairs"), 
                "R3: Computing": extract_cell("Round 3", "Computing"),
                "R4: Affairs": extract_cell("Round 4", "Affairs"), 
                "R4: Computing": extract_cell("Round 4", "Computing"),
                "⚠️ Sudden Death": extract_cell("Round 5 Tie-Breaker", ""), 
                "Aggregate": f"{total_pts} pts"
            })
            
        if matrix_data:
            df_matrix = pd.DataFrame(matrix_data)
            df_matrix["_sort_idx"] = df_matrix["Team"].apply(lambda x: ranked_teams.index(x) if x in ranked_teams else 99)
            df_matrix = df_matrix.sort_values("_sort_idx").drop(columns=["_sort_idx"]).reset_index(drop=True)
            st.dataframe(df_matrix.set_index("Team"), use_container_width=True)
        else:
            st.info("No active teams logged for this filtered context view segment.")

render_live_monitoring_view()

# --- ADMIN PANEL CONTROL BUTTONS ---
st.sidebar.header("⚠️ Admin Control Panel")
if st.sidebar.button("🔓 Clear Active Session Locks", use_container_width=True):
    with st.spinner("Flushing hardware states..."):
        url_users = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{USERS_FILE}"
        res = requests.get(url_users, headers=HEADERS, params={"ref": BRANCH})
        if res.status_code == 200:
            content = base64.b64decode(res.json()["content"]).decode("utf-8")
            df_u = pd.read_csv(StringIO(content))
            df_u.columns = [str(col).strip().lower() for col in df_u.columns]
            if "is_logged_in" in df_u.columns:
                df_u["is_logged_in"] = 0  
                csv_str = df_u.to_csv(index=False)
                encoded = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")
                sha = res.json().get("sha")
                p_load = {"message": "🔓 Lock Override", "content": encoded, "branch": BRANCH, "sha": sha}
                requests.put(url_users, headers=HEADERS, data=json.dumps(p_load))
                st.sidebar.success("Locks released!")
                time.sleep(0.5)
                st.rerun()

st.sidebar.write("---")

if "confirm_reset" not in st.session_state: st.session_state.confirm_reset = False
if not st.session_state.confirm_reset:
    if st.sidebar.button("💥 Reset All Quiz Data", type="primary", use_container_width=True):
        st.session_state.confirm_reset = True
        st.rerun()
else:
    st.sidebar.error("❗ PERMANENTLY WIPE DATABASE?")
    col_yes, col_no = st.sidebar.columns(2)
    if col_yes.button("Yes, Wipe", type="primary", use_container_width=True):
        fresh_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
        fresh_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
        fresh_taken = pd.DataFrame({"question": ["_initialization_placeholder_"]}) 
        
        def api_wipe(path, df):
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
            csv_str = df.to_csv(index=False)
            encoded = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")
            res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
            sha = res.json().get("sha") if res.status_code == 200 else None
            p_load = {"message": "💥 Admin Wipe", "content": encoded, "branch": BRANCH}
            if sha: p_load["sha"] = sha
            requests.put(url, headers=HEADERS, data=json.dumps(p_load))

        api_wipe(SCORES_FILE, fresh_scores)
        api_wipe(ROUNDS_FILE, fresh_rounds)
        api_wipe(TAKEN_QUESTIONS_FILE, fresh_taken) 
        st.session_state.confirm_reset = False
        st.toast("GitHub records wiped clean! 🧹", icon="✅")
        time.sleep(0.5)
        st.rerun()
    if col_no.button("Cancel", use_container_width=True):
        st.session_state.confirm_reset = False; st.rerun()

st.markdown("""<style>.admin-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #737a85; text-align: center; padding: 12px 0; font-size: 14px; font-weight: 500; border-top: 1px solid #262730; z-index: 999; } .main .block-container { padding-bottom: 80px !important; } @media (min-width: 576px) { .admin-footer { padding-left: 15rem; } }</style>""", unsafe_allow_html=True)
st.markdown(f'<div class="admin-footer">⚙️ Faculty of Computing Quiz Administrative Dashboard • 2026 • 📡 Automated Sync Active</div>', unsafe_allow_html=True)
