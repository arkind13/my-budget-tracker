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

# --- CONFIGURATION ---
ELEC_SHEET_URL = "https://docs.google.com/spreadsheets/d/10szrS6fabDdK19pfCCiedhRnueXTC9cS_Cfx8JACuSE/edit?gid=1978947189#gid=1978947189"

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
    st.success("Connected: Electricity Bills")
    st.success("Connected: Gas Bills")

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
    st.caption(f"Cycle: {start_date.strftime('%d %b')} → {end_date.strftime('%d %b')}")
    
    tokens_rem = st.number_input("Tokens Remaining (from App):", 
                                 value=st.session_state.ai_tokens_value, 
                                 step=1000, key="ai_in", on_change=sync_to_cloud)
    
    used_to_date = MONTHLY_LIMIT - tokens_rem
    avg_daily = used_to_date / days_passed
    daily_budget = tokens_rem / days_remaining_monthly
    projected = used_to_date + (avg_daily * days_remaining_monthly)

    st.write(f"### Currently Used: {used_to_date:,}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Daily Spent", f"{int(avg_daily):,} tokens")
    c2.metric("Daily Budget", f"{int(daily_budget):,} tokens", delta=f"{int(daily_budget - avg_daily):,} vs avg")
    c3.metric("Projected Total", f"{int(projected):,} / 3.0M")

    if projected > MONTHLY_LIMIT:
        st.error(f"⚠️ Over Limit: Projected to exceed by {int(projected - MONTHLY_LIMIT):,} tokens.")
    else:
        st.success(f"✅ On Track: Buffer of {int(MONTHLY_LIMIT - projected):,} tokens.")

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts **Thursday**.")
    
    st.metric("Weekly Budget", "$630.00")
    
    spent = st.number_input("Total Spent so far (including today):", 
                           value=st.session_state.pb_spent_val, 
                           step=1.0, key="pb_spent", on_change=sync_to_cloud)
    adj = st.number_input("Adjusted Amount (AUD):", 
                         value=st.session_state.pb_adj_val, 
                         step=1.0, key="pb_adj", on_change=sync_to_cloud)
    
    today_is_over = st.checkbox("Today is over (count as completed day)", value=False)
    
    current_weekday = NOW.weekday() 
    days_since_thurs = (current_weekday - 3) % 7

    if current_weekday == 2:  # Wednesday
        days_left_weekly = 0 if today_is_over else 1
    else:
        days_left_weekly = (7 - (days_since_thurs + 1)) if today_is_over else (7 - days_since_thurs)
    
    weekly_limit = 630.0  
    remaining_funds = weekly_limit - spent + adj
    net_spent = spent - adj
    daily_allowance_weekly = remaining_funds / max(days_left_weekly, 1)

    st.divider()
    col_a, col_b, col_c = st.columns(3)
    
    # Show days remaining in small font under budget
    col_a.metric("Remaining Budget", f"${remaining_funds:.2f}")
    col_a.caption(f"🗓️ {days_left_weekly} days remaining")
    
    if days_left_weekly > 0:
        col_b.metric("Allowed Daily Spend", f"${daily_allowance_weekly:.2f}")
    else:
        col_b.metric("Allowed Daily Spend", "Last Day")

    col_c.metric("Net Spent", f"${net_spent:.2f}")

# --- TAB 3: WOOLIES PAY ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    st.info("Rates include Casual Loading and Shift Penalties. Tax @28%")

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        n_h = st.number_input("Standard Hours:", value=st.session_state.w_n_val, step=0.5, key="w_n", on_change=sync_to_cloud)
    with row1_col2:
        l_h = st.number_input("Late Night Hours:", value=st.session_state.w_l_val, step=0.5, key="w_l", on_change=sync_to_cloud)
    with row2_col1:
        s_h = st.number_input("Sunday Hours:", value=st.session_state.w_s_val, step=0.5, key="w_s", on_change=sync_to_cloud)
    with row2_col2:
        p_h = st.number_input("Public Holiday Hours:", value=st.session_state.w_p_val, step=0.5, key="w_p", on_change=sync_to_cloud)

    BASE_ORD, CAS_LOAD, SHIFT_25, SHIFT_50, LAUNDRY, NET_GOAL = 26.9797, 6.7449, 6.7449, 13.4899, 6.25, 520.00
    rate_std = BASE_ORD + CAS_LOAD + SHIFT_25
    rate_pen = BASE_ORD + CAS_LOAD + SHIFT_50
    rate_ph = BASE_ORD * 2.5

    total_gross = (n_h * rate_std) + ((l_h + s_h) * rate_pen) + (p_h * rate_ph)
    est_net = (total_gross * 0.72) + LAUNDRY

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Net Pay", f"${est_net:.2f}")
    m2.metric("Total Hours", f"{n_h + l_h + s_h + p_h} hrs")
    
    # Goal status with dynamic coloring (Positive = Green, Negative = Red)
    goal_delta = est_net - NET_GOAL
    m3.metric("Goal Status", f"${goal_delta:.2f}", delta=f"${goal_delta:.2f} vs $520", delta_color="normal")

