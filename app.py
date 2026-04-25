import streamlit as st
from datetime import datetime, timedelta
import os, time
import pickle

os.environ['TZ'] = 'Australia/Sydney'
time.tzset()

# --- CONFIG ---
st.set_page_config(page_title="Personal Dashboard", layout="wide", page_icon="📊")

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
    st.session_state.ai_tokens_value = ai_state.get("value", 2368000)

if "personal_budget_spent" not in st.session_state:
    pb_state = load_state("personal_budget")
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
st.title("📊 Personal Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "🛒 Woolies Pay"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("AI Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    remaining_tokens = st.number_input("Tokens Remaining (from App):", value=st.session_state.ai_tokens_value, step=1000, format="%i")
    
    st.session_state.ai_tokens_value = remaining_tokens
    save_state("ai_tokens", {"value": remaining_tokens})

    used_to_date = MONTHLY_LIMIT - remaining_tokens
    avg_spent_daily = used_to_date / days_passed_monthly
    daily_allowance_remaining = remaining_tokens / days_remaining_monthly
    projected_total = used_to_date + (avg_spent_daily * days_remaining_monthly)

    st.write(f"### Currently Used: {used_to_date:,}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_spent_daily):,} tokens")
    c2.metric("Daily Budget", f"{int(daily_allowance_remaining):,} tokens", delta=f"{int(daily_allowance_remaining - avg_spent_daily):,} vs avg")
    c3.metric("Projected Total", f"{int(projected_total):,} / 3,000,000")

    if projected_total > MONTHLY_LIMIT:
        st.error(f"⚠️ Over Limit: Projected to exceed by {int(projected_total - MONTHLY_LIMIT):,} tokens.")
    else:
        st.success(f"✅ On Track: Buffer of {int(MONTHLY_LIMIT - projected_total):,} tokens remaining.")

# --- TAB 2: PERSONAL WEEKLY BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts **Thursday**.")
    
    st.metric("Weekly Budget", "$630.00")
    
    spent_to_date = st.number_input("Total Spent so far (including today):", value=st.session_state.personal_budget_spent, step=1.0)
    adjusted_amount = st.number_input("Adjusted Amount (AUD):", value=st.session_state.personal_budget_adjusted, step=1.0)
    today_is_over = st.checkbox("Today is over (count as completed day)", value=st.session_state.personal_budget_today_is_over)
    
    current_weekday = NOW.weekday() 
    days_since_thurs = (current_weekday - 3) % 7

    if current_weekday == 2:  # Wednesday
        days_left_weekly = 0 if today_is_over else 1
    else:
        days_left_weekly = (7 - (days_since_thurs + 1)) if today_is_over else (7 - days_since_thurs)
    
    weekly_limit = 630.0  
    remaining_funds = weekly_limit - spent_to_date + adjusted_amount
    net_spent = spent_to_date - adjusted_amount

    if days_left_weekly > 0:
        daily_allowance_weekly = remaining_funds / days_left_weekly
    else:
        daily_allowance_weekly = remaining_funds

    st.session_state.personal_budget_spent = spent_to_date
    st.session_state.personal_budget_adjusted = adjusted_amount
    st.session_state.personal_budget_today_is_over = today_is_over
    
    save_state("personal_budget", {
        "spent_to_date": spent_to_date,
        "adjusted_amount": adjusted_amount,
        "today_is_over": today_is_over
    })

    st.divider()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Remaining Budget", f"${remaining_funds:.2f}")
    
    if days_left_weekly > 0:
        col_b.metric("Allowed Daily Spend", f"${daily_allowance_weekly:.2f}")
    else:
        col_b.metric("Allowed Daily Spend", "Last Day")

    col_c.metric("Net Spent", f"${net_spent:.2f}")

# --- TAB 3: WOOLWORTHS PAY CALCULATOR ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    st.info("Rates include Casual Loading and Shift Penalties. Tax @28%")

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

    BASE_ORD, CAS_LOAD, SHIFT_25, SHIFT_50, LAUNDRY, NET_GOAL = 26.9797, 6.7449, 6.7449, 13.4899, 6.25, 520.00
    rate_std = BASE_ORD + CAS_LOAD + SHIFT_25
    rate_pen = BASE_ORD + CAS_LOAD + SHIFT_50
    rate_ph = BASE_ORD * 2.5

    total_gross = (norm_h * rate_std) + ((late_h + sun_h) * rate_pen) + (ph_h * rate_ph)
    est_tax = total_gross * 0.28
    est_net = (total_gross - est_tax) + LAUNDRY

    st.session_state.woolies_pay_norm_h, st.session_state.woolies_pay_late_h = norm_h, late_h
    st.session_state.woolies_pay_sun_h, st.session_state.woolies_pay_ph_h = sun_h, ph_h
    save_state("woolies_pay", {"norm_h": norm_h, "late_h": late_h, "sun_h": sun_h, "ph_h": ph_h})

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Net Pay", f"${est_net:.2f}")
    m2.metric("Total Hours", f"{norm_h + late_h + sun_h + ph_h} hrs")
    goal_delta = est_net - NET_GOAL
    m3.metric("Goal Status", f"${est_net:.2f}", delta=f"${goal_delta:.2f} vs $520")
