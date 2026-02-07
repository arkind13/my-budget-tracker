import streamlit as st
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="Gunners Budget Tracker", layout="wide", page_icon="🔴")

# 2. Connection to Google Sheets
# This requires the URL to be in your Streamlit Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Memory Logic: Load previous data from Sheets
try:
    token_df = conn.read(worksheet="Tokens", ttl=0)
    last_saved_tokens = int(token_df["Usage"].iloc[-1]) if not token_df.empty else 632000
    
    expense_df = conn.read(worksheet="Expenses", ttl=0)
    last_saved_expense = float(expense_df["Spent"].iloc[-1]) if not expense_df.empty else 0.0
except:
    last_saved_tokens = 632000
    last_saved_expense = 0.0

# 4. Date Logic
NOW = datetime.now()
RESET_DAY = 25

# Monthly Cycle calculation
if NOW.day >= RESET_DAY:
    start_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    next_month = (NOW.replace(day=1) + timedelta(days=32)).replace(day=RESET_DAY)
    end_date = next_month.replace(hour=17, minute=20)
else:
    end_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    prev_month = (NOW.replace(day=1) - timedelta(days=1)).replace(day=RESET_DAY)
    start_date = prev_month.replace(hour=17, minute=20)

days_passed = max((NOW - start_date).days, 1)
days_remaining = max((end_date - NOW).days, 1)

# --- APP INTERFACE ---
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("Monthly Token Cycle")
    current_tokens = st.number_input("Tokens Used to Date:", value=last_saved_tokens, step=1000)
    
    if st.button("Save Token Usage"):
        new_row = pd.DataFrame([{"Date": NOW.strftime("%Y-%m-%d"), "Usage": current_tokens}])
        conn.update(worksheet="Tokens", data=new_row)
        st.success("Usage Saved to Cloud!")
    
    st.divider()
    # Math
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
    weekly_limit = st.number_input("Weekly Budget:", value=630.0)
    spent_to_date = st.number_input("Spent including Today:", value=last_saved_expense)

    if st.button("Save Expenses"):
        new_exp = pd.DataFrame([{"Date": NOW.strftime("%Y-%m-%d"), "Spent": spent_to_date}])
        conn.update(worksheet="Expenses", data=new_exp)
        st.success("Expenses Saved to Cloud!")

    st.divider()
    days_since_thurs = (NOW.weekday() - 3) % 7
    days_left = 7 - (days_since_thurs + 1)
    remaining_money = weekly_limit - spent_to_date
    
    ca, cb = st.columns(2)
    ca.metric("Remaining Funds", f"${remaining_money:.2f}")
    if days_left > 0:
        cb.metric("Daily Limit (from tomorrow)", f"${(remaining_money/days_left):.2f}")
        st.write(f"📅 {days_left} days remaining in your week.")
    else:
        st.warning("Last day of the week! Reset tomorrow.")

# --- TAB 3: ARSENAL FC ---
with tab3:
    st.header("⚽ Match Day Centre")
    st.info("✅ **Last Match:** Arsenal 1 - 0 Chelsea (Carabao Cup Semi-Final) - *Final Bound!*")

    col_x, col_y = st.columns(2)
    with col_x:
        st.subheader("Next Opponent")
        st.markdown("### Sunderland (H)")
        st.write("🏆 Premier League | 🏟️ Emirates Stadium")
    with col_y:
        st.subheader("Kick-off (SYD)")
        st.markdown("### 02:00 AM")
        st.write("📅 Sunday, 8 Feb")

    st.divider()
    st.subheader("Premier League Table (Top 4)")
    st.table({
        "Pos": [1, 2, 3, 4],
        "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
        "Played": [24, 24, 24, 24],
        "Pts": [53, 47, 46, 41]
    })
    st.success("COYG! 6 Points Clear at the Top! 🏆")
