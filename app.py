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
conn = st.connection("gsheets", type=GSheetsConnection)

# URL for the separate Electricity Bills file
ELEC_SHEET_URL = "https://docs.google.com/spreadsheets/d/10szrS6fabDdK19pfCCiedhRnueXTC9cS_Cfx8JACuSE/edit?gid=1988111189#gid=1988111189"

def load_gsheet_data():
    """Fetch data from the 'Personal Dashboard' sheet."""
    try:
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
        conn.update(worksheet="Sheet1", data=df)
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
days_passed = max((NOW - start_date).days, 1)
days_remaining_monthly = max((end_date - NOW).days, 1)

# --- APP INTERFACE ---
st.title("📊 Personal Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "🛒 Woolies Pay", "⚡ Utility Tracker"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("AI Token Cycle")
    tokens_rem = st.number_input("Tokens Remaining:", value=st.session_state.ai_tokens_value, step=1000, key="ai_in", on_change=sync_to_cloud)
    used_to_date = MONTHLY_LIMIT - tokens_rem
    avg_daily = used_to_date / days_passed
    daily_budget = tokens_rem / days_remaining_monthly
    projected = used_to_date + (avg_daily * days_remaining_monthly)
    
    st.write(f"### Currently Used: {used_to_date:,}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_daily):,}")
    c2.metric("Daily Budget", f"{int(daily_budget):,}")
    c3.metric("Projected Total", f"{int(projected):,}")

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    spent = st.number_input("Total Spent:", value=st.session_state.pb_spent_val, step=1.0, key="pb_spent", on_change=sync_to_cloud)
    adj = st.number_input("Adjusted Amount:", value=st.session_state.pb_adj_val, step=1.0, key="pb_adj", on_change=sync_to_cloud)
    
    current_weekday = NOW.weekday() 
    days_since_thurs = (current_weekday - 3) % 7
    days_left = 7 - days_since_thurs
    
    rem = 630.0 - spent + adj
    st.metric("Remaining Budget", f"${rem:.2f}")
    st.caption(f"{days_left} days remaining")

# --- TAB 3: WOOLIES PAY ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    n_h = st.number_input("Standard Hours:", value=st.session_state.w_n_val, step=0.5, key="w_n", on_change=sync_to_cloud)
    l_h = st.number_input("Late Night Hours:", value=st.session_state.w_l_val, step=0.5, key="w_l", on_change=sync_to_cloud)
    s_h = st.number_input("Sunday Hours:", value=st.session_state.w_s_val, step=0.5, key="w_s", on_change=sync_to_cloud)
    p_h = st.number_input("Public Holiday Hours:", value=st.session_state.w_p_val, step=0.5, key="w_p", on_change=sync_to_cloud)

    total_gross = (n_h * 33.72) + ((l_h + s_h) * 40.46) + (p_h * 67.45) # Simplified Rates
    est_net = (total_gross * 0.72) + 6.25
    st.metric("Estimated Net Pay", f"${est_net:.2f}")

# --- TAB 4: UTILITY TRACKER ---
with tab4:
    st.header("⚡ Electricity Usage & Cost")
    try:
        # Fetching from the second spreadsheet
        df_raw = conn.read(spreadsheet=ELEC_SHEET_URL, worksheet="Sheet1", ttl=0)
        
        # Columns: E(4)=End Date, F(5)=Days, H(7)=Usage/Day, N(13)=Amt/Day
        df_plot = df_raw.iloc[:, [4, 5, 7, 13]].copy()
        df_plot.columns = ["Date", "Days", "Usage", "Amount"]
        
        # Data Cleaning
        df_plot["Date"] = pd.to_datetime(df_plot["Date"])
        df_plot = df_plot.sort_values("Date").tail(10)

        # Plotly Multi-axis Chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Bar: Billing Cycle Days
        fig.add_trace(go.Bar(x=df_plot["Date"], y=df_plot["Days"], name="Days in Bill", marker_color='lightgrey', opacity=0.5), secondary_y=True)
        
        # Line: Usage
        fig.add_trace(go.Scatter(x=df_plot["Date"], y=df_plot["Usage"], name="Usage (kWh/Day)", line=dict(color='blue', width=3)), secondary_y=False)
        
        # Line: Amount
        fig.add_trace(go.Scatter(x=df_plot["Date"], y=df_plot["Amount"], name="Cost ($/Day)", line=dict(color='red', width=3, dash='dot')), secondary_y=False)

        fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning("Connect your Electricity sheet by pasting the URL in the code.")
        st.error(f"Error: {e}")
