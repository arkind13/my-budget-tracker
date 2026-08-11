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


# --- HELPER FUNCTION ---
def safe_float(value, default=0.0):
    """Safely convert a value to float, handling NaN, None, and strings."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


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
    """
    Update (overwrite) a Google Sheet worksheet with DataFrame data.

    Uses a targeted write: only the cells covered by the DataFrame's used range
    are written (via worksheet.update with raw values), instead of clear() +
    set_with_dataframe which rewrites the entire worksheet on every change.
    This avoids full-worksheet rewrites that cause timeouts / API quota hits
    when a single field changes.
    """
    client = get_gspread_client()
    ss = client.open_by_url(spreadsheet_url)
    try:
        ws = ss.worksheet(worksheet)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=worksheet, rows=data.shape[0], cols=data.shape[1])

    # Header row: column names; data rows follow.
    header = [str(c) for c in data.columns]
    body = []
    for _, row in data.iterrows():
        body.append(["" if pd.isna(v) else v for v in row])

    rows_to_write = [header] + body
    # Write only the used range (row1=header, row2..=data). Do NOT clear the
    # rest of the sheet — untouched cells keep their values.
    ws.update(rows_to_write, raw=False)  # values first; range auto-detected
    st.cache_data.clear()


def gsheet_update_field(spreadsheet_url: str, worksheet: str, field: str, value):
    """
    Update a SINGLE field (cell) in the dashboard worksheet without touching
    any other cell. This is the low-traffic primitive used for targeted edits
    (e.g. changing only the balance or only one Woolies hours field).

    Layout: row 1 = column names, row 2 = the single data row.
    The field's column is located by scanning the header row.

    Args:
        spreadsheet_url (str): The Google Sheet URL.
        worksheet (str): Worksheet name (e.g. "Sheet1").
        field (str): Exact column header name (e.g. "Current Available Limit").
        value: The new value to write.
    """
    client = get_gspread_client()
    ss = client.open_by_url(spreadsheet_url)
    ws = ss.worksheet(worksheet)
    headers = ws.row_values(1)
    if field not in headers:
        raise ValueError(f"Field '{field}' not found in worksheet headers: {headers}")
    col_idx = headers.index(field) + 1
    ws.update_cell(2, col_idx, value)
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
            # Convert to dict and handle NaN values properly
            raw_dict = df.iloc[0].to_dict()
            # Clean the dict: replace NaN with None
            clean_dict = {}
            for key, value in raw_dict.items():
                if pd.isna(value):
                    clean_dict[key] = None
                else:
                    clean_dict[key] = value
            return clean_dict
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


# Mapping: Google-Sheet header name -> Streamlit session_state key.
# Used by sync_to_cloud(field) to read the changed value for a targeted update.
FIELD_TO_SESSION_KEY = {
    "Start Available Limit": "start_limit",
    "Current Available Limit": "current_limit",
    "Paid Amount": "paid_amount",
    "Payment Timestamp": "payment_timestamp",
    "True Net Spent": None,  # computed, not stored as an input
    "Total Spent So Far": "pb_spent",
    "Adjusted Amount": "pb_adj",
    "Standard Hours": "w_n",
    "Sunday Hours": "w_s",
    "Late Night Hours": "w_l",
    "Public Holiday Hours": "w_p",
}


def sync_to_cloud(field=None):
    """
    Pushes UI values to Google Sheets.

    When `field` is provided (e.g. "Current Available Limit"), only that single
    cell is written via gsheet_update_field — a targeted edit that avoids
    rewriting the entire worksheet. This fixes the over-sync problem where
    changing one field rewrote every column and caused timeouts / quota hits.

    When `field` is None, falls back to writing the whole dashboard row
    (used for bulk operations).

    Args:
        field (str | None): Exact header name of the field that changed.
    """
    try:
        if field is not None:
            session_key = FIELD_TO_SESSION_KEY.get(field)
            if session_key is None:
                raise ValueError(f"No session_state key mapped for field '{field}'")
            gsheet_update_field(DASHBOARD_SHEET_URL, "Sheet1", field,
                                st.session_state.get(session_key, None))
            st.toast(f"✅ Synced: {field}")
            return

        raw_spent = st.session_state.start_limit - st.session_state.current_limit
        pb_adj = st.session_state.get("pb_adj", 0.0)
        true_net_spent = raw_spent + paid_amount - pb_adj        # ← adjusted amount subtracted

        # Defensive: grab pb_spent with a fallback
        pb_spent = st.session_state.get("pb_spent", 0.0)
        pb_adj = st.session_state.get("pb_adj", 0.0)
        w_n = st.session_state.get("w_n", 0.0)
        w_s = st.session_state.get("w_s", 0.0)
        w_l = st.session_state.get("w_l", 0.0)
        w_p = st.session_state.get("w_p", 0.0)

        updates_dict = {
            "Start Available Limit": st.session_state.start_limit,
            "Current Available Limit": st.session_state.current_limit,
            "Paid Amount": st.session_state.paid_amount,
            "Payment Timestamp": st.session_state.payment_timestamp,
            "True Net Spent": true_net_spent,
            "Total Spent So Far": pb_spent,
            "Adjusted Amount": pb_adj,
            "Standard Hours": w_n,
            "Sunday Hours": w_s,
            "Late Night Hours": w_l,
            "Public Holiday Hours": w_p,
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
    sync_to_cloud("Paid Amount")
    # Payment timestamp changed too — write it in the same targeted fashion.
    sync_to_cloud("Payment Timestamp")


# --- INITIALIZE SESSION STATE (upgrade-safe) ---
# Use a single block that always checks each key individually
_gs_data = load_gsheet_data()

# Credit-limit fields
if "start_limit" not in st.session_state:
    st.session_state.start_limit = safe_float(_gs_data.get("Start Available Limit"), 1000.0)
if "current_limit" not in st.session_state:
    st.session_state.current_limit = safe_float(_gs_data.get("Current Available Limit"), 850.0)
if "paid_amount" not in st.session_state:
    st.session_state.paid_amount = safe_float(_gs_data.get("Paid Amount"), 0.0)
if "payment_timestamp" not in st.session_state:
    st.session_state.payment_timestamp = _gs_data.get("Payment Timestamp", "") or ""

# Legacy fields (still needed for backward compat and sync_to_cloud)
if "pb_spent" not in st.session_state:
    st.session_state.pb_spent = safe_float(_gs_data.get("Total Spent So Far"), 180.0)
if "pb_adj" not in st.session_state:
    st.session_state.pb_adj = safe_float(_gs_data.get("Adjusted Amount"), 0.0)
if "w_n" not in st.session_state:
    st.session_state.w_n = safe_float(_gs_data.get("Standard Hours"), 17.5)
if "w_s" not in st.session_state:
    st.session_state.w_s = safe_float(_gs_data.get("Sunday Hours"), 5.5)
if "w_l" not in st.session_state:
    st.session_state.w_l = safe_float(_gs_data.get("Late Night Hours"), 1.5)
if "w_p" not in st.session_state:
    st.session_state.w_p = safe_float(_gs_data.get("Public Holiday Hours"), 0.0)

# Mark as initialized
if "initialized" not in st.session_state:
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

        # API key label: blank/NaN keys are labelled as "chat"
        if 'api_key_name' not in df_or.columns:
            df_or['api_key_name'] = ''
        df_or['api_key_label'] = df_or['api_key_name'].fillna('').astype(str).str.strip().replace('', 'chat')

        # Display data update date ceiling header
        max_date = df_or['created_at'].max().strftime('%d-%b-%Y')
        st.subheader(f"📅 Data updated till: {max_date}")

        # --- FILTERS PANEL ---
        st.write("### 🔍 Filters")
        f_col1, f_col2 = st.columns(2)

        with f_col1:
            model_query = st.text_input("Include Model (e.g., deepseek):", value="")
        with f_col2:
            default_exclusions = "bytedance/seedance-2.0-fast-20260414|google/veo-3.1-lite-20260331|google/gemini-2.5-flash-image|recraft/recraft-v4.1-pro-vector-20260514"
            exclude_query = st.text_input("Exclude Model:", value=default_exclusions)

        f_col3, f_col4, f_col5 = st.columns(3)
        with f_col3:
            years_avail = sorted(df_or['year'].unique(), reverse=True)
            selected_years = st.multiselect("Filter by Year:", options=years_avail, default=years_avail)
        with f_col4:
            months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            months_avail = [m for m in months_order if m in df_or['month'].unique()]
            selected_months = st.multiselect("Filter by Month:", options=months_avail, default=months_avail)
        with f_col5:
            api_keys_avail = sorted(df_or['api_key_label'].unique())
            selected_api_keys = st.multiselect("Filter by API Key Name:", options=api_keys_avail, default=api_keys_avail)

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
        if selected_api_keys:
            df_filtered = df_filtered[df_filtered['api_key_label'].isin(selected_api_keys)]

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

        # --- API KEY USAGE PIE CHART ---
        df_key_usage = df_filtered.groupby('api_key_label').agg(
            Total_Amount=('cost_total', lambda s: pd.to_numeric(s, errors='coerce').sum())
        ).reset_index()

        df_key_usage = df_key_usage.sort_values('Total_Amount', ascending=False)

        if (df_key_usage['Total_Amount'] > 0).any():
            st.write("### 🥧 API Key Cost Proportion (%)")

            fig_key_pie = go.Figure(data=[go.Pie(
                labels=df_key_usage['api_key_label'],
                values=df_key_usage['Total_Amount'],
                hole=0.4,
                textinfo='label+percent',
                insidetextorientation='radial'
            )])

            fig_key_pie.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                showlegend=True,
                legend=dict(orientation="h", y=-0.1)
            )

            st.plotly_chart(fig_key_pie, use_container_width=True)

    else:
        st.info("No OpenRouter data found in the cloud workspace. Upload a CSV file above to establish records.")


# =============================================================================
# TAB 2: PERSONAL BUDGET — REFACTORED WITH CREDIT-LIMIT LOGIC
# =============================================================================
with tab2:
    st.header("Weekly Budget Tracker")
    st.info("Week starts **Thursday**. Using credit-card available-limit logic to bypass pending / cleared entry errors.")

    st.metric("Weekly Budget", "$700.00")

    # --- NEW 3-FIELD INPUTS (replace old "Total Spent So Far") ---
    start_limit = st.number_input(
        "Weekly Start Available Limit (AUD):",
        value=st.session_state.start_limit,
        step=10.0,
        key="start_limit",
        on_change=lambda: sync_to_cloud("Start Available Limit")
    )
    current_limit = st.number_input(
        "Current Available Limit (AUD):",
        value=st.session_state.current_limit,
        step=10.0,
        key="current_limit",
        on_change=lambda: sync_to_cloud("Current Available Limit")
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
        on_change=lambda: sync_to_cloud("Adjusted Amount")
    )

    today_is_over = st.checkbox("Today is over (count as completed day)", value=False)

    # --- DAYS REMAINING (unchanged logic) ---
    current_weekday = NOW.weekday()
    days_since_thurs = (current_weekday - 3) % 7

    if current_weekday == 2:  # Wednesday
        days_left_weekly = 0 if today_is_over else 1
    else:
        days_left_weekly = (7 - (days_since_thurs + 1)) if today_is_over else (7 - days_since_thurs)

    # --- CORE CALCULATION LOGIC (Fixed) ---
    weekly_limit = 700.0
    raw_spent = start_limit - current_limit
    true_net_spent = raw_spent + paid_amount - adj       # ← adj IS NOW ACTUALLY SUBTRACTED
    remaining_funds = weekly_limit - true_net_spent       # ← no longer needs +adj here
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
        st.write(f"**Adjusted Amount** = **${adj:.2f}** (subtracted)")
        st.write(f"**True Net Spent** = Raw Spent ({raw_spent:.2f}) + Paid Amount ({paid_amount:.2f}) – Adjusted Amount ({adj:.2f}) = **${true_net_spent:.2f}**")
        st.write(f"**Remaining Budget** = Weekly Budget ({weekly_limit}) – True Net Spent ({true_net_spent:.2f}) = **${remaining_funds:.2f}**")
        if days_left_weekly > 0:
            st.write(f"**Allowed Daily Spend** = Remaining ({remaining_funds:.2f}) ÷ Days Left ({days_left_weekly}) = **${daily_allowance_weekly:.2f}**")

# --- TAB 3: WOOLIES PAY (unchanged) ---
with tab3:
    st.header("🛒 Woolies Pay Calculator")
    st.info("Rates include FY27 Pay Increase (4.75%), Casual Loading and Shift Penalties. Tax @28%")

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        n_h = st.number_input("Standard Hours:", value=st.session_state.w_n, step=0.5, key="w_n", on_change=lambda: sync_to_cloud("Standard Hours"))
    with row1_col2:
        l_h = st.number_input("Late Night Hours:", value=st.session_state.w_l, step=0.5, key="w_l", on_change=lambda: sync_to_cloud("Late Night Hours"))
    with row2_col1:
        s_h = st.number_input("Sunday Hours:", value=st.session_state.w_s, step=0.5, key="w_s", on_change=lambda: sync_to_cloud("Sunday Hours"))
    with row2_col2:
        p_h = st.number_input("Public Holiday Hours:", value=st.session_state.w_p, step=0.5, key="w_p", on_change=lambda: sync_to_cloud("Public Holiday Hours"))

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