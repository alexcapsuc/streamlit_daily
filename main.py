import streamlit as st
from datetime import datetime, timedelta, date, time


from pages import Overview, Trader
from lib import formats
from lib import db
from queries import filter_lists


st.set_page_config(page_title="Trading Platform Dashboard", layout="wide")

page = st.sidebar.radio("Section", ["Overview", "Trader"], index=0)

df_assets = db.read_sql(filter_lists.assets_list)
assets = (
    dict(zip(df_assets["ASSET_ID"], df_assets["ASSET_NAME"]))
    if not df_assets.empty else {}
)
asset_id_options = list(assets.keys())

df_durations = db.read_sql(filter_lists.durations_list)
durations = df_durations["DURATION"].tolist() if not df_durations.empty else formats.durations

start_date, end_date = formats.today, formats.today 


# ===============================
# SIDEBAR NAVIGATION
# ===============================
st.sidebar.subheader("Section")
# Looks like button pills, but acts like a radio
page = st.sidebar.segmented_control(
    "Section", 
    options=formats.sections, 
    default=formats.default_section
)

st.sidebar.subheader("Filters")

# Quick date-range dropdown
selected_range = st.sidebar.selectbox(
    "Quick Date Range",
    options=list(formats.date_ranges.keys()),
    index=0  # default to the first one, e.g., "Today"
)

# Set start_date and end_date based on the selected range
start_date, end_date = formats.date_ranges[selected_range]

# Date range picker
picked_date = st.sidebar.date_input(
    "Manual Date Range",
    value=(start_date, end_date),
    min_value=date(2013, 1, 1),
    max_value=date(2030, 12, 31)
)
if isinstance(picked_date, tuple) and len(picked_date) == 2:
    start_date, end_date = picked_date

start_dt = datetime.combine(start_date, time.min) - timedelta(hours=2)
end_dt = datetime.combine(end_date, time.max) - timedelta(hours=2)

# Game type selector = duration + asset (independent multiselects)
sel_durations = st.sidebar.multiselect("Durations", durations, default=durations[:3])
sel_asset_ids = st.sidebar.multiselect(
    "Assets",
    options=asset_id_options, 
    default=asset_id_options[:5],
    format_func=lambda _id: assets.get(_id, str(_id))  # display names
)

# Derived combined labels (if you want to display/use later)
selected_game_type_labels = [f"{d} {assets[a]}" for d in sel_durations for a in sel_asset_ids]

st.sidebar.write(selected_game_type_labels)

st.sidebar.write("---")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

    
if page == "Overview":
    Overview.render(start_dt, end_dt, sel_asset_ids, sel_durations)
elif page == "Trader":
    Trader.render(start_dt, end_dt)
