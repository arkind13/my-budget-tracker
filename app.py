import streamlit as st
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os, time

# Set timezone to Sydney
os.environ['TZ'] = 'Australia/Sydney'
try:
    time.tzset()
except AttributeError:
    pass

# --- CONFIG ---
st.set_page_config(page_title="Personal Dashboard", layout="wide", page_icon="📊")

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_gsheet_data():
    """Fetch data from the 'Personal Dashboard' sheet."""
    try:
        # ttl=0 ensures we fetch the latest data from the sheet
        df = conn.read(worksheet="Sheet1", ttl=0) 
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")
    
    return {
        "AI Remaining Token": 2368000,
        "Total Spent So Far": 180.0,
        "Adjusted Amount": 0.0,
        "Standard Hours": 17.5,
        "Sunday Hours": 5.5,
        "Late Night Hours": 1.5,
        "Public Holiday Hours": 0.0
    }

def sync_to_cloud():
    """Write all current dashboard values back to the Google Sheet."""
    updates_dict = {
        "AI Remaining Token": st.session_state.ai_tokens_value,
        "Total Spent So Far": st.session_state.personal_budget_spent,
        "Adjusted Amount": st.session_state.personal_budget_adjusted,
        "Standard Hours": st.session_state.woolies_pay_norm_h,
        "Sunday Hours": st.session_state.woolies_pay_sun_h,
        "Late Night Hours": st.session_state.woolies_pay_late_h,
        "Public Holiday Hours": st.session_state.woolies_pay_ph_h
    }
    df = pd.DataFrame([updates_dict])
    conn.update(worksheet="Sheet1", data=df)
    st.sidebar.success("Cloud Synced!")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🔄 Data Controls")
if st.sidebar.button("Test Connection / Refresh"):
    gs_data = load_gsheet_data()
    st.session_state.data_loaded = False # Force reload logic
    st.sidebar.write("Connection: ✅ Active")
    st.rerun()

# Initialize Session State
if "data_loaded" not in st.session_state or not st.session_state.data_loaded:
    gs_data = load_gsheet_data()
    st.session_state.ai_tokens_value = int(gs_data.get("AI Remaining Token", 2368000))
    st.session_state.personal_budget_spent = float(gs_data.get("Total Spent So Far", 180.0))
    st.session_state.personal_budget_adjusted = float(gs_data.get("Adjusted Amount", 0.0))
    st.session_state.woolies_pay_norm_h = float(gs_data.get("Standard Hours", 17.5))
    st.session_state.woolies_pay_sun_h = float(gs_data.get("Sunday Hours", 5.5))
    st.session_state.woolies_pay_late_h = float(gs_data.get("Late Night Hours", 1.5))
    st.session_state.woolies_pay_ph_h = float(gs_data.get("Public Holiday Hours", 0.0))
    st.session_state.data_loaded = True

# --- DATE CALCULATIONS ---
NOW = datetime.now()
MONTHLY_LIMIT = 3000000
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

start_date, end_date = cycle_dates(NOW)
days_passed_monthly = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- APP INTERFACE ---
st.title("📊 Personal Dashboard")
tab1, tab2, tab3 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "🛒 Woolies Pay"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("AI Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    val = st.number_input("Tokens Remaining:", 
                          value=st.session_state.ai_tokens_value, 
                          step=1000, 
                          key="ai_in", 
                          on_change=sync_to_cloud)
    st.session_state.ai_tokens_value = val

    used_to_date = MONTHLY_LIMIT - val
    avg_spent_daily = used_to_date / days_passed_monthly
    daily_allowance = val / days_remaining_monthly
    projected = used_to_date + (avg_spent_daily * days_remaining_monthly)

    st.write(f"### Currently Used: {used_to_date:,}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_spent_daily):,}")
    c2.metric("Daily Budget", f"{int(daily_allowance):,}")
    c3.metric("Projected Total", f"{int(projected):,}")

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts Thursday.")
    
    spent = st.number_input("Total Spent so far:", 
                           value=st.session_state.personal_budget_spent, 
                           step=1.0, 
                           key="pb_spent", 
                           on_change=sync_to_cloud)
    adj = st.number_input("Adjusted Amount (AUD):", 
                         value=st.session_state.personal_budget_adjusted, 
                         step=1.0, 
                         key="pb_adj", 
                         on_change=sync_to_cloud)
    
    st.session_state.personal_budget_spent = spent
    st.session_state.personal_budget_adjusted = adj

    days_since_thurs = (NOW.weekday() - 3) % 7
    days_left = 7 - days_since_thurs
    
    rem_funds = 630.0 - spent + adj
    daily_alloc = rem_funds / max(days_left, 1)

    st.divider()
    col_a, col_b = st.columns(2)
    col_a.metric("Remaining Budget", f"${rem_funds:.2f}")
    col_b.metric("Allowed Daily Spend", f"${daily_alloc:.2f}")

# --- TAB 3: WOOLIES PAY ---
with tab3:
    st.header("🛒 Woolies Pay")
    
    row1_1, row1_2 = st.columns(2)
    with row1_1:
        n_h = st.number_input("Standard Hours:", value=st.session_state.woolies_pay_norm_h, step=0.5, key="w_n", on_change=sync_to_cloud)
    with row1_2:
        l_h = st.number_input("Late Night Hours:", value=st.session_state.woolies_pay_late_h, step=0.5, key="w_l", on_change=sync_to_cloud)
    
    row2_1, row2_2 = st.columns(2)
    with row2_1:
        s_h = st.number_input("Sunday Hours:", value=st.session_state.woolies_pay_sun_h, step=0.5, key="w_s", on_change=sync_to_cloud)
    with row2_2:
        p_h = st.number_input("Public Holiday Hours:", value=st.session_state.woolies_pay_ph_h, step=0.5, key="w_p", on_change=sync_to_cloud)

    st.session_state.woolies_pay_norm_h, st.session_state.woolies_pay_late_h = n_h, l_h
    st.session_state.woolies_pay_sun_h, st.session_state.woolies_pay_ph_h = s_h, p_h

    # Pay Calculation Logic (Tax @28%)
    BASE_ORD, CAS_LOAD, SHIFT_25, SHIFT_50, LAUNDRY = 26.9797, 6.7449, 6.7449, 13.4899, 6.25
    total_gross = (n_h * (BASE_ORD + CAS_LOAD + SHIFT_25)) + \
                  ((l_h + s_h) * (BASE_ORD + CAS_LOAD + SHIFT_50)) + \
                  (p_h * (BASE_ORD * 2.5))
    est_net = (total_gross * 0.72) + LAUNDRY

    st.divider()
    st.metric("Estimated Net Pay", f"${est_net:.2f}", delta=f"${est_net - 520:.2f} vs Goal")
