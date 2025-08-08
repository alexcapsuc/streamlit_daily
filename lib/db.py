import streamlit as st
from snowflake.snowpark.context import get_active_session

session = get_active_session()

@st.cache_data(ttl=60, show_spinner=False)
def read_sql(sql: str):
    return session.sql(sql).to_pandas()
