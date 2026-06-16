import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import os  # <-- Fixed: Added missing import to resolve NameError
from datetime import datetime
from io import StringIO

# Set page configuration (MUST BE FIRST)
st.set_page_config(
    page_title="Faculty Quiz Admin Portal",
    page_icon="⚙️",
    layout="wide"
)

# --- REPOSITORY PATH CONSTANTS ---
REPO_OWNER = "datascience-uniben"       
REPO_NAME = "faculty_of_com_quiz"   
SCORES_FILE = "scores.csv"
ROUNDS_FILE = "completed_rounds.csv"
TEAMS_FILE = "team.csv"
USERS_FILE = "users.csv"  # <-- Tracked for security overrides
BRANCH = "main"

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def load_allowed_teams():
    """Attempts to pull active team definitions dynamically from GitHub."""
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
        
    if os.path.exists(TEAMS_FILE):
        try:
            df = pd.read_csv(TEAMS_FILE)
            team_col = [col for col in df.columns if 'team' in col.lower()]
            return [str(name).strip() for name in df[team_col[0]].dropna().unique()] if team_col else [str(name).strip() for name in df.iloc[:, 0].dropna().unique()]
        except Exception:
            return ["A", "B", "C", "D", "E", "F"]
            
    return ["A", "B", "C", "D", "E", "F"]

ALL_TEAMS = load_allowed_teams()

st.title("⚙️ Faculty of Computing Quiz Competition — Admin & Screen Dashboard")

# -----------------------------------------------------------------
# DATA SYNC PIPELINE (GITHUB REST API LAYER)
# -----------------------------------------------------------------
def load_dashboard_data_from_github():
    # 1. Fetch live scoreboard metrics
    url_scores = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{SCORES_FILE}"
    res_scores = requests.get(url_scores, headers=HEADERS, params={"ref": BRANCH})
    
    if res_scores.status_code == 200:
        content = base64.b64decode(res_scores.json()["content"]).decode("utf-8")
        df_scores = pd.read_csv(StringIO(content))
        df_scores["Team"] = df_scores["Team"].astype(str)
    else:
        df_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
    
    # Pad out missing records inside dataset frame cleanly
    existing_teams = df_scores["Team"].tolist() if not df_scores.empty else []
    missing = [{"Team": t, "Total Score": 0} for t in ALL_TEAMS if t not in existing_teams]
    if missing:
        df_scores = pd.concat([df_scores, pd.DataFrame(missing)], ignore_index=True)
        
    df_scores = df_scores[df_scores["Team"].isin(ALL_TEAMS)]
    df_scores = df_scores.sort_values(by="Total Score", ascending=False).reset_index(drop=True)
    
    # 2. Fetch live round progression logs
    url_rounds = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{ROUNDS_FILE}"
    res_rounds = requests.get(url_rounds, headers=HEADERS, params={"ref": BRANCH})
    
    if res_rounds.status_code == 200:
        content = base64.b64decode(res_rounds.json()["content"]).decode("utf-8")
        df_rounds = pd.read_csv(StringIO(content))
        df_rounds["Team"] = df_rounds["Team"].astype(str)
        df_rounds = df_rounds[df_rounds["Team"].isin(ALL_TEAMS)]
    else:
        df_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
        
    return df_scores, df_rounds

# -----------------------------------------------------------------
# AUTONOMOUS LIVE MONITORING PROJECTOR SCREEN
# -----------------------------------------------------------------
@st.fragment(run_every=4.0) 
def render_live_monitoring_view():
    df_scores, df_rounds = load_dashboard_data_from_github()
    ranked_teams = df_scores["Team"].tolist()

    # --- BRACKET ELIMINATION TRACKING PANELS ---
    st.subheader("🏁 Elimination Tournament Bracket Status")
    stages_meta = [
        {"title": "Round 2 (Top 5)", "cutoff": 5},
        {"title": "Round 3 (Top 4)", "cutoff": 4},
        {"title": "Round 4 (Top 3)", "cutoff": 3},
        {"title": "Finals (Top 2)", "cutoff": 2}
    ]
    
    cols = st.columns(4)
    for i, stage in enumerate(stages_meta):
        with cols[i]:
            cutoff = stage["cutoff"]
            if len(ranked_teams) >= cutoff:
                borderline_team = ranked_teams[cutoff - 1]
                st.metric(
                    label=stage["title"], 
                    value=f"Top {cutoff} Qualified", 
                    delta=f"Cutoff Line: Team {borderline_team}", 
                    delta_color="normal"
                )
            else:
                st.metric(label=stage["title"], value="Calculating...")
                
    st.write("---")
    
    # --- SCREEN UI MAIN MATRIX GRID ---
    col1, col2 = st.columns([1, 1.2], gap="large")
    
    with col1:
        st.subheader("🏆 Live Leaderboard Standings")
        if not df_scores.empty and df_scores.iloc[0]["Total Score"] > 0:
            st.success(f"🌟 **Current Tournament Leader:** Team {df_scores.iloc[0]['Team']} ({df_scores.iloc[0]['Total Score']} pts)")
            
        st.dataframe(
            df_scores.set_index("Team"), 
            use_container_width=True,
            column_config={"Total Score": st.column_config.NumberColumn(format="%d Points")}
        )
        
    with col2:
        st.subheader("📊 Round-by-Round Numerical Breakdown")
        
        matrix_data = []
        for team in ALL_TEAMS:
            team_logs = df_rounds[df_rounds["Team"] == team]
            
            def extract_round_score(round_str):
                match_row = team_logs[team_logs["Bracket Stage"] == round_str]
                if not match_row.empty:
                    return f"{match_row.iloc[0].get('Points Scored', '✅')} pts"
                return "⏳ Pending"

            total_pts = df_scores[df_scores["Team"] == team]["Total Score"].values[0] if not df_scores[df_scores["Team"] == team].empty else 0
            
            matrix_data.append({
                "Team": team,
                "Round 1": extract_round_score("Round 1"),
                "Round 2": extract_round_score("Round 2"),
                "Round 3": extract_round_score("Round 3"),
                "Round 4": extract_round_score("Round 4"),
                "Round 5": extract_round_score("Round 5"),
                "Aggregate": f"{total_pts} pts"
            })
            
        df_matrix = pd.DataFrame(matrix_data)
        df_matrix["_sort_idx"] = df_matrix["Team"].apply(lambda x: ranked_teams.index(x) if x in ranked_teams else 99)
        df_matrix = df_matrix.sort_values("_sort_idx").drop(columns=["_sort_idx"]).reset_index(drop=True)
        
        st.dataframe(df_matrix.set_index("Team"), use_container_width=True)

        with st.expander("📝 View Raw Historical Activity Logs"):
            if df_rounds.empty:
                st.info("No records stored yet.")
            else:
                st.dataframe(df_rounds, use_container_width=True, hide_index=True)

