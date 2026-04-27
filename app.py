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

# --- CONFIGURATION: PASTE YOUR FULL URL HERE ---
ELEC_SHEET_URL = "https://docs.google.com/spreadsheets/d/10szrS6fabDdK19pfCCiedhRnueXTC9cS_Cfx8JACuSE/edit?gid=1978947189#gid=1978947189"

def load_gsheet_data():
    """Fetch data from the 'Personal Dashboard' sheet (Main Connection)."""
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

# --- APP INTERFACE ---
st.title("📊 Personal Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 AI Tokens", "💰 Personal Budget", "🛒 Woolies Pay", "⚡ Utility Tracker"])

# --- TAB 1: AI TOKENS ---
with tab1:
    st.header("AI Token Cycle")
    tokens_rem = st.number_input("Tokens Remaining:", value=st.session_state.ai_tokens_value, step=1000, key="ai_in", on_change=sync_to_cloud)
    used = MONTHLY_LIMIT - tokens_rem
    st.metric("Currently Used", f"{used:,}")
    st.metric("Avg Daily Spent", f"{int(used / days_passed):,} tokens")

# --- TAB 2: PERSONAL BUDGET ---
with tab2:
    st.header("Weekly Budget Tracker")
    spent = st.number_input("Total Spent:", value=st.session_state.pb_spent_val, step=1.0, key="pb_spent", on_change=sync_to_cloud)
    st.metric("Remaining Budget", f"${630.0 - spent + st.session_state.pb_adj_val:.2f}")

# --- TAB 3: WOOLIES PAY ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    n_h = st.number_input("Standard Hours:", value=st.session_state.w_n_val, step=0.5, key="w_n", on_change=sync_to_cloud)
    st.info("Calculator synced with Woolies rates.")

# --- TAB 4: UTILITY TRACKER ---
with tab4:
    st.header("⚡ Electricity Usage & Cost")
    
    try:
        # Step 1: Read the full sheet (Sheet1)
        df_raw = conn.read(spreadsheet=ELEC_SHEET_URL, worksheet="Sheet1", ttl=0)
        
        # Step 2: Grab Columns based on user feedback of shifting
        # Since F(5) was taking G(6), we shift all indices back by 1
        # Target: E(index 3), F(index 4), H(index 6), N(index 12)
        df_working = df_raw.iloc[:, [3, 4, 6, 12]].copy()
        df_working.columns = ["Date", "Days", "Usage", "Amount"]
        
        # Step 3: Advanced Date Parsing
        # dayfirst=True handles Australian/European formats (10-Aug)
        df_working["Date"] = pd.to_datetime(df_working["Date"], errors='coerce', dayfirst=True)
        
        # Step 4: Numeric Conversion
        df_working["Days"] = pd.to_numeric(df_working["Days"], errors='coerce')
        df_working["Usage"] = pd.to_numeric(df_working["Usage"], errors='coerce')
        df_working["Amount"] = pd.to_numeric(df_working["Amount"], errors='coerce')
        
        # Filter out invalid rows (like headers or empty rows) and take last 10
        df_clean = df_working.dropna(subset=["Date", "Usage"]).tail(10)

        if not df_clean.empty:
            # Sort chronologically for the graph
            df_clean = df_clean.sort_values("Date")
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Bar: Billing Days (Secondary Axis)
            fig.add_trace(
                go.Bar(x=df_clean["Date"], y=df_clean["Days"], name="Days", 
                       marker_color='rgba(150, 150, 150, 0.2)'),
                secondary_y=True,
            )

            # Line: Usage (Primary Axis)
            fig.add_trace(
                go.Scatter(x=df_clean["Date"], y=df_clean["Usage"], name="Usage (kWh/Day)", 
                           line=dict(color='royalblue', width=4)),
                secondary_y=False,
            )

            # Line: Cost (Primary Axis)
            fig.add_trace(
                go.Scatter(x=df_clean["Date"], y=df_clean["Amount"], name="Cost ($/Day)", 
                           line=dict(color='firebrick', width=4, dash='dot')),
                secondary_y=False,
            )

            fig.update_layout(
                title_text="Electricity Trends (Last 10 Bills)", 
                hovermode="x unified",
                legend=dict(orientation="h", y=1.1)
            )
            fig.update_xaxes(tickformat="%d %b %y") # Better date labels
            fig.update_yaxes(title_text="Usage & Cost", secondary_y=False)
            fig.update_yaxes(title_text="Days", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No valid data found to graph. Check the Data Preview below.")

        with st.expander("🔍 Data Verification (Last 10 Rows)"):
            st.write("Ensure these columns match your expected data:")
            st.dataframe(df_clean)

    except Exception as e:
        st.error(f"Error loading utility data: {e}")
