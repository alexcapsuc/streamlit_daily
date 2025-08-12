import streamlit as st
from pathlib import Path


from lib.db import read_sql
# from lib.ui import kpi_row


def trader_link(tid):
    st.page_link(
        f"?page=Trader&trader_id={tid}",   # relative URL within the app
        label=f"Open {tid}",               # looks/behaves like a link
        icon=":material/open_in_new:"      # optional
    )
    st.query_params.update(page="Trader", trader_id=str(tid))
    st.rerun()

def go_to_trader(tid):
    st.query_params.update(page="Trader", trader_id=str(tid))
    st.rerun()


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

    col1, col2, col3, col4, col5 = st.columns(5)
    if df_kpi is None or df_kpi.empty:
        vals = [0,0,0,0,0]
    else:
        vals = [
            df_kpi.loc[0, "NUM_TRADES"] or 0,
            df_kpi.loc[0, "NUM_TRADERS"] or 0,
            df_kpi.loc[0, "SITE_PROFITS"] or 0,
            df_kpi.loc[0, "SITE_VOLUME"] or 0,
            (df_kpi.loc[0, "MARGIN"] or 0) * 100
        ]
    col1.metric("Total Trades", f"${vals[0]:,.0f}")
    col2.metric("Total Traders", f"${vals[1]:,.0f}")
    col3.metric("Total Profit", f"${vals[3]:,.0f}")
    col4.metric("Trading Volume", f"${vals[2]:,.0f}")
    col5.metric("Margin", f"{vals[4]:.2f}%")

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

    df_top_traders["OPEN"] = df_top_traders["PLAYER_ID"].apply(
        lambda tid: f"?page=Trader&trader_id={tid}"
    )

    st.subheader("Top Traders")
    # st.dataframe(
    #     df_top_traders,
    #     use_container_width=True,
    #     hide_index=True,
    #     column_config={
    #         "PLAYER_ID": "Trader ID",
    #         "PLAYER_NAME": "Username",
    #         "NUM_TRADES": "Num Trades",
    #         "TRADER_PNL": "Total Profit",
    #         "VOL": "Total Volume",
    #         "OPEN": st.column_config.LinkColumn(
    #             "Open",
    #             display_text="Open Trader",
    #             help="Open Trader page with this ID"
    #         ),
    #     }
    # )
    
    # Display table rows with inline "Open" buttons
    c1, c2, c3, c4, c5, c6 = st.columns([3, 3, 3, 3, 3, 3])
    _ = (c1.write("Username"), c2.write("Player ID"), c3.write("Num Trades"),
         c4.write("Total Profit"), c5.write("Total Volume"))
    for _, row in df_top_traders.iterrows():
        # if c1.button(row["PLAYER_NAME"], key=f"open_{row['PLAYER_ID']}"):
        #     st.query_params.update(page="Trader", trader_id=str(row["PLAYER_ID"]))
        #     st.rerun()
        with c1:
            # trader_link(row["PLAYER_ID"]) 
            st.markdown(f"[{row['PLAYER_NAME']}](?page=Trader&trader_id={row['PLAYER_ID']})")
        c2.write(row["PLAYER_ID"])
        c3.write(f"{row['NUM_TRADES']:,.0f}")
        c4.write(f"¥{row['TRADER_PNL']:,.0f}")
        c5.write(f"¥{row['VOL']:,.0f}")
        with c6:
            if st.button("Open", key=f"open_{row['PLAYER_ID']}"):
                go_to_trader(row['PLAYER_ID'])

        

