import streamlit as st
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Arsenal & AI Dashboard", layout="wide")

# --- DATE LOGIC ---
NOW = datetime.now()
RESET_DAY = 25

# Monthly Cycle Logic
if NOW.day >= RESET_DAY:
    start_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    end_date = (start_date + timedelta(days=32)).replace(day=RESET_DAY)
else:
    end_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    start_date = (end_date - timedelta(days=5)).replace(day=RESET_DAY) - timedelta(days=25)

days_passed_monthly = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- APP LAYOUT ---
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("Monthly Token Cycle")
    current_tokens = st.number_input("Tokens Used to Date:", value=632000, step=1000)
    
    if st.button("Save Token Usage"):
        st.success("Usage Saved!")

    # EVERYTHING BELOW IS NOW INDENTED TO SHOW IN TAB 1
    st.divider()
    avg_spent_daily = current_tokens / days_passed_monthly
    remaining_tokens = 3000000 - current_tokens
    daily_limit = remaining_tokens / days_remaining_monthly
    
    col1, col2 = st.columns(2)
    col1.metric("Current Avg Daily", f"{int(avg_spent_daily):,} tokens")
    col2.metric("New Daily Limit", f"{int(daily_limit):,} tokens")
    
    st.subheader("Projected Total")
    projected = current_tokens + (avg_spent_daily * days_remaining_monthly)
    st.write(f"**{int(projected):,} / 3,000,000**")
    st.progress(min(projected / 3000000, 1.0))

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    weekly_limit = st.number_input("Weekly Budget (AUD):", value=630.0)
    spent_so_far = st.number_input("Spent including Today:", value=180.0)

    if st.button("Save Expenses"):
        st.success("Expenses Saved!")

    # CALCULATIONS INDENTED TO SHOW IN TAB 2
    st.divider()
    days_since_thurs = (NOW.weekday() - 3) % 7
    days_left = 7 - (days_since_thurs + 1)
    remaining_funds = weekly_limit - spent_so_far
    
    c_a, c_b = st.columns(2)
    c_a.metric("Remaining", f"${remaining_funds:.2f}")
    if days_left > 0:
        c_b.metric("Daily Limit (from tomorrow)", f"${(remaining_funds/days_left):.2f}")
        st.write(f"📅 **{days_left} days** remaining in your week.")
    else:
        st.warning("Last day of the week! Reset starts tomorrow.")

# --- TAB 3: ARSENAL TRACKER ---
with tab3:
    st.header("⚽ Match Day Centre")
    
    # Live Data for Feb 7, 2026
    col_x, col_y = st.columns(2)
    with col_x:
        st.metric("Next Opponent", "Sunderland (H)", "Premier League")
        st.write("🏟️ **Emirates Stadium**")
    with col_y:
        st.metric("Kick-off (SYD)", "02:00 AM", "Sun 8 Feb")
        st.write("🕒 *Today at 3:00 PM UK time*")

    st.divider()
    st.subheader("Premier League Standings")
    st.table({
        "Pos": [1, 2, 3, 4],
        "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
        "Pts": [53, 47, 46, 41]
    })
    st.success("COYG! Arsenal sits 6 points clear at the top! 🏆")
