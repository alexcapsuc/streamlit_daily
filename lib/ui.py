import streamlit as st

def kpi_row(df):
    col1, col2, col3, col4, col5 = st.columns(5)
    if df is None or df.empty:
        vals = [0,0,0,0,0]
    else:
        vals = [
            df.loc[0, "TOTAL_DEPOSITS"] or 0,
            df.loc[0, "TOTAL_WITHDRAWALS"] or 0,
            df.loc[0, "TOTAL_VOLUME"] or 0,
            df.loc[0, "TOTAL_PROFIT"] or 0,
            (df.loc[0, "MARGIN"] or 0) * 100
        ]
    col1.metric("Total Deposits", f"${vals[0]:,.2f}")
    col2.metric("Total Withdrawals", f"${vals[1]:,.2f}")
    col3.metric("Trading Volume", f"${vals[2]:,.2f}")
    col4.metric("Total Profit", f"${vals[3]:,.2f}")
    col5.metric("Margin", f"{vals[4]:.2f}%")
