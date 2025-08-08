import streamlit as st

def kpi_row(df):
    col1, col2, col3, col4, col5 = st.columns(5)
    if df is None or df.empty:
        vals = [0,0,0,0,0]
    else:
        vals = [
            df.loc[0, "NUM_TRADES"] or 0,
            df.loc[0, "NUM_TRADERS"] or 0,
            df.loc[0, "SITE_PROFITS"] or 0,
            df.loc[0, "SITE_VOLUME"] or 0,
            (df.loc[0, "MARGIN"] or 0) * 100
        ]
    col1.metric("Total Trades", f"${vals[0]:,.0f}")
    col2.metric("Total Traders", f"${vals[1]:,.0f}")
    col3.metric("Total Profit", f"${vals[3]:,.0f}")
    col4.metric("Trading Volume", f"${vals[2]:,.0f}")
    col5.metric("Margin", f"{vals[4]:.2f}%")
