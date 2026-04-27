import streamlit as st
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os, time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- TIMEZONE CONFIG ---
os.environ['TZ'] = 'Australia/Sydney'
try:
    time.tzset()
except AttributeError:
    pass

st.set_page_config(page_title="Personal Dashboard", layout="wide", page_icon="📊")

# --- GOOGLE SHEETS CONNECTIONS ---
# Connection 1: Personal Dashboard (Defined in secrets)
conn_main = st.connection("gsheets", type=GSheetsConnection)

# Connection 2: Electricity Bills (Using the direct URL)
# Replace 'YOUR_SHEET_URL_HERE' with the actual URL of your Electricity Bills Google Sheet
ELEC_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_URL_HERE/edit#gid=0"

def load_gsheet_data():
    """Fetch data from the 'Personal Dashboard' sheet."""
    try:
        df = conn_main.read(worksheet="Sheet1", ttl=0) 
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
    """Pushes current UI values to Google Sheets."""
    try:
        updates_dict = {
            "AI Remaining Token": st.session_state.ai_in,
            "Total Spent So Far": st.session_state.pb_spent,
            "Adjusted Amount": st.session_state.pb_adj,
            "Standard Hours": st.session_state.w_n,
            "Sunday Hours": st.session_state.w_s,
            "Late Night Hours": st.session_state.w_l,
            "Public Holiday Hours": st.session_state.w_p
        }
        df = pd.DataFrame([updates_dict])
        conn_main.update(worksheet="Sheet1", data=df)
        st.toast("✅ Cloud Synced!")
    except Exception as e:
        st.error(f"Sync failed: {e}")

