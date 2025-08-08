import streamlit as st
from pathlib import Path
from lib.db import read_sql
from lib.formats import daterange_to_utc

def render():
    st.title("Trader Detail Overview")

    trader_id = st.text_input("Enter Trader ID, Email, or Username")
    if not trader_id:
        st.info("Please enter a trader to view details.")
        return

    start_dt_utc, end_dt_utc, *_ = daterange_to_utc()

    sql_profile = Path("queries/trader_profile.sql").read_text()
    sql_profile = sql_profile.format(
        trader_id=trader_id,
        start=start_dt_utc.date(),
        end=end_dt_utc.date()
    )
    df_profile = read_sql(sql_profile)

    st.dataframe(df_profile, use_container_width=True)