# Run the live display
render_live_monitoring_view()

# -----------------------------------------------------------------
# ADMIN CONTROL PANEL & SECURITY MANAGEMENT
# -----------------------------------------------------------------
st.sidebar.header("⚠️ Admin Control Panel")

# 🔓 EMERGENCY OVERRIDE BUTTON (Clears concurrent hardware/tab blocks)
if st.sidebar.button("🔓 Clear Active Session Locks", use_container_width=True):
    with st.spinner("Flushing authentication matrices..."):
        url_users = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{USERS_FILE}"
        res = requests.get(url_users, headers=HEADERS, params={"ref": BRANCH})
        if res.status_code == 200:
            content = base64.b64decode(res.json()["content"]).decode("utf-8")
            df_u = pd.read_csv(StringIO(content))
            df_u.columns = [str(col).strip().lower() for col in df_u.columns]
            
            if "is_logged_in" in df_u.columns:
                df_u["is_logged_in"] = 0  # Force clear all lockout tracking counters
                csv_str = df_u.to_csv(index=False)
                encoded = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")
                sha = res.json().get("sha")
                
                p_load = {"message": "🔓 Administrative Session Lock Override", "content": encoded, "branch": BRANCH, "sha": sha}
                requests.put(url_users, headers=HEADERS, data=json.dumps(p_load))
                st.sidebar.success("All hardware login locks cleared! 🔓")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error("Error: 'is_logged_in' column not found in users.csv")
        else:
            st.sidebar.error("Could not fetch user file from GitHub.")

st.sidebar.write("---")

# 💥 HARD DATA RESET CONTROLS
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False

if not st.session_state.confirm_reset:
    if st.sidebar.button("💥 Reset All Quiz Data", type="primary", use_container_width=True):
        st.session_state.confirm_reset = True
        st.rerun()
else:
    st.sidebar.error("❗ PERMANENTLY WIPE GITHUB DATABASE?")
    col_yes, col_no = st.sidebar.columns(2)
    
    if col_yes.button("Yes, Wipe", type="primary", use_container_width=True):
        fresh_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
        fresh_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage", "Points Scored"])
        
        def api_wipe(path, df):
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
            csv_str = df.to_csv(index=False)
            encoded = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")
            res = requests.get(url, headers=HEADERS, params={"ref": BRANCH})
            sha = res.json().get("sha") if res.status_code == 200 else None
            p_load = {"message": "💥 Administrative Database Reset", "content": encoded, "branch": BRANCH}
            if sha: p_load["sha"] = sha
            requests.put(url, headers=HEADERS, data=json.dumps(p_load))

        api_wipe(SCORES_FILE, fresh_scores)
        api_wipe(ROUNDS_FILE, fresh_rounds)
            
        st.session_state.confirm_reset = False
        st.toast("GitHub files successfully wiped clean! 🧹", icon="✅")
        time.sleep(1)
        st.rerun()
        
    if col_no.button("Cancel", use_container_width=True):
        st.session_state.confirm_reset = False
        st.rerun()

if st.sidebar.button("🔄 Force Interface Redraw", use_container_width=True):
    st.rerun()

# --- ADMIN FOOTER DESIGN ---
st.markdown("""<style>.admin-footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #0e1117; color: #737a85; text-align: center; padding: 12px 0; font-size: 14px; font-weight: 500; border-top: 1px solid #262730; z-index: 999; } .main .block-container { padding-bottom: 80px !important; } @media (min-width: 576px) { .admin-footer { padding-left: 15rem; } }</style>""", unsafe_allow_html=True)
st.markdown(f'<div class="admin-footer">⚙️ Faculty of Computing Quiz Administrative Dashboard • {datetime.now().year} • 📡 Automated Real-time Sync Active</div>', unsafe_allow_html=True)
