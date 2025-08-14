import streamlit as st
from datetime import datetime, timedelta, date, time


from manual_pages import Overview, Trader
from lib import formats, multiselect
from lib import db
from queries.filter_lists import assets_list, durations_list


st.set_page_config(page_title="Trading Platform Dashboard", layout="wide")


# Keep query params in sync (no st.rerun here)
def sync_url_param():
    if st.session_state.page is None:
        st.session_state.page = "Overview"
    if st.session_state.page != qp.get("page", "Overview"):
        # if st.session_state.page == 'Overview' and qp.get("page") == "Trader":
        st.query_params.update(page=st.session_state.page, trader_id=url_requested_trader)

def go_to_page(page: str, trader_id: str | int = ""):
    st.query_params.update(page=page, trader_id=str(trader_id))
    st.rerun()


# Read current URL params
qp = st.query_params
url_requested_trader = qp.get("trader_id", "44554")
url_requested_page = qp.get("page", "Overview")

# Get values for filters
df_assets = db.read_sql(assets_list)
assets = (
    dict(zip(df_assets["ASSET_ID"], df_assets["ASSET_NAME"]))
    if not df_assets.empty else formats.assets
)
st.session_state["assets_dict"] = assets
asset_id_options = list(assets.keys())

df_durations = db.read_sql(durations_list)
durations = df_durations["DURATION"].tolist() if not df_durations.empty else formats.durations

# ===============================
# SIDEBAR NAVIGATION
# ===============================
st.sidebar.subheader("Section")

# Looks like button pills, but acts like a radio
page = st.sidebar.segmented_control(
    "Section",
    label_visibility="hidden",
    options=formats.sections, 
    default=url_requested_page,
    key="page",
    on_change=sync_url_param
)

if page != url_requested_page:  # user clicked a new section
    go_to_page(page, url_requested_trader)

st.sidebar.subheader("Filters")

# Quick date-range dropdown
st.sidebar.selectbox(
    "Quick Date Range",
    options=list(formats.date_ranges.keys()),
    key="selected_range",
    index=0  # default to the first one, e.g., "Today"
)

# Set start_date and end_date based on the selected range
start_date, end_date = formats.date_ranges[st.session_state.selected_range]

# Date range picker
picked_date = st.sidebar.date_input(
    "Manual Date Range",
    value=(start_date, end_date),
    min_value=date(2013, 1, 1),
    max_value=date(2030, 12, 31),
    key="date_input"
)
if isinstance(picked_date, tuple) and len(picked_date) == 2:
    start_date, end_date = picked_date

start_dt = datetime.combine(start_date, time.min) - timedelta(hours=2)
end_dt = datetime.combine(end_date, time.max) - timedelta(hours=2)

# Game type selector = duration + asset (independent multiselects)
sel_durations, all_durations = multiselect.multi_with_all(
    label="Durations", 
    options=durations,
    key="durations"
)
sel_asset_ids, all_assets = multiselect.multi_with_all(
    label="Assets",
    options=asset_id_options, 
    format_func=lambda _id: assets.get(_id, str(_id)),  # display names
    key="assets"
)

st.sidebar.write("---")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()

if page == "Overview":
    Overview.render(
        start_dt, end_dt, 
        all_assets, all_durations, sel_asset_ids, sel_durations
    )
elif page == "Trader":
    Trader.render(
        start_dt, end_dt, 
        url_requested_trader
    )

st.write('End')
st.write(st.session_state)

