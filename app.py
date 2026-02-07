import streamlit as st
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Gunners Budget Tracker", layout="wide", page_icon="🔴")

# --- ARSENAL DATA (Update these after each match) ---
LAST_MATCH_TXT = "Arsenal 1 - 0 Chelsea (Carabao Cup Semi)"
NEXT_OPPONENT = "Sunderland (H) 8th"
NEXT_KICKOFF = "02:00 AM, Sun 8 Feb (SYD)"
PL_TABLE = {
    "Pos": [1, 2, 3, 4],
    "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
    "Pts": [53, 47, 46, 41]
}

# --- DATE CALCULATIONS (SYDNEY TIME) ---
NOW = datetime.now()
MONTHLY_LIMIT = 3000000
RESET_DAY = 25

# Monthly Reset Logic
if NOW.day >= RESET_DAY:
    start_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)
    if NOW.month == 12:
        end_date = datetime(NOW.year + 1, 1, RESET_DAY, 17, 20)
    else:
        end_date = datetime(NOW.year, NOW.month + 1, RESET_DAY, 17, 20)
else:
    if NOW.month == 1:
        start_date = datetime(NOW.year - 1, 12, RESET_DAY, 17, 20)
    else:
        start_date = datetime(NOW.year, NOW.month - 1, RESET_DAY, 17, 20)
    end_date = datetime(NOW.year, NOW.month, RESET_DAY, 17, 20)

total_cycle_days = (end_date - start_date).days
days_passed_monthly = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- APP INTERFACE ---
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC"])

# --- TAB 1: AI FIESTA TOKENS ---
with tab1:
    st.header("AI Fiesta Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    current_tokens = st.number_input("Tokens Used to Date:", value=632000, step=1000)
    
    avg_spent_daily = current_tokens / days_passed_monthly
    remaining_tokens = MONTHLY_LIMIT - current_tokens
    daily_allowance_remaining = remaining_tokens / days_remaining_monthly
    projected_total = current_tokens + (avg_spent_daily * days_remaining_monthly)

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_spent_daily):,} tokens")
    c2.metric("Daily Goal", f"{int(daily_allowance_remaining):,} tokens", delta=f"{int(daily_allowance_remaining - avg_spent_daily):,} vs avg")
    c3.metric("Projected Monthly", f"{int(projected_total):,} / 3,000,000")

    # Arsenal Fan Themed Alerts
    if projected_total > MONTHLY_LIMIT:
        st.error(f"⚠️ We're losing the lead! Projected to exceed by {int(projected_total - MONTHLY_LIMIT):,} tokens.")
    else:
        st.success(f"✅ Clean sheet! Buffer of {int(MONTHLY_LIMIT - projected_total):,} tokens remaining.")

# --- TAB 2: PERSONAL WEEKLY BUDGET (THURS START) ---
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts **Thursday**. Calculations assume the day you enter data is **already finished**.")
    
    weekly_limit = st.number_input("Weekly Budget (AUD):", value=630.0, step=10.0)
    spent_to_date = st.number_input("Total Spent so far (including today):", value=180.0, step=1.0)
    
    # Calculate days left (Thursday = Day 0, Wednesday = Day 6)
    current_weekday = NOW.weekday() 
    # Adjusting weekday index so Thursday = 0
    # Python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    days_since_thurs = (current_weekday - 3) % 7
    
    # As per request: If today is Saturday, Saturday is over. 
    # Thursday (0), Friday (1), Saturday (2) are done.
    # Remaining days = 7 - (days_since_thurs + 1)
    days_left_weekly = 7 - (days_since_thurs + 1)
    
    remaining_funds = weekly_limit - spent_to_date

    # Avoid division by zero on Wednesday night
    if days_left_weekly > 0:
        daily_allowance_weekly = remaining_funds / days_left_weekly
    else:
        daily_allowance_weekly = remaining_funds

    st.divider()
    
    col_a, col_b = st.columns(2)
    col_a.metric("Remaining Budget", f"${remaining_funds:.2f}")
    
    if days_left_weekly > 0:
        col_b.metric("Allowed Daily Spend", f"${daily_allowance_weekly:.2f}")
        st.write(f"📅 **{days_left_weekly} days** remaining in your cycle (starting tomorrow).")
    else:
        col_b.metric("Allowed Daily Spend", "N/A")
        st.warning("Last day of the weekly cycle! New budget starts tomorrow (Thursday).")

    if remaining_funds < 0:
        st.error(f"Budget overspent by ${abs(remaining_funds):.2f}!")

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
