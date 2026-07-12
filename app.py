import os
import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials

# --- TIMEZONE CONFIG ---
os.environ['TZ'] = 'Australia/Sydney'
try:
    time.tzset()
except AttributeError:
    pass

# --- PAGE CONFIG (MUST BE FIRST) ---
st.set_page_config(page_title="Personal Dashboard", layout="wide", page_icon="📊")

# --- CONFIGURATION ---
DASHBOARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1Y1au4X4XE41-wXNMplVtJ0bN0OCh3yODvjMwnlI_kUg/edit"
ELEC_SHEET_URL = "https://docs.google.com/spreadsheets/d/10szrS6fabDdK19pfCCiedhRnueXTC9cS_Cfx8JACuSE/edit"

# Numeric columns that must be coerced to proper numeric dtype
NUMERIC_COLS = ['tokens_prompt', 'tokens_completion', 'cost_total']


# --- GSPREAD CONNECTION HELPER ---
@st.cache_resource
def get_gspread_client():
    """Create a gspread client using service account credentials from Streamlit secrets."""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    # Remove non-credential keys that may be present in secrets.toml
    creds_dict.pop("spreadsheet", None)
    creds_dict.pop("worksheet", None)
    
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)


def gsheet_read(spreadsheet_url: str, worksheet: str, ttl: int = 0) -> pd.DataFrame:
    """Read a Google Sheet worksheet into a DataFrame with caching."""
    @st.cache_data(ttl=ttl, show_spinner=False)
    def _read_cached(_client_id: str, spreadsheet_url: str, worksheet: str):
        client = get_gspread_client()
        ss = client.open_by_url(spreadsheet_url)
        ws = ss.worksheet(worksheet)
        df = get_as_dataframe(ws, evaluate_formulas=True)
        return df
    
    # Use a cache key based on the spreadsheet URL + worksheet name
    return _read_cached("v1", spreadsheet_url, worksheet)


def gsheet_update(spreadsheet_url: str, worksheet: str, data: pd.DataFrame):
    """Update (overwrite) a Google Sheet worksheet with DataFrame data."""
    client = get_gspread_client()
    ss = client.open_by_url(spreadsheet_url)
    try:
        ws = ss.worksheet(worksheet)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=worksheet, rows=data.shape[0], cols=data.shape[1])
    set_with_dataframe(ws, data)
    st.cache_data.clear()


def gsheet_create_worksheet(spreadsheet_url: str, worksheet: str, data: pd.DataFrame):
    """Create a new worksheet in an existing spreadsheet."""
    client = get_gspread_client()
    ss = client.open_by_url(spreadsheet_url)
    ws = ss.add_worksheet(title=worksheet, rows=data.shape[0], cols=data.shape[1])
    set_with_dataframe(ws, data)
    st.cache_data.clear()


# --- DATA LOADING FUNCTIONS ---
def load_gsheet_data():
    """Fetch data from the 'Personal Dashboard' sheet summary row."""
    try:
        df = gsheet_read(DASHBOARD_SHEET_URL, "Sheet1", ttl=0)
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")

    # Fallback defaults — now using new credit-limit fields
    return {
        "Start Available Limit": 1000.0,
        "Current Available Limit": 850.0,
        "Paid Amount": 0.0,
        "Payment Timestamp": "",
        "True Net Spent": 150.0,
        "Total Spent So Far": 180.0,   # kept for backward compat
        "Adjusted Amount": 0.0,
        "Standard Hours": 17.5,
        "Sunday Hours": 5.5,
        "Late Night Hours": 1.5,
        "Public Holiday Hours": 0.0
    }


