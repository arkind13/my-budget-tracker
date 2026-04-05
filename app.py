import streamlit as st
from datetime import datetime, timedelta
import os, time
import pickle

os.environ['TZ'] = 'Australia/Sydney'
time.tzset()

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
RESET_DAY, RESET_HOUR, RESET_MIN = 25, 17, 20

def cycle_dates(ref):
    """Return (start, end) for the cycle that contains ref."""
    start = ref.replace(day=RESET_DAY, hour=RESET_HOUR, minute=RESET_MIN,
                        second=0, microsecond=0)
    if ref < start:  # still in previous cycle
        prev = (start.replace(day=1) - timedelta(days=1))
        start = prev.replace(day=RESET_DAY, hour=RESET_HOUR, minute=RESET_MIN,
                            second=0, microsecond=0)
    # next cycle
    m = (start.month % 12) + 1
    y = start.year + (1 if m == 1 else 0)
    end = start.replace(year=y, month=m)
    return start, end

start_date, end_date = cycle_dates(NOW)
total_cycle_days = (end_date - start_date).days
days_passed_monthly = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- PERSISTENCE FUNCTIONS ---
def save_state(tab_key, data):
    """Save state to a file"""
    try:
        with open(f"{tab_key}_state.pkl", "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        st.error(f"Error saving state: {e}")

def load_state(tab_key):
    """Load state from a file"""
    try:
        with open(f"{tab_key}_state.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        st.error(f"Error loading state: {e}")
        return {}

# Initialize session state for tabs
if "ai_tokens_value" not in st.session_state:
    ai_state = load_state("ai_tokens")
    st.session_state.ai_tokens_value = ai_state.get("value", 632000)

if "personal_budget_weekly_limit" not in st.session_state:
    pb_state = load_state("personal_budget")
    st.session_state.personal_budget_weekly_limit = pb_state.get("weekly_limit", 630.0)
    st.session_state.personal_budget_spent = pb_state.get("spent_to_date", 180.0)
    st.session_state.personal_budget_adjusted = pb_state.get("adjusted_amount", 0.0)
    st.session_state.personal_budget_today_is_over = pb_state.get("today_is_over", False)

if "woolies_pay_norm_h" not in st.session_state:
    wp_state = load_state("woolies_pay")
    st.session_state.woolies_pay_norm_h = wp_state.get("norm_h", 17.5)
    st.session_state.woolies_pay_late_h = wp_state.get("late_h", 1.5)
    st.session_state.woolies_pay_sun_h = wp_state.get("sun_h", 5.5)
    st.session_state.woolies_pay_ph_h = wp_state.get("ph_h", 0.0)

# --- APP INTERFACE ---
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC", "🛒 Woolies Pay"])

# --- TAB 1: AI FIESTA TOKENS ---
with tab1:
    st.header("AI Fiesta Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    current_tokens = st.number_input("Tokens Used to Date:", value=st.session_state.ai_tokens_value, step=1000, format="%i")
    st.write(f"### Current Input: {current_tokens:,}")
    
    # Save the value for next session
    st.session_state.ai_tokens_value = current_tokens
    save_state("ai_tokens", {"value": current_tokens})
    
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
    
    # Load saved values
    weekly_limit = st.number_input("Weekly Budget (AUD):", value=st.session_state.personal_budget_weekly_limit, step=10.0)
    spent_to_date = st.number_input("Total Spent so far (including today):", value=st.session_state.personal_budget_spent, step=1.0)

    # NEW: Add adjusted amount input field with default $$0
    adjusted_amount = st.number_input("Adjusted Amount (AUD):", value=st.session_state.personal_budget_adjusted, step=1.0)

    # NEW: Add checkbox to indicate if today is over
    today_is_over = st.checkbox("Today is over (count as completed day)", value=st.session_state.personal_budget_today_is_over)
    
    # Calculate days left (Thursday = Day 0, Wednesday = Day 6)
    current_weekday = NOW.weekday() 
    # Adjusting weekday index so Thursday = 0
    # Python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    days_since_thurs = (current_weekday - 3) % 7

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
    net_spent = spent_to_date - adjusted_amount

    # Avoid division by zero on Wednesday night
    if days_left_weekly > 0:
        daily_allowance_weekly = remaining_funds / days_left_weekly
    else:
        daily_allowance_weekly = remaining_funds

    # Save state
    st.session_state.personal_budget_weekly_limit = weekly_limit
    st.session_state.personal_budget_spent = spent_to_date
    st.session_state.personal_budget_adjusted = adjusted_amount
    st.session_state.personal_budget_today_is_over = today_is_over
    
    save_state("personal_budget", {
        "weekly_limit": weekly_limit,
        "spent_to_date": spent_to_date,
        "adjusted_amount": adjusted_amount,
        "today_is_over": today_is_over
    })

    st.divider()
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Remaining Budget", f"$${remaining_funds:.2f}")
    
    if days_left_weekly > 0:
        col_b.metric("Allowed Daily Spend", f"$${daily_allowance_weekly:.2f}")
        st.write(f"📅 **{days_left_weekly} days** remaining in your cycle")
    else:
        col_b.metric("Allowed Daily Spend", "Last Day of the Week")
        st.warning("Last day of the weekly cycle! New budget starts tomorrow (Thursday).")

    col_c.metric("Net Spent", f"$${net_spent:.2f}")

    if remaining_funds < 0:
        st.error(f"Budget overspent by $${abs(remaining_funds):.2f}!")

    # Check what day we're actually working with
    st.write(f" Current weekday number: {current_weekday}")
    st.write(f" Days since Thursday: {days_since_thurs}")
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
        norm_h = st.number_input("Standard Hours (Mon-Sat < 11pm):", value=st.session_state.woolies_pay_norm_h, step=0.5)
    with row1_col2:
        late_h = st.number_input("Late Night Hours (Mon-Sat > 11pm):", value=st.session_state.woolies_pay_late_h, step=0.5)
    with row2_col1:
        sun_h = st.number_input("Sunday Hours (All day):", value=st.session_state.woolies_pay_sun_h, step=0.5)
    with row2_col2:
        ph_h = st.number_input("Public Holiday Hours:", value=st.session_state.woolies_pay_ph_h, step=0.5)

    # Constants based on your payslip
    BASE_ORD = 26.9797
    CAS_LOAD = 6.7449
    SHIFT_25 = 6.7449
    SHIFT_50 = 13.4899
    LAUNDRY = 6.25
    NET_GOAL = 520.00

    # Hourly Rates (Gross)
    rate_std = BASE_ORD + CAS_LOAD + SHIFT_25  # $$40.84 (Standard)
    rate_pen = BASE_ORD + CAS_LOAD + SHIFT_50  # $$47.58 (Sunday/Late Night)
    rate_ph = BASE_ORD * 2.5                   # $$67.45 (Public Holiday)

    # Gross Calculations
    gross_std = norm_h * rate_std
    gross_pen = (late_h + sun_h) * rate_pen
    gross_ph = ph_h * rate_ph
    total_gross = gross_std + gross_pen + gross_ph
    
    # Net Calculations (Flat 28% Tax as requested)
    est_tax = total_gross * 0.28
    est_net = (total_gross - est_tax) + LAUNDRY
    total_hrs = norm_h + late_h + sun_h + ph_h

    # Save state
    st.session_state.woolies_pay_norm_h = norm_h
    st.session_state.woolies_pay_late_h = late_h
    st.session_state.woolies_pay_sun_h = sun_h
    st.session_state.woolies_pay_ph_h = ph_h
    
    save_state("woolies_pay", {
        "norm_h": norm_h,
        "late_h": late_h,
        "sun_h": sun_h,
        "ph_h": ph_h
    })

    # Display Metrics
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Net Pay", f"$${est_net:.2f}")
    m2.metric("Total Hours", f"{total_hrs} hrs")
    
    # Goal Tracker Delta
    goal_delta = est_net - NET_GOAL
    m3.metric("Goal Status", f"$${est_net:.2f}", delta=f"$${goal_delta:.2f} vs $$520")

    # Arsenal Themed Success/Warning
    if est_net >= NET_GOAL:
        st.success(f"🏆 Top of the Table! You've cleared the $$520 target by $${goal_delta:.2f}.")
    else:
        st.warning(f"⚠️ Needs a Late Goal! You are $${abs(goal_delta):.2f} short of your $$520 target.")
