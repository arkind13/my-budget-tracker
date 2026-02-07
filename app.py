import streamlit as st
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Arsenal Budget & AI Tracker", layout="wide")

# --- GOOGLE SHEETS CONNECTION ---
# We will set the URL in the Streamlit Dashboard "Secrets" later
conn = st.connection("gsheets", type=GSheetsConnection)

# --- DATE LOGIC ---
NOW = datetime.now()
RESET_DAY = 25
# (Auto-calc dates logic same as before...)

st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("Monthly Token Cycle")
    # Pull last value from Sheet if it exists, otherwise default
    last_tokens = 632000 
    current_tokens = st.number_input("Update Tokens Used:", value=last_tokens)
    
    if st.button("Save Token Usage"):
        new_data = pd.DataFrame([{"Date": NOW.strftime("%Y-%m-%d"), "Usage": current_tokens}])
        # Note: Writing to GSheets requires 'Secrets' setup in Phase 3
        st.success("Usage Saved to Cloud!")

    # (Calculation logic for Daily Limit same as before...)

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget (Thurs Start)")
    weekly_limit = st.number_input("Weekly Budget (AUD):", value=630.0)
    spent_to_date = st.number_input("Total Spent including Today:", value=180.0)

    if st.button("Save Expenses"):
        st.success("Expenses Saved!")

    # (Calculation logic for remaining days same as before...)

# --- TAB 3: ARSENAL MATCH TRACKER ---
with tab3:
    st.header("Match Day Centre")
    c1, c2 = st.columns(2)
    c1.metric("Last Match", "1 - 0 (W)", "vs Chelsea")
    c2.metric("Next Match", "02:00 AM", "Sun 8 Feb (SYD)")
    
    st.subheader("PL Table - Top 4")
    st.table({
        "Pos": [1, 2, 3, 4],
        "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
        "Pts": [53, 47, 46, 41]
    })
