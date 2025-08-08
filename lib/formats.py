import streamlit as st
from datetime import datetime, time, timedelta

def daterange_to_utc():
    today_dt = (datetime.today() + timedelta(hours=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date, end_date = st.sidebar.date_input("Select Date Range", value=(today_dt.date(), today_dt.date()))
    start_dt_utc = datetime.combine(start_date, time.min) - timedelta(hours=2)
    end_dt_utc = datetime.combine(end_date, time.max) - timedelta(hours=2)
    sel_asset_ids = []  # TODO: hook up assets multiselect
    sel_duration_ids = []  # TODO: hook up durations multiselect
    return start_dt_utc, end_dt_utc, sel_asset_ids, sel_duration_ids