def load_openrouter_data():
    """Fetch raw OpenRouter historical data from the cloud sheet."""
    try:
        df = gsheet_read(DASHBOARD_SHEET_URL, "OpenRouter_Data", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame()

        # Drop completely empty rows (gspread-dataframe often returns trailing empty rows)
        df = df.dropna(how='all')

        # Parse datetime column
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')

        # ✅ Convert numeric columns from string to proper numeric dtype
        for col in NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df
    except Exception:
        # Returns empty dataframe if worksheet doesn't exist yet
        return pd.DataFrame()


def sync_to_cloud():
    """Pushes current UI values to Google Sheets for Sheet1 metrics."""
    try:
        # Compute current values for payload
        raw_spent = st.session_state.start_limit - st.session_state.current_limit
        true_net_spent = raw_spent + st.session_state.paid_amount

        updates_dict = {
            "Start Available Limit": st.session_state.start_limit,
            "Current Available Limit": st.session_state.current_limit,
            "Paid Amount": st.session_state.paid_amount,
            "Payment Timestamp": st.session_state.payment_timestamp,
            "True Net Spent": true_net_spent,
            "Total Spent So Far": st.session_state.pb_spent,
            "Adjusted Amount": st.session_state.pb_adj,
            "Standard Hours": st.session_state.w_n,
            "Sunday Hours": st.session_state.w_s,
            "Late Night Hours": st.session_state.w_l,
            "Public Holiday Hours": st.session_state.w_p,
        }
        df = pd.DataFrame([updates_dict])
        gsheet_update(DASHBOARD_SHEET_URL, "Sheet1", df)
        st.toast("✅ Cloud Synced!")
    except Exception as e:
        st.error(f"Sync failed: {e}")


# --- PAYMENT TIMESTAMPING CALLBACK ---
def on_paid_amount_change():
    """If Paid Amount > 0, capture current AEST/AEDT timestamp."""
    paid = st.session_state.paid_amount
    if paid > 0:
        st.session_state.payment_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    else:
        st.session_state.payment_timestamp = ""
    sync_to_cloud()


# --- INITIALIZE SESSION STATE ---
# --- INITIALIZE SESSION STATE (upgrade-safe — handles old cached sessions) ---
# Always ensure new credit-limit keys exist, even if "initialized" is from old code
if "start_limit" not in st.session_state:
    gs_data = load_gsheet_data()
    st.session_state.start_limit = float(gs_data.get("Start Available Limit", 1000.0))
    st.session_state.current_limit = float(gs_data.get("Current Available Limit", 850.0))
    st.session_state.paid_amount = float(gs_data.get("Paid Amount", 0.0))
    st.session_state.payment_timestamp = gs_data.get("Payment Timestamp", "")

if "initialized" not in st.session_state:
    gs_data = load_gsheet_data()
    # New credit-limit fields (also set here to cover fresh first-run)
    st.session_state.start_limit = float(gs_data.get("Start Available Limit", 1000.0))
    st.session_state.current_limit = float(gs_data.get("Current Available Limit", 850.0))
    st.session_state.paid_amount = float(gs_data.get("Paid Amount", 0.0))
    st.session_state.payment_timestamp = gs_data.get("Payment Timestamp", "")
    # Existing fields (kept for backward compat)
    st.session_state.pb_spent = float(gs_data.get("Total Spent So Far", 180.0))
    st.session_state.pb_adj = float(gs_data.get("Adjusted Amount", 0.0))
    st.session_state.w_n = float(gs_data.get("Standard Hours", 17.5))
    st.session_state.w_s = float(gs_data.get("Sunday Hours", 5.5))
    st.session_state.w_l = float(gs_data.get("Late Night Hours", 1.5))
    st.session_state.w_p = float(gs_data.get("Public Holiday Hours", 0.0))
    st.session_state.initialized = True

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔄 Connection")
    if st.button("Manual Refresh"):
        st.cache_data.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# --- DATE CALCULATIONS ---
NOW = datetime.now()
ONE_YEAR_AGO = NOW - timedelta(days=365)

# --- APP INTERFACE ---
st.title("📊 Personal Dashboard")
tab1, tab2, tab3, tab4 = st.tabs(["🤖 OpenRouter Data", "💰 Personal Budget", "🛒 Woolies Pay", "⚡ Utility Tracker"])

# --- TAB 1: OPENROUTER DATA ---
with tab1:
    st.header("OpenRouter Token & Cost Analytics")

    # Load historical database
    df_or = load_openrouter_data()

    # --- FILE UPLOADER & PROCESSING PIPELINE ---
    uploaded_file = st.file_uploader("Upload OpenRouter Activity CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            df_new = pd.read_csv(uploaded_file)
            df_new['created_at'] = pd.to_datetime(df_new['created_at'])

            # ✅ Convert numeric columns in the uploaded CSV too
            for col in NUMERIC_COLS:
                if col in df_new.columns:
                    df_new[col] = pd.to_numeric(df_new[col], errors='coerce')

            # Combine historical data and new data if history exists
            if not df_or.empty:
                df_combined = pd.concat([df_or, df_new], ignore_index=True)
            else:
                df_combined = df_new

            # De-duplicate entries based on unique OpenRouter generation_id
            df_combined = df_combined.drop_duplicates(subset=["generation_id"], keep="first")

            # Apply rolling 1-year retention threshold (Pruning old data)
            df_combined = df_combined[df_combined['created_at'] >= ONE_YEAR_AGO]

            # Create a string-serializable copy for Google Sheets transport
            df_upload = df_combined.copy()
            df_upload['created_at'] = df_upload['created_at'].dt.strftime('%Y-%m-%d %H:%M:%S')

            # ✅ Handle empty/NaN text fields cleanly for cloud storage payload
            for col in df_upload.columns:
                if col in NUMERIC_COLS:
                    df_upload[col] = pd.to_numeric(df_upload[col], errors='coerce')
                elif df_upload[col].dtype == 'object':
                    df_upload[col] = df_upload[col].fillna('')

            # Save parsed clean tracking sheet back to Google Sheets
            try:
                gsheet_update(DASHBOARD_SHEET_URL, "OpenRouter_Data", df_upload)
            except Exception:
                # Automatic fallback: creates the worksheet tab if it doesn't exist yet
                gsheet_create_worksheet(DASHBOARD_SHEET_URL, "OpenRouter_Data", df_upload)

            st.cache_data.clear()
            st.success("🚀 File processed, de-duplicated, and rolling 1-year archive updated successfully!")
            df_or = df_combined  # Update view state instantly
        except Exception as e:
            st.error(f"Error handling file upload processing pipeline: {e}")

    st.divider()

    if not df_or.empty:
        # Precompute target metrics columns
        df_or['total_tokens'] = df_or['tokens_prompt'] + df_or['tokens_completion']
        df_or['year'] = df_or['created_at'].dt.year
        df_or['month'] = df_or['created_at'].dt.strftime('%b')

        # Display data update date ceiling header
        max_date = df_or['created_at'].max().strftime('%d-%b-%Y')
        st.subheader(f"📅 Data updated till: {max_date}")

        # --- FILTERS PANEL ---
        st.write("### 🔍 Filters")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)

        with f_col1:
            model_query = st.text_input("Include Model (e.g., deepseek):", value="")
        with f_col2:
            default_exclusions = "bytedance/seedance-2.0-fast-20260414|google/veo-3.1-lite-20260331|google/gemini-2.5-flash-image|recraft/recraft-v4.1-pro-vector-20260514"
            exclude_query = st.text_input("Exclude Model:", value=default_exclusions)
        with f_col3:
            years_avail = sorted(df_or['year'].unique(), reverse=True)
            selected_years = st.multiselect("Filter by Year:", options=years_avail, default=years_avail)
        with f_col4:
            months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            months_avail = [m for m in months_order if m in df_or['month'].unique()]
            selected_months = st.multiselect("Filter by Month:", options=months_avail, default=months_avail)

        # Apply filters seamlessly
        df_filtered = df_or.copy()
        if model_query:
            df_filtered = df_filtered[df_filtered['model_permaslug'].str.contains(model_query, case=False, na=False)]
        if exclude_query:
            df_filtered = df_filtered[~df_filtered['model_permaslug'].str.contains(exclude_query, case=False, na=False)]
        if selected_years:
            df_filtered = df_filtered[df_filtered['year'].isin(selected_years)]
        if selected_months:
            df_filtered = df_filtered[df_filtered['month'].isin(selected_months)]

        # --- CALCULATION LOGIC & SUMMARY CARDS ---
        def calculate_metrics(dataframe):
            t_tokens = pd.to_numeric(dataframe['total_tokens'], errors='coerce').sum()
            t_amount = pd.to_numeric(dataframe['cost_total'], errors='coerce').sum()
            amt_per_3m = (t_amount / (t_tokens / 3000000)) if t_tokens > 0 else 0.0
            return t_tokens, t_amount, amt_per_3m

        # Compute Unfiltered / Filtered values
        unfilt_tok, unfilt_amt, unfilt_3m = calculate_metrics(df_or)
        filt_tok, filt_amt, filt_3m = calculate_metrics(df_filtered)

        # UI Metrics Blocks Display
        st.write("### 📈 Key Summary Metrics")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Total Tokens (Filtered / Global)", f"{filt_tok:,.0f}", delta=f"Global: {unfilt_tok:,.0f}", delta_color="off")
        m_col2.metric("Total Cost (Filtered / Global)", f"${filt_amt:,.2f}", delta=f"Global: ${unfilt_amt:,.2f}", delta_color="off")
        m_col3.metric("Cost per 3M Tokens (Filtered)", f"${filt_3m:,.2f}", delta=f"Global: ${unfilt_3m:,.2f}", delta_color="off")

        st.divider()

        # --- INTERACTIVE DATAFRAME VIEW ---
        st.write("### 📋 Model Usage Breakdown")

        df_display = df_filtered.groupby('model_permaslug').agg(
            Total_Tokens=('total_tokens', 'sum'),
            Total_Amount=('cost_total', 'sum')
        ).reset_index()

        df_display['Amount_per_3M_Tokens'] = df_display.apply(
            lambda r: (r['Total_Amount'] / (r['Total_Tokens'] / 3000000)) if r['Total_Tokens'] > 0 else 0.0, axis=1
        )

        df_display = df_display.sort_values(by="Amount_per_3M_Tokens", ascending=True)
        df_display.columns = ["Model Permaslug", "Total Tokens", "Total Amount", "Amount per 3M Tokens"]

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total Tokens": st.column_config.NumberColumn(format="%,d"),
                "Total Amount": st.column_config.NumberColumn(format="$%.4f"),
                "Amount per 3M Tokens": st.column_config.NumberColumn(format="$%.2f")
            }
        )

        # --- MODEL PERCENTAGE VISUALIZATION WITH 80% PARETO GROUPING ---
        if not df_display.empty:
            st.write("### 🍩 Model Volume Proportion (%)")

            df_chart = df_display.sort_values(by="Total Tokens", ascending=False).copy()
            total_tokens_sum = df_chart["Total Tokens"].sum()

            if total_tokens_sum > 0:
                df_chart['cumsum_pct'] = df_chart['Total Tokens'].cumsum() / total_tokens_sum
                df_chart['prev_cumsum_pct'] = df_chart['cumsum_pct'].shift(1, fill_value=0.0)
                df_chart['Chart_Label'] = df_chart.apply(
                    lambda row: row['Model Permaslug'] if row['prev_cumsum_pct'] < 0.80 else 'Others', axis=1
                )
                df_pie_data = df_chart.groupby('Chart_Label')['Total Tokens'].sum().reset_index()

                fig_pie = go.Figure(data=[go.Pie(
                    labels=df_pie_data["Chart_Label"],
                    values=df_pie_data["Total Tokens"],
                    hole=0.4,
                    textinfo='label+percent',
                    insidetextorientation='radial'
                )])

                fig_pie.update_layout(
                    margin=dict(t=20, b=20, l=20, r=20),
                    showlegend=True,
                    legend=dict(orientation="h", y=-0.1)
                )

                st.plotly_chart(fig_pie, use_container_width=True)

    else:
        st.info("No OpenRouter data found in the cloud workspace. Upload a CSV file above to establish records.")


