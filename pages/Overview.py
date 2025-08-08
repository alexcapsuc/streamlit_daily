import streamlit as st
from pathlib import Path


from lib.db import read_sql
from lib.ui import kpi_row


def render(start_dt_utc, end_dt_utc, sel_asset_ids, sel_duration_ids):
    st.title("Trading Platform Overview")

    # KPI Query
    sql_kpi = Path("queries/overview_kpi.sql").read_text()
    
    sql_kpi_params = {
        "start": start_dt_utc.date(),
        "end": end_dt_utc.date(),
        "asset_ids": ",".join(map(str, sel_asset_ids)) or "NULL",
        "duration_ids": ",".join(map(str, sel_duration_ids)) or "NULL"
    }
    df_kpi = read_sql(sql_kpi, params=sql_kpi_params)

    kpi_row(df_kpi)

    # TODO: Add charts/tables here from other SQL files
