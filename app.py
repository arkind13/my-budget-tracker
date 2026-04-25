import streamlit as st
from datetime import datetime, timedelta
import os, time
import pickle

os.environ['TZ'] = 'Australia/Sydney'
time.tzset()

# --- CONFIG ---
st.set_page_config(page_title="Gunners Budget Tracker", layout="wide", page_icon="🔴")

# --- ARSENAL DATA ---
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
    start = ref.replace(day=RESET_DAY, hour=RESET_HOUR, minute=RESET_MIN,
                        second=0, microsecond=0)
    if ref < start:
        prev = (start.replace(day=1) - timedelta(days=1))
        start = prev.replace(day=RESET_DAY, hour=RESET_HOUR, minute=RESET_MIN,
                            second=0, microsecond=0)
    m = (start.month % 12) + 1
    y = start.year + (1 if m == 1 else 0)
    end = start.replace(year=y, month=m)
    return start, end

start_date, end_date = cycle_dates(NOW)
days_passed_monthly = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- PERSISTENCE FUNCTIONS ---
def save_state(tab_key, data):
    try:
        with open(f"{tab_key}_state.pkl", "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        st.error(f"Error saving state: {e}")

def load_state(tab_key):
    try:
        with open(f"{tab_key}_state.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        st.error(f"Error loading state: {e}")
        return {}

# Initialize session state
if "ai_tokens_value" not in st.session_state:
    ai_state = load_state("ai_tokens")
    st.session_state.ai_tokens_value = ai_state.get("value", 2368000) # Default high since it's remaining

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
st.title("🔴 Gunners Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "⚽ Arsenal FC", "🛒 Woolies Pay"])

# --- TAB 1: AI FIESTA TOKENS (UPDATED LOGIC) ---
with tab1:
    st.header("AI Fiesta Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    # Input is now REMAINING tokens
    remaining_tokens = st.number_input("Tokens Remaining (from App):", value=st.session_state.ai_tokens_value, step=1000, format="%i")
    
    # Derived Logic
    used_to_date = MONTHLY_LIMIT - remaining_tokens
    avg_spent_daily = used_to_date / days_passed_monthly
    daily_allowance_remaining = remaining_tokens / days_remaining_monthly
    projected_total = used_to_date + (avg_spent_daily * days_remaining_monthly)

    # Save state
    st.session_state.ai_tokens_value = remaining_tokens
    save_state("ai_tokens", {"value": remaining_tokens})
    
    st.write(f"### Currently Used: {used_to_date:,}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_spent_daily):,} tokens")
    c2.metric("Daily Budget", f"{int(daily_allowance_remaining):,} tokens", delta=f"{int(daily_allowance_remaining - avg_spent_daily):,} vs avg")
    c3.metric("Projected Total", f"{int(projected_total):,} / 3,000,000")

    if projected_total > MONTHLY_LIMIT:
        st.error(f"⚠️ We're losing the lead! Projected to exceed by {int(projected_total - MONTHLY_LIMIT):,} tokens.")
    else:
        st.success(f"✅ Clean sheet! Buffer of {int(MONTHLY_LIMIT - projected_total):,} tokens remaining.")

# --- TAB 2: PERSONAL WEEKLY BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts **Thursday**.")
    st.metric("Weekly Budget", "$630.00")
    
    spent_to_date = st.number_input("Total Spent so far (including today):", value=st.session_state.personal_budget_spent, step=1.0)
    adjusted_amount = st.number_input("Adjusted Amount (AUD):", value=st.session_state.personal_budget
