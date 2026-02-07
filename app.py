import streamlit as st
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Gunners Budget Tracker", layout="wide", page_icon="🔴")

# --- USER INPUTS (Change these numbers on GitHub to update defaults) ---
DEFAULT_TOKENS_USED = 632000
DEFAULT_WEEKLY_SPENT = 180.0
WEEKLY_BUDGET_LIMIT = 630.0

# --- ARSENAL DATA (Update these after each match) ---
LAST_MATCH_TXT = "Arsenal 1 - 0 Chelsea (Carabao Cup Semi)"
NEXT_OPPONENT = "Sunderland (H) 8th"
NEXT_KICKOFF = "02:00 AM, Sun 8 Feb (SYD)"
PL_TABLE = {
    "Pos": [1, 2, 3, 4],
    "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
    "Pts": [53, 47, 46, 41]
}

# --- DATE LOGIC ---
NOW = datetime.now()
RESET_DAY = 25

if NOW.day >= RESET_DAY:
    start_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    end_date = (start_date + timedelta(days=32)).replace(day=RESET_DAY)
else:
    end_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    start_date = (end_date - timedelta(days=5)).replace(day=RESET_DAY) - timedelta(days=25)

days_passed = max((NOW - start_date).days, 1)
days_remaining = max((end_date - NOW).days, 1)

# --- APP INTERFACE ---
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("Monthly Token Cycle")
    current_tokens = st.number_input("Tokens Used to Date:", value=DEFAULT_TOKENS_USED, step=1000)
    
    st.divider()
    avg_spent = current_tokens / days_passed
    remaining_tokens = 3000000 - current_tokens
    daily_limit = remaining_tokens / days_remaining
    
    c1, c2 = st.columns(2)
    c1.metric("Current Avg Daily", f"{int(avg_spent):,} tokens")
    c2.metric("New Daily Limit", f"{int(daily_limit):,} tokens")
    
    projected = current_tokens + (avg_spent * days_remaining)
    st.subheader(f"Projected Monthly: {int(projected):,} / 3,000,000")
    st.progress(min(projected / 3000000, 1.0))

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget (AUD)")
    spent_to_date = st.number_input("Spent including Today:", value=DEFAULT_WEEKLY_SPENT)

    st.divider()
    days_since_thurs = (NOW.weekday() - 3) % 7
    days_left = 7 - (days_since_thurs + 1)
    remaining_money = WEEKLY_BUDGET_LIMIT - spent_to_date
    
    ca, cb = st.columns(2)
    ca.metric("Remaining Funds", f"${remaining_money:.2f}")
    if days_left > 0:
        cb.metric("Daily Limit (from tomorrow)", f"${(remaining_money/days_left):.2f}")
        st.write(f"📅 {days_left} days remaining in your week.")
    else:
        st.warning("Last day of the week! Reset tomorrow (Thursday).")

# --- TAB 3: ARSENAL FC ---
with tab3:
    st.header("⚽ Match Day Centre")
    st.info(f"✅ **Last Match:** {LAST_MATCH_TXT}")

    col_x, col_y = st.columns(2)
    with col_x:
        st.subheader("Next Opponent")
        st.markdown(f"### {NEXT_OPPONENT}")
        st.write("🏆 Premier League | 🏟️ Emirates Stadium")
    with col_y:
        st.subheader("Kick-off (SYD)")
        st.markdown(f"### {NEXT_KICKOFF}")
    
    st.divider()
    st.subheader("Premier League Table (Top 4)")
    st.table(PL_TABLE)
    st.success("COYG! Top of the league! 🏆")
