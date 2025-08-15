import streamlit as st
from pathlib import Path
import plotly.graph_objects as go


from lib.db import read_sql
from lib.formats import colors_context
# from lib.ui import kpi_row
from queries.overview_sql import queries


def trader_link(tid):
    st.page_link(
        page=f"?page=Trader&trader_id={tid}",   # relative URL within the app
        label=f"Open {tid}",               # looks/behaves like a link
        # icon=":material/open_in_new:"      # optional
    )
    st.query_params.update(page="Trader", trader_id=str(tid))
    st.rerun()

def go_to_trader(tid):
    st.query_params.update(page="Trader", trader_id=str(tid))
    st.rerun()

def _show_trader_history(trader_data_orig, start_dt_utc, end_dt_utc):
    """
    Shows trader's monthly history (volume, pnl, dep/wd)
    :param trader_data:
    :param start_dt_utc:
    :param end_dt_utc:
    :return:
    """
    trader_data = trader_data_orig.copy()
    trader_data["pnl"] = (trader_data["INCOME"] - trader_data["INVEST"]).cumsum()
    trader_data["dep"] = (trader_data["DEPOSIT"]).cumsum()
    trader_data["wd"] = (trader_data["WITHDRAWAL"]).cumsum()

    with st.expander('Sample Data', width=1800):
        st.write(f"Trades rows: {trader_data.shape[0]}, example rows: ")
        st.dataframe(trader_data.head(100))

    fig = go.Figure()

    if not trader_data.empty:
        fig.add_trace(go.Scatter(
            x=trader_data["MM"],
            y=trader_data["INVEST"].values,
            mode="lines",
            name="Volume",
            fill="tozeroy",
            fillcolor=colors_context["background_area"],
            line=dict(width=1, shape='hvh', color=colors_context["background_area"]),
            connectgaps=True,
            hovertemplate="%{x|%b %Y}<br>Volume = %{y}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=trader_data["MM"],
            y=trader_data["pnl"].values,
            mode="lines",
            line=dict(width=1, shape='hvh', color=colors_context["normal line"]),
            name="Profit",
            connectgaps=True,
            hovertemplate="%{x|%b %Y}<br>PnL = %{y}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=trader_data["MM"],
            y=trader_data["dep"].values,
            mode="lines",
            line=dict(width=1, shape='hvh', color=colors_context["win"]),
            # fill="tozeroy",
            # fillcolor="rgb(100, 110, 250, .1)",
            name="Dep",
            connectgaps=True,
            hovertemplate="%{x|%b %Y}<br>Deposits = %{y}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=trader_data["MM"],
            y=trader_data["wd"].values,
            mode="lines",
            line=dict(width=1, shape='hvh', color=colors_context["lose"]),
            # fill="tozeroy",
            # fillcolor="rgb(250, 110, 100, .1)",
            name="WD",
            connectgaps=True,
            hovertemplate="%{x|%b %Y}<br>Withdrawals = %{y}<extra></extra>",
        ))


    st.plotly_chart(fig, use_container_width=True)

def render(start_dt_utc, end_dt_utc, all_assets, all_durations,
           sel_asset_ids, sel_duration_ids):
    st.title("Trading Platform Overview")

    # KPI Query
    sql_kpi = Path("queries/overview_kpi.sql").read_text()
    
    sql_kpi_params = {
        "start": start_dt_utc.date(),
        "end": end_dt_utc.date(),
        "all_assets": all_assets,
        "all_durations": all_durations,
        "assets": "','".join(map(str, sel_asset_ids)) or '0',
        "durations": "','".join(map(str, sel_duration_ids)) or '00:00'
    }
    df_kpi = read_sql(sql_kpi, params=sql_kpi_params)

    # kpi_row(df_kpi)

    col1, col2, col3, col4, col5 = st.columns([30, 30, 40, 40, 20])
    if df_kpi is not None and not df_kpi.empty:
        col1.metric("Total Trades", f"{df_kpi.loc[0, 'NUM_TRADES']:,.0f}")
        col2.metric("Total Traders", f"{df_kpi.loc[0, 'NUM_TRADERS']:,.0f}")
        col3.metric("Total Profit", f"¥{df_kpi.loc[0, 'SITE_PROFITS']:,.0f}")
        col4.metric("Trading Volume", f"¥{df_kpi.loc[0, 'SITE_VOLUME']:,.0f}")
        col5.metric("Margin", f"{df_kpi.loc[0, 'MARGIN']:.2f}%")

    # Top Traders
    sql_top_traders = Path("queries/top_traders.sql").read_text()

    sql_top_traders_params = {
        "limit_rows": 10,
        "pnl_threshold": 1000,
        "start": start_dt_utc.date(),
        "end": end_dt_utc.date(),
        "all_assets": all_assets,
        "all_durations": all_durations,
        "assets": "','".join(map(str, sel_asset_ids)) or '0',
        "durations": "','".join(map(str, sel_duration_ids)) or '00:00'       
    }
    
    df_top_traders = read_sql(sql_top_traders, params=sql_top_traders_params)
    df_prominents = df_top_traders[['PLAYER_NAME', 'PLAYER_ID', 'VOL', 'TRADER_PNL',
                                    'NUM_TRADES', 'LTV', 'NOTES']].drop_duplicates()

    st.subheader("Top Traders")
    c1, c2, c3, c4, c5, c6, c7 = st.columns([20, 20, 20, 20, 20, 20, 50])
    _ = (c1.write("Username"), c2.write("Player ID"), c3.write("Num Trades"),
         c4.write("Total Profit"), c5.write("Total Volume")), c6.write("LTV")
    for _, row in df_prominents.iterrows():
        c1, c2, c3, c4, c5, c6, c7 = st.columns([20, 20, 20, 20, 20, 20, 50], vertical_alignment='center', gap="small")

        with c1:
            # trader_link(row["PLAYER_ID"])
            # st.link_button(url =f"?page=Trader&trader_id={row['PLAYER_ID']}", label="Trader", type="tertiary")
            # st.markdown(f"[{row['PLAYER_NAME']}](?page=Trader&trader_id={row['PLAYER_ID']})")
            if st.button(row['PLAYER_NAME'], key=f"open_{row['PLAYER_ID']}"):
                go_to_trader(row['PLAYER_ID'])
        with c2:
            with st.popover(label=f"{row['PLAYER_ID']}"):
                selected_trader_data = df_top_traders.loc[df_top_traders["PLAYER_ID"] == row['PLAYER_ID']]
                _show_trader_history(selected_trader_data, start_dt_utc, end_dt_utc)
        # c2.write(f"{row['PLAYER_ID']}")
        c3.write(f"{row['NUM_TRADES']:,.0f}")
        c4.write(f"¥{row['TRADER_PNL']:,.0f}")
        c5.write(f"¥{row['VOL']:,.0f}")
        c6.write(f"¥{row['LTV']:,.0f}")
        c7.write(f"{row['NOTES']}")



        