# --- TAB 4: UTILITY TRACKER ---
with tab4:
    # --- ELECTRICITY SECTION ---
    st.header("⚡ Electricity Analysis")
    try:
        df_e_raw = conn.read(spreadsheet=ELEC_SHEET_URL, worksheet="Sheet1", ttl=0)
        # Columns: E(3), F(4), H(6), K(9), N(12)
        df_e = df_e_raw.iloc[:, [3, 4, 6, 9, 12]].copy()
        df_e.columns = ["Date", "Billing Days", "Usage Per Day", "Net Amount", "Amount Per Day"]
        df_e["Date"] = pd.to_datetime(df_e["Date"], errors='coerce', dayfirst=True)
        for col in ["Billing Days", "Usage Per Day", "Net Amount", "Amount Per Day"]:
            df_e[col] = pd.to_numeric(df_e[col], errors='coerce')
        
        df_e_clean = df_e.dropna(subset=["Date", "Usage Per Day"]).sort_values("Date").tail(10)

        if not df_e_clean.empty:
            fig_e = make_subplots(specs=[[{"secondary_y": True}]])
            fig_e.add_trace(go.Scatter(x=df_e_clean["Date"], y=df_e_clean["Usage Per Day"], name="Usage (kWh/Day)", line=dict(color='royalblue', width=4)), secondary_y=False)
            fig_e.add_trace(go.Scatter(x=df_e_clean["Date"], y=df_e_clean["Amount Per Day"], name="Cost ($/Day)", line=dict(color='firebrick', width=4, dash='dot')), secondary_y=True)
            fig_e.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.15), margin=dict(t=30))
            fig_e.update_yaxes(title_text="Usage (kWh)", secondary_y=False, color="royalblue")
            fig_e.update_yaxes(title_text="Cost ($)", secondary_y=True, color="firebrick")
            st.plotly_chart(fig_e, use_container_width=True)
        
        with st.expander("🔍 Electricity Data Table"):
            df_e_table = df_e_clean.sort_values("Date", ascending=False).copy()
            df_e_table["Date"] = df_e_table["Date"].dt.date
            st.dataframe(df_e_table, use_container_width=True)
    except Exception as e:
        st.error(f"Elec Error: {e}")

    st.divider()

    # --- GAS SECTION ---
    st.header("🔥 Gas Analysis")
    try:
        df_g_raw = conn.read(spreadsheet=ELEC_SHEET_URL, worksheet="Gas", ttl=0)
        df_g = df_g_raw.iloc[:, [3, 4, 6, 9, 12]].copy()
        df_g.columns = ["Date", "Billing Days", "Usage Per Day", "Net Amount", "Amount Per Day"]
        df_g["Date"] = pd.to_datetime(df_g["Date"], errors='coerce', dayfirst=True)
        for col in ["Billing Days", "Usage Per Day", "Net Amount", "Amount Per Day"]:
            df_g[col] = pd.to_numeric(df_g[col], errors='coerce')
        
        df_g_clean = df_g.dropna(subset=["Date", "Usage Per Day"]).sort_values("Date").tail(10)

        if not df_g_clean.empty:
            fig_g = make_subplots(specs=[[{"secondary_y": True}]])
            fig_g.add_trace(go.Scatter(x=df_g_clean["Date"], y=df_g_clean["Usage Per Day"], name="Usage (MJ/Day)", line=dict(color='orange', width=4)), secondary_y=False)
            fig_g.add_trace(go.Scatter(x=df_g_clean["Date"], y=df_g_clean["Amount Per Day"], name="Cost ($/Day)", line=dict(color='darkred', width=4, dash='dot')), secondary_y=True)
            fig_g.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.15), margin=dict(t=30))
            fig_g.update_yaxes(title_text="Usage (MJ)", secondary_y=False, color="orange")
            fig_g.update_yaxes(title_text="Cost ($)", secondary_y=True, color="darkred")
            st.plotly_chart(fig_g, use_container_width=True)
        
        with st.expander("🔍 Gas Data Table"):
            df_g_table = df_g_clean.sort_values("Date", ascending=False).copy()
            df_g_table["Date"] = df_g_table["Date"].dt.date
            st.dataframe(df_g_table, use_container_width=True)
    except Exception as e:
        st.error(f"Gas Error: {e}")