# =============================================================================
# TAB 2: PERSONAL BUDGET — REFACTORED WITH CREDIT-LIMIT LOGIC
# =============================================================================
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts **Thursday**. Using credit-card available-limit logic to bypass pending / cleared entry errors.")

    st.metric("Weekly Budget", "$630.00")

    # --- NEW 3-FIELD INPUTS (replace old "Total Spent So Far") ---
    start_limit = st.number_input(
        "Weekly Start Available Limit (AUD):",
        value=st.session_state.start_limit,
        step=10.0,
        key="start_limit",
        on_change=sync_to_cloud
    )
    current_limit = st.number_input(
        "Current Available Limit (AUD):",
        value=st.session_state.current_limit,
        step=10.0,
        key="current_limit",
        on_change=sync_to_cloud
    )
    paid_amount = st.number_input(
        "Paid Amount (AUD):",
        value=st.session_state.paid_amount,
        step=1.0,
        min_value=0.0,
        key="paid_amount",
        on_change=on_paid_amount_change  # captures timestamp when > 0
    )

    # --- DISPLAY PAYMENT TIMESTAMP (if captured) ---
    if st.session_state.payment_timestamp:
        st.info(f"🕒 **Payment captured at:** {st.session_state.payment_timestamp} AEST/AEDT")

    # --- KEEP EXISTING ADJUSTED AMOUNT INPUT ---
    adj = st.number_input(
        "Adjusted Amount (AUD):",
        value=st.session_state.pb_adj,
        step=1.0,
        key="pb_adj",
        on_change=sync_to_cloud
    )

    today_is_over = st.checkbox("Today is over (count as completed day)", value=False)

    # --- DAYS REMAINING (unchanged logic) ---
    current_weekday = NOW.weekday()
    days_since_thurs = (current_weekday - 3) % 7

    if current_weekday == 2:  # Wednesday
        days_left_weekly = 0 if today_is_over else 1
    else:
        days_left_weekly = (7 - (days_since_thurs + 1)) if today_is_over else (7 - days_since_thurs)

    # --- CORE CALCULATION LOGIC (New) ---
    weekly_limit = 630.0
    raw_spent = start_limit - current_limit
    true_net_spent = raw_spent + paid_amount
    remaining_funds = weekly_limit - true_net_spent + adj
    daily_allowance_weekly = remaining_funds / max(days_left_weekly, 1)

    st.divider()
    col_a, col_b, col_c = st.columns(3)

    col_a.metric("Remaining Budget", f"${remaining_funds:.2f}")
    col_a.caption(f"🗓️ {days_left_weekly} days remaining")

    if days_left_weekly > 0:
        col_b.metric("Allowed Daily Spend", f"${daily_allowance_weekly:.2f}")
    else:
        col_b.metric("Allowed Daily Spend", "Last Day")

    col_c.metric("True Net Spent", f"${true_net_spent:.2f}")

    # --- DETAIL BREAKDOWN (collapsible for power users) ---
    with st.expander("📐 Calculation Breakdown"):
        st.write(f"**Raw Spent** = Start Available ({start_limit}) – Current Available ({current_limit}) = **${raw_spent:.2f}**")
        st.write(f"**True Net Spent** = Raw Spent ({raw_spent}) + Paid Amount ({paid_amount}) = **${true_net_spent:.2f}**")
        st.write(f"**Remaining** = Weekly Budget ({weekly_limit}) – True Net Spent ({true_net_spent}) = **${remaining_funds:.2f}**")
        if days_left_weekly > 0:
            st.write(f"**Daily Allowance** = Remaining ({remaining_funds:.2f}) ÷ Days Left ({days_left_weekly}) = **${daily_allowance_weekly:.2f}**")

