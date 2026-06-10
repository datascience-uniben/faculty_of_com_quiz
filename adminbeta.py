import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# Set page configuration (MUST BE FIRST)
st.set_page_config(
    page_title="Faculty Quiz Admin Portal",
    page_icon="⚙️",
    layout="wide"
)

TEAMS_FILE = "team.csv"
SCORES_FILE = "scores.csv"
ROUNDS_FILE = "completed_rounds.csv"

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

st.title("⚙️ Faculty of Computing Quiz Competition — Admin Dashboard")

# -----------------------------------------------------------------
# DATA LOADING & ROUND SCORE PARSING PIPELINE
# -----------------------------------------------------------------
def load_dashboard_data():
    # 1. Load running totals
    if os.path.exists(SCORES_FILE):
        try:
            df_scores = pd.read_csv(SCORES_FILE)
            df_scores["Team"] = df_scores["Team"].astype(str)
        except Exception:
            df_scores = pd.DataFrame(columns=["Team", "Total Score"])
    else:
        df_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
    
    # Ensure all teams exist in the dataframe
    existing_teams = df_scores["Team"].tolist() if not df_scores.empty else []
    missing_records = [{"Team": t, "Total Score": 0} for t in ALL_TEAMS if t not in existing_teams]
    if missing_records:
        df_scores = pd.concat([df_scores, pd.DataFrame(missing_records)], ignore_index=True)
        
    df_scores = df_scores[df_scores["Team"].isin(ALL_TEAMS)]
    df_scores = df_scores.sort_values(by="Total Score", ascending=False).reset_index(drop=True)
    
    # 2. Load Match Logs
    if os.path.exists(ROUNDS_FILE):
        try:
            df_rounds = pd.read_csv(ROUNDS_FILE)
            df_rounds["Team"] = df_rounds["Team"].astype(str)
            df_rounds = df_rounds[df_rounds["Team"].isin(ALL_TEAMS)]
        except Exception:
            df_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage"])
    else:
        df_rounds = pd.DataFrame(columns=["Team", "Subject", "Bracket Stage"])
        
    return df_scores, df_rounds

# -----------------------------------------------------------------
# AUTONOMOUS LIVE MONITORING LOOP
# -----------------------------------------------------------------
@st.fragment(run_every=3.0)
def render_live_monitoring_view():
    df_scores, df_rounds = load_dashboard_data()
    ranked_teams = df_scores["Team"].tolist()

    # --- BRACKET STAGE STATS VISUALIZATION ---
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
    
    # --- UI MAIN LAYOUT ---
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("🏆 Live Scores from Team")
        if not df_scores.empty and df_scores.iloc[0]["Total Score"] > 0:
            st.success(f"🌟 **Current Tournament Leader:** Team {df_scores.iloc[0]['Team']} ({df_scores.iloc[0]['Total Score']} pts)")
            
        st.dataframe(
            df_scores.set_index("Team"), 
            use_container_width=True,
            column_config={"Total Score": st.column_config.NumberColumn(format="%d Points")}
        )
        
    with col2:
        st.subheader("📊 Round-by-Round Score Breakdown")
        
        # Build the dynamic matrix
        matrix_data = []
        for team in ALL_TEAMS:
            # Filter logs just for this team
            team_logs = df_rounds[df_rounds["Team"] == team]
            
            # Since your main engine increments total score, we can parse individual history 
            # or extract points per bracket if mapped. For a clean UI representation:
            r1_played = not team_logs[team_logs["Bracket Stage"] == "Round 1"].empty
            r2_played = not team_logs[team_logs["Bracket Stage"] == "Round 2"].empty
            r3_played = not team_logs[team_logs["Bracket Stage"] == "Round 3"].empty
            r4_played = not team_logs[team_logs["Bracket Stage"] == "Round 4"].empty
            r5_played = not team_logs[team_logs["Bracket Stage"] == "Round 5"].empty
            
            # Fetch current total assigned to the team
            total_pts = df_scores[df_scores["Team"] == team]["Total Score"].values[0] if not df_scores[df_scores["Team"] == team].empty else 0
            
            matrix_data.append({
                "Team": team,
                "Round 1": "✅ Attempted" if r1_played else "⏳ Pending",
                "Round 2": "✅ Attempted" if r2_played else "⏳ Pending",
                "Round 3": "✅ Attempted" if r3_played else "⏳ Pending",
                "Round 4": "✅ Attempted" if r4_played else "⏳ Pending",
                "Round 5": "✅ Attempted" if r5_played else "⏳ Pending",
                "Total Score": f"{total_pts} pts"
            })
            
        df_matrix = pd.DataFrame(matrix_data)
        # Sort matrix to match leaderboard standings
        df_matrix["_sort_idx"] = df_matrix["Team"].apply(lambda x: ranked_teams.index(x) if x in ranked_teams else 99)
        df_matrix = df_matrix.sort_values("_sort_idx").drop(columns=["_sort_idx"]).reset_index(drop=True)
        
        st.dataframe(df_matrix.set_index("Team"), use_container_width=True)

        # Raw Activity Logs Expander
        with st.expander("📝 View Raw Match History Logs"):
            if df_rounds.empty:
                st.info("No logs found.")
            else:
                st.dataframe(df_rounds, use_container_width=True, hide_index=True)

# Run the isolated auto-refreshing view
render_live_monitoring_view()

# -----------------------------------------------------------------
# ADMIN CONTROL PANEL (SIDEBAR)
# -----------------------------------------------------------------
st.sidebar.header("⚠️ Admin Control Panel")
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False

if not st.session_state.confirm_reset:
    if st.sidebar.button("💥 Reset All Quiz Data", type="primary", use_container_width=True):
        st.session_state.confirm_reset = True
        st.rerun()
else:
    st.sidebar.error("❗ PERMANENTLY WIPE EVERYTHING?")
    col_yes, col_no = st.sidebar.columns(2)
    if col_yes.button("Yes, Wipe", type="primary", use_container_width=True):
        fresh_scores = pd.DataFrame(list({t: 0 for t in ALL_TEAMS}.items()), columns=["Team", "Total Score"])
        fresh_scores.to_csv(SCORES_FILE, index=False)
        if os.path.exists(ROUNDS_FILE):
            os.remove(ROUNDS_FILE)
        st.session_state.confirm_reset = False
        st.toast("Databases successfully wiped! 🧹", icon="✅")
        time.sleep(1)
        st.rerun()
    if col_no.button("Cancel", use_container_width=True):
        st.session_state.confirm_reset = False
        st.rerun()

if st.sidebar.button("🔄 Force Interface Redraw", use_container_width=True):
    st.rerun()

# -------------------------------
# STICKY CSS FOOTER WITH SIDEBAR OFFSET
# -------------------------------
st.markdown("""
    <style>
    .admin-footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0e1117;
        color: #737a85;
        text-align: center;
        padding: 12px 0;
        font-size: 14px;
        font-weight: 500;
        border-top: 1px solid #262730;
        z-index: 999;
    }
    .main .block-container { padding-bottom: 80px !important; }
    @media (min-width: 576px) { .admin-footer { padding-left: 15rem; } }
    </style>
    """, unsafe_allow_html=True)

current_year = datetime.now().year
st.markdown(f'<div class="admin-footer">⚙️ Faculty of Computing Quiz Administrative Dashboard • {current_year} • 📡 Automated Real-time Sync Active</div>', unsafe_allow_html=True)