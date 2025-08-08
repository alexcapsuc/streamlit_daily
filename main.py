import streamlit as st
from pages import Overview, Trader

st.set_page_config(page_title="Trading Platform Dashboard", layout="wide")

page = st.sidebar.radio("Section", ["Overview", "Trader"], index=0)

if page == "Overview":
    Overview.render()
else:
    Trader.render()
