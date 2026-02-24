import streamlit as st
from datetime import datetime, timedelta
import pytz

# --- CONFIG ---
st.set_page_config(page_title="Gunners Budget Tracker", layout="wide", page_icon="🔴")

# --- ARSENAL DATA (Update these after each match) ---
LAST_MATCH_TXT = "Arsenal 3 - 0 Sunderland (Premier League)"
NEXT_OPPONENT = "Brentford (A) 7th"
NEXT_KICKOFF = "07:00 AM, Fri 13 Feb (SYD)"
PL_TABLE = {
    "Pos": [1, 2, 3, 4],
    "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
    "Pts": [56, 47, 47, 44]
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
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC", "🛒 Woolies Pay"])

# --- TAB 1: AI FIESTA TOKENS ---
with tab1:
    st.header("AI Fiesta Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    current_tokens = st.number_input("Tokens Used to Date:", value=632000, step=1000, format="%i")
    st.write(f"### Current Input: {current_tokens:,}")
    
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
    st.info("Week starts **Thursday**.")
    
    weekly_limit = st.number_input("Weekly Budget (AUD):", value=630.0, step=10.0)
    spent_to_date = st.number_input("Total Spent so far (including today):", value=180.0, step=1.0)

    # NEW: Add adjusted amount input field with default $0
    adjusted_amount = st.number_input("Adjusted Amount (AUD):", value=0.0, step=1.0)

    # NEW: Add checkbox to indicate if today is over
    today_is_over = st.checkbox("Today is over (count as completed day)")
    
    # Calculate days left (Thursday = Day 0, Wednesday = Day 6)
    current_weekday = NOW.weekday() 
    # Adjusting weekday index so Thursday = 0
    # Python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    days_since_thurs = (current_weekday - 3) % 7

# Check what day we're actually working with
st.write(f"Debug - Current weekday number: {current_weekday}")
st.write(f"Debug - Days since Thursday: {days_since_thurs}")

    
    # NEW: Time-based logic for today's completion
# If it's Wednesday (index 2) AND current time is past noon (12 PM), then today is effectively over
# Or more simply: We want to treat Wednesday as the "last day" regardless of time
if current_weekday == 2:  # Wednesday
    # For Wednesday specifically, always show 1 day left (the day itself)
    # But respect the checkbox for whether to count today as completed
    if today_is_over:
        days_left_weekly = 0  # Today is over, so no days left
    else:
        days_left_weekly = 1  # Today is not over, so 1 day left (Wednesday itself)
else:
    # For all other days, use normal calculation
    if today_is_over:
        days_left_weekly = 7 - (days_since_thurs + 1)
    else:
        days_left_weekly = 7 - days_since_thurs
    
    # NEW: Calculate remaining funds with adjusted amount
    remaining_funds = weekly_limit - spent_to_date + adjusted_amount

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
# COMPLETE DIAGNOSTIC
st.write("=== FULL SYSTEM DIAGNOSTIC ===")
st.write(f"**System Time:** {NOW}")
st.write(f"**Day Name:** {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][NOW.weekday()]}")

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

# --- TAB 4: WOOLWORTHS PAY CALCULATOR ---
with tab4:
    st.header("🛒 Woolies Pay Calculator")
    st.info("Enter hours separately. Rates include Casual Loading and Shift Penalties. Tax @28%")

    # Input Fields arranged in a 2x2 grid
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        norm_h = st.number_input("Standard Hours (Mon-Sat < 11pm):", value=17.5, step=0.5)
    with row1_col2:
        late_h = st.number_input("Late Night Hours (Mon-Sat > 11pm):", value=1.5, step=0.5)
    with row2_col1:
        sun_h = st.number_input("Sunday Hours (All day):", value=5.5, step=0.5)
    with row2_col2:
        ph_h = st.number_input("Public Holiday Hours:", value=0.0, step=0.5)

    # Constants based on your payslip
    BASE_ORD = 26.9797
    CAS_LOAD = 6.7449
    SHIFT_25 = 6.7449
    SHIFT_50 = 13.4899
    LAUNDRY = 6.25
    NET_GOAL = 520.00

    # Hourly Rates (Gross)
    rate_std = BASE_ORD + CAS_LOAD + SHIFT_25  # $40.84 (Standard)
    rate_pen = BASE_ORD + CAS_LOAD + SHIFT_50  # $47.58 (Sunday/Late Night)
    rate_ph  = BASE_ORD * 2.5                  # $67.45 (Public Holiday)

    # Gross Calculations
    gross_std = norm_h * rate_std
    gross_pen = (late_h + sun_h) * rate_pen
    gross_ph  = ph_h * rate_ph
    total_gross = gross_std + gross_pen + gross_ph
    
    # Net Calculations (Flat 28% Tax as requested)
    est_tax = total_gross * 0.28
    est_net = (total_gross - est_tax) + LAUNDRY
    total_hrs = norm_h + late_h + sun_h + ph_h

    # Display Metrics
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Net Pay", f"${est_net:.2f}")
    m2.metric("Total Hours", f"{total_hrs} hrs")
    
    # Goal Tracker Delta
    goal_delta = est_net - NET_GOAL
    m3.metric("Goal Status", f"${est_net:.2f}", delta=f"${goal_delta:.2f} vs $520")

    # Arsenal Themed Success/Warning
    if est_net >= NET_GOAL:
        st.success(f"🏆 Top of the Table! You've cleared the $520 target by ${goal_delta:.2f}.")
    else:
        st.warning(f"⚠️ Needs a Late Goal! You are ${abs(goal_delta):.2f} short of your $520 target.")
