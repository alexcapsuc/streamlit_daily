import streamlit as st
from pathlib import Path
from lib.db import read_sql
from lib.ui import kpi_row
from lib.formats import daterange_to_utc

def render():
    st.title("Trading Platform Overview")

    # Filters
    start_dt_utc, end_dt_utc, sel_asset_ids, sel_duration_ids = daterange_to_utc()

    # KPI Query
    sql_kpi = Path("queries/overview_kpi.sql").read_text()
    sql_kpi = sql_kpi.format(
        start=start_dt_utc.date(),
        end=end_dt_utc.date(),
        asset_ids=",".join(map(str, sel_asset_ids)) or "NULL",
        duration_ids=",".join(map(str, sel_duration_ids)) or "NULL",
    )
    df_kpi = read_sql(sql_kpi)

    kpi_row(df_kpi)

    # TODO: Add charts/tables here from other SQL files
