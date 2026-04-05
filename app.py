import streamlit as st
from datetime import datetime, timedelta
import os, time

# --- TIMEZONE CONFIG ---
os.environ['TZ'] = 'Australia/Sydney'
try:
    time.tzset()
except AttributeError:
    pass # tzset is Unix-only; logic below uses NOW for safety

# --- CONFIG ---
st.set_page_config(page_title="Gunners Budget Tracker", layout="wide", page_icon="🔴")
NOW = datetime.now()

# --- RESET & PERSISTENCE LOGIC ---
def handle_resets():
    """Checks if reset conditions are met and clears/updates session state."""
    
    # 1. AI Tokens Reset (Monthly cycle reset)
    # We use your existing cycle_dates logic. If NOW is the start of a new cycle, reset.
    start_date, _ = cycle_dates(NOW)
    if "last_ai_cycle_start" not in st.session_state:
        st.session_state.last_ai_cycle_start = start_date
    
    if start_date > st.session_state.last_ai_cycle_start:
        st.session_state.tokens_used = 0
        st.session_state.last_ai_cycle_start = start_date

    # 2. Personal Budget Reset (Thursday)
    # If today is Thursday and we haven't reset today yet
    today_date = NOW.strftime('%Y-%m-%d')
    if NOW.weekday() == 3: # Thursday
        if st.session_state.get("last_budget_reset") != today_date:
            st.session_state.spent_to_date = 0.0
            st.session_state.adjusted_amount = 0.0
            st.session_state.last_budget_reset = today_date

    # 3. Woolies Pay Reset (Monday)
    if NOW.weekday() == 0: # Monday
        if st.session_state.get("last_woolies_reset") != today_date:
            st.session_state.norm_h = 0.0
            st.session_state.late_h = 0.0
            st.session_state.sun_h = 0.0
            st.session_state.ph_h = 0.0
            st.session_state.last_woolies_reset = today_date

# Initialize Session States with your default values if they don't exist
if "tokens_used" not in st.session_state: st.session_state.tokens_used = 632000
if "spent_to_date" not in st.session_state: st.session_state.spent_to_date = 180.0
if "adjusted_amount" not in st.session_state: st.session_state.adjusted_amount = 0.0
if "norm_h" not in st.session_state: st.session_state.norm_h = 17.5
if "late_h" not in st.session_state: st.session_state.late_h = 1.5
if "sun_h" not in st.session_state: st.session_state.sun_h = 5.5
if "ph_h" not in st.session_state: st.session_state.ph_h = 0.0

# --- ARSENAL DATA ---
LAST_MATCH_TXT = "Arsenal 3 - 0 Sunderland (Premier League)"
NEXT_OPPONENT = "Brentford (A) 7th"
NEXT_KICKOFF = "07:00 AM, Fri 13 Feb (SYD)"
PL_TABLE = {
    "Pos": [1, 2, 3, 4],
    "Team": ["Arsenal", "Man City", "Aston Villa", "Man Utd"],
    "Pts": [56, 47, 47, 44]
}

# --- DATE CALCULATIONS ---
RESET_DAY, RESET_HOUR, RESET_MIN = 25, 17, 20
def cycle_dates(ref):
    start = ref.replace(day=RESET_DAY, hour=RESET_HOUR, minute=RESET_MIN, second=0, microsecond=0)
    if ref < start:
        prev = (start.replace(day=1) - timedelta(days=1))
        start = prev.replace(day=RESET_DAY, hour=RESET_HOUR, minute=RESET_MIN, second=0, microsecond=0)
    m = (start.month % 12) + 1
    y = start.year + (1 if m == 1 else 0)
    end = start.replace(year=y, month=m)
    return start, end

# Run reset check
handle_resets()
start_date, end_date = cycle_dates(NOW)
days_passed_monthly = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)
MONTHLY_LIMIT = 3000000

# --- APP INTERFACE ---
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC", "🛒 Woolies Pay"])

with tab1:
    st.header("AI Fiesta Token Cycle")
    # Use session_state in the widget
    st.session_state.tokens_used = st.number_input("Tokens Used to Date:", value=st.session_state.tokens_used, step=1000, format="%i")
    
    current_tokens = st.session_state.tokens_used
    avg_spent_daily = current_tokens / days_passed_monthly
    remaining_tokens = MONTHLY_LIMIT - current_tokens
    daily_allowance_remaining = remaining_tokens / days_remaining_monthly
    projected_total = current_tokens + (avg_spent_daily * days_remaining_monthly)

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_spent_daily):,} tokens")
    c2.metric("Daily Goal", f"{int(daily_allowance_remaining):,} tokens")
    c3.metric("Projected Monthly", f"{int(projected_total):,} / 3,000,000")

with tab2:
    st.header("Weekly Budget Tracker")
    weekly_limit = 630.0 # Fixed as per your request
    st.write(f"### Weekly Budget: ${weekly_limit}")
    
    st.session_state.spent_to_date = st.number_input("Total Spent so far:", value=st.session_state.spent_to_date, step=1.0)
    st.session_state.adjusted_amount = st.number_input("Adjusted Amount (AUD):", value=st.session_state.adjusted_amount, step=1.0)
    
    today_is_over = st.checkbox("Today is over")
    current_weekday = NOW.weekday() 
    days_since_thurs = (current_weekday - 3) % 7
    days_left_weekly = (7 - (days_since_thurs + 1)) if today_is_over else (7 - days_since_thurs)

    remaining_funds = weekly_limit - st.session_state.spent_to_date + st.session_state.adjusted_amount
    st.metric("Remaining Budget", f"${remaining_funds:.2f}")

with tab4:
    st.header("🛒 Woolies Pay Calculator")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.norm_h = st.number_input("Standard Hours:", value=st.session_state.norm_h, step=0.5)
        st.session_state.late_h = st.number_input("Late Night Hours:", value=st.session_state.late_h, step=0.5)
    with col2:
        st.session_state.sun_h = st.number_input("Sunday Hours:", value=st.session_state.sun_h, step=0.5)
        st.session_state.ph_h = st.number_input("Public Holiday Hours:", value=st.session_state.ph_h, step=0.5)

    # (Keep your existing math logic here using st.session_state values)
    st.write(f"Total Hours tracked: {st.session_state.norm_h + st.session_state.late_h + st.session_state.sun_h + st.session_state.ph_h}")