# --- INITIALIZE SESSION STATE ---
if "initialized" not in st.session_state:
    gs_data = load_gsheet_data()
    st.session_state.ai_tokens_value = int(gs_data.get("AI Remaining Token", 2368000))
    st.session_state.pb_spent_val = float(gs_data.get("Total Spent So Far", 180.0))
    st.session_state.pb_adj_val = float(gs_data.get("Adjusted Amount", 0.0))
    st.session_state.w_n_val = float(gs_data.get("Standard Hours", 17.5))
    st.session_state.w_s_val = float(gs_data.get("Sunday Hours", 5.5))
    st.session_state.w_l_val = float(gs_data.get("Late Night Hours", 1.5))
    st.session_state.w_p_val = float(gs_data.get("Public Holiday Hours", 0.0))
    st.session_state.initialized = True

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔄 Connection")
    if st.button("Manual Refresh"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.success("Connected: Personal Dashboard")
    st.success("Connected: Utility Tracker")

# --- DATE CALCULATIONS (AI Tab) ---
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
days_passed = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- APP INTERFACE ---
st.title("📊 Personal Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "🛒 Woolies Pay", "⚡ Utilities"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("AI Token Cycle")
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    tokens_rem = st.number_input("Tokens Remaining (from App):", value=st.session_state.ai_tokens_value, step=1000, key="ai_in", on_change=sync_to_cloud)
    
    used_to_date = MONTHLY_LIMIT - tokens_rem
    avg_daily = used_to_date / days_passed
    daily_budget = tokens_rem / days_remaining_monthly
    projected = used_to_date + (avg_daily * days_remaining_monthly)

    st.write(f"### Currently Used: {used_to_date:,}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_daily):,} tokens")
    c2.metric("Daily Budget", f"{int(daily_budget):,} tokens", delta=f"{int(daily_budget - avg_daily):,} vs avg")
    c3.metric("Projected Total", f"{int(projected):,} / 3.0M")

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    spent = st.number_input("Total Spent so far:", value=st.session_state.pb_spent_val, step=1.0, key="pb_spent", on_change=sync_to_cloud)
    adj = st.number_input("Adjusted Amount (AUD):", value=st.session_state.pb_adj_val, step=1.0, key="pb_adj", on_change=sync_to_cloud)
    
    current_weekday = NOW.weekday() 
    days_since_thurs = (current_weekday - 3) % 7
    days_left_weekly = (7 - days_since_thurs)
    
    remaining_funds = 630.0 - spent + adj
    daily_allowance = remaining_funds / max(days_left_weekly, 1)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Remaining Budget", f"${remaining_funds:.2f}")
    col_b.metric("Allowed Daily Spend", f"${daily_allowance:.2f}")
    col_c.metric("Net Spent", f"${spent - adj:.2f}")

# --- TAB 3: WOOLIES PAY ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    n_h = st.number_input("Standard Hours:", value=st.session_state.w_n_val, step=0.5, key="w_n", on_change=sync_to_cloud)
    l_h = st.number_input("Late Night Hours:", value=st.session_state.w_l_val, step=0.5, key="w_l", on_change=sync_to_cloud)
    s_h = st.number_input("Sunday Hours:", value=st.session_state.w_s_val, step=0.5, key="w_s", on_change=sync_to_cloud)
    p_h = st.number_input("Public Holiday Hours:", value=st.session_state.w_p_val, step=0.5, key="w_p", on_change=sync_to_cloud)

    BASE_ORD, CAS_LOAD, SHIFT_25, SHIFT_50, LAUNDRY = 26.9797, 6.7449, 6.7449, 13.4899, 6.25
    total_gross = (n_h * (BASE_ORD+CAS_LOAD+SHIFT_25)) + ((l_h + s_h) * (BASE_ORD+CAS_LOAD+SHIFT_50)) + (p_h * (BASE_ORD*2.5))
    est_net = (total_gross * 0.72) + LAUNDRY

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Net Pay", f"${est_net:.2f}")
    m2.metric("Total Hours", f"{n_h + l_h + s_h + p_h} hrs")
    m3.metric("Goal Status", f"${est_net - 520:.2f}", delta=f"${est_net - 520:.2f}")

# --- TAB 4: UTILITIES ---
with tab4:
    st.header("⚡ Electricity Bill Analysis")
    
    try:
        # Fetching data from the separate "Electricity Bills" file
        df_elec_raw = conn_main.read(spreadsheet=ELEC_SHEET_URL, worksheet="Sheet1", ttl=0)
        
        # Selecting specific columns: E (4), F (5), H (7), N (13) - Indexing starts at 0
        # Columns: End Date, No. of Days, Usage/Day, Amt/Day
        df_elec = df_elec_raw.iloc[:, [4, 5, 7, 13]].copy()
        df_elec.columns = ["End Date", "Billing Days", "Usage Per Day", "Amount Per Day"]
        
        # Convert Date and grab last 10
        df_elec["End Date"] = pd.to_datetime(df_elec["End Date"])
        df_elec = df_elec.sort_values("End Date").tail(10)

        # Plotly Figure with Secondary Y-Axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Bar Chart: Billing Days (Secondary Axis)
        fig.add_trace(
            go.Bar(x=df_elec["End Date"], y=df_elec["Billing Days"], name="Days in Bill", 
                   marker_color='rgba(200, 200, 200, 0.3)'),
            secondary_y=True,
        )

        # Line Chart: Usage Per Day
        fig.add_trace(
            go.Scatter(x=df_elec["End Date"], y=df_elec["Usage Per Day"], name="Usage (kWh/Day)", 
                       line=dict(color='royalblue', width=4)),
            secondary_y=False,
        )

        # Line Chart: Amount Per Day
        fig.add_trace(
            go.Scatter(x=df_elec["End Date"], y=df_elec["Amount Per Day"], name="Cost ($/Day)", 
                       line=dict(color='firebrick', width=4, dash='dot')),
            secondary_y=False,
        )

        fig.update_layout(title_text="Last 10 Electricity Bills (Daily Averages)", hovermode="x unified")
        fig.update_yaxes(title_text="<b>Usage / Cost</b>", secondary_y=False)
        fig.update_yaxes(title_text="<b>Days in Cycle</b>", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("View Raw Data"):
            st.dataframe(df_elec)

    except Exception as e:
        st.error(f"Could not load Electricity data. Check URL and Sheet Permissions. Error: {e}")