# --- TAB 3: WOOLIES PAY (unchanged) ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    st.info("Rates include FY27 Pay Increase (4.75%), Casual Loading and Shift Penalties. Tax @28%")

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        n_h = st.number_input("Standard Hours:", value=st.session_state.w_n, step=0.5, key="w_n", on_change=sync_to_cloud)
    with row1_col2:
        l_h = st.number_input("Late Night Hours:", value=st.session_state.w_l, step=0.5, key="w_l", on_change=sync_to_cloud)
    with row2_col1:
        s_h = st.number_input("Sunday Hours:", value=st.session_state.w_s, step=0.5, key="w_s", on_change=sync_to_cloud)
    with row2_col2:
        p_h = st.number_input("Public Holiday Hours:", value=st.session_state.w_p, step=0.5, key="w_p", on_change=sync_to_cloud)

    FY27_INCREASE = 1.0475

    BASE_ORD = 26.9797 * FY27_INCREASE
    CAS_LOAD = 6.7449 * FY27_INCREASE
    SHIFT_25 = 6.7449 * FY27_INCREASE
    SHIFT_50 = 13.4899 * FY27_INCREASE
    LAUNDRY, NET_GOAL = 6.25, 520.00

    rate_std = BASE_ORD + CAS_LOAD + SHIFT_25
    rate_pen = BASE_ORD + CAS_LOAD + SHIFT_50
    rate_ph = BASE_ORD * 2.5

    total_gross = (n_h * rate_std) + ((l_h + s_h) * rate_pen) + (p_h * rate_ph)
    est_net = (total_gross * 0.72) + LAUNDRY

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated Net Pay", f"${est_net:.2f}")
    m2.metric("Total Hours", f"{n_h + l_h + s_h + p_h} hrs")

    goal_delta = est_net - NET_GOAL
    m3.metric("Goal Status", f"${goal_delta:.2f}", delta=f"${goal_delta:.2f} vs $520", delta_color="normal")

# --- TAB 4: UTILITY TRACKER (unchanged) ---
with tab4:
    st.header("⚡ Electricity Analysis")
    try:
        df_e_raw = gsheet_read(ELEC_SHEET_URL, "Sheet1", ttl=0)
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
            st.plotly_chart(fig_e, use_container_width=True)
    except Exception as e:
        st.error(f"Elec Error: {e}")

    st.divider()
    st.header("🔥 Gas Analysis")
    try:
        df_g_raw = gsheet_read(ELEC_SHEET_URL, "Gas", ttl=0)
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
            st.plotly_chart(fig_g, use_container_width=True)
    except Exception as e:
        st.error(f"Gas Error: {e}")
