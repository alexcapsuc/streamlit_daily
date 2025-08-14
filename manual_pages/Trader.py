import streamlit as st
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta


from lib.db import read_sql
from queries.trader_sql import queries


def render(start_dt_utc: datetime, end_dt_utc: datetime, selected_trader: str):
    """
    Constructs content of the page Trader
    :param start_dt_utc: Start of the period of interest
    :param end_dt_utc: End of the period of interest
    :param selected_trader: Trader ID as text. Later will add support for Username
    :return:
    """
    st.title("Trader Detail Overview")
    if "keep_elements" not in st.session_state:
        st.session_state.keep_elements = []

    trader_id = st.text_input(
        "Enter Trader ID, Email, or Username",
        value=selected_trader
    )
    if not trader_id:
        st.info("Please enter a trader to view details.")
        return

    sql_profile = Path("queries/trader_profile.sql").read_text()
    sql_profile = sql_profile.format(
        trader_id=trader_id,
        start=start_dt_utc.date(),
        end=end_dt_utc.date()
    )
    df_profile = read_sql(sql_profile)

    st.dataframe(df_profile, use_container_width=True)

    if st.button("Show All Trades"):
        show_trades(start_dt_utc, end_dt_utc, selected_trader)

    if st.button("Show Trades on Graph") or "Trades Chart" in st.session_state.keep_elements:
        st.session_state.keep_elements.append("Trades Chart")
        plot_trades(start_dt_utc, end_dt_utc, selected_trader)

def show_trades(start_dt_utc, end_dt_utc, selected_trader):
    trades = get_trades(start_dt_utc, end_dt_utc, selected_trader)
    st.dataframe(trades)

def get_trades(start_dt_utc, end_dt_utc, selected_trader):
    all_trades_sql = queries['all_trades']
    all_trades_sql_params = {
        "trader_id": selected_trader,
        "start_time": start_dt_utc,
        "end_time": end_dt_utc
    }
    trades = read_sql(all_trades_sql, params=all_trades_sql_params)
    return trades

def plot_trades(start_dt_utc, end_dt_utc, selected_trader,
                grouping_gap_threshold=60):
    trades =  get_trades(start_dt_utc, end_dt_utc, selected_trader)
    if trades.empty:
        st.info("No trades found for the selected filters.")
        return

    trade_groups = _group_trades(
        trades=trades,
        grouping_gap_threshold=timedelta(seconds=grouping_gap_threshold)
    )
    num_trade_groups = trade_groups["group_label"].max()
    st.caption(f"Found {num_trade_groups} trade group(s). Grouping margin: {grouping_gap_threshold}s.")

    idx_key = "trade_group__idx"
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 1

    _build_group_controls(idx_key, num_trade_groups)

    cur_group = trade_groups.loc[trade_groups["group_label"] == st.session_state[idx_key]]
    asset_id = int(cur_group["ASSET_ID"].unique().squeeze())  # ToDo: do we need to check it's unique?

    g_from = cur_group["TRADING_TIME"].min() - timedelta(seconds=grouping_gap_threshold)
    g_to = cur_group["CLOSE_TIME"].max() + timedelta(seconds=grouping_gap_threshold)

    # ---- Fetch ticks for this group (lazy)
    ticks_sql = queries["rtd_for_trades"]
    ticks_sql_params = {
        "asset_id": asset_id,
        "start_ts": g_from,
        "end_ts": g_to
    }
    ticks = read_sql(ticks_sql, params=ticks_sql_params)

    st.markdown(f"Group {st.session_state[idx_key]} / {num_trade_groups} &nbsp;&nbsp; "
               f"• &nbsp;&nbsp; Asset {st.session_state['assets_dict'][asset_id]} &nbsp;&nbsp; "
               f"• &nbsp;&nbsp; Window {g_from} → {g_to} &nbsp;&nbsp; • &nbsp;&nbsp; {cur_group.shape[0]} Trade(s)")

    _build_trades_chart(cur_group, ticks)

def _build_trades_chart(trades: pd.DataFrame, ticks: pd.DataFrame, engine="ECharts"):
    """
    Constructs the actual graph. Switch to use ECharts / Plotly / other
    :param trades: DataFrame with trades (columns: )
    :param ticks: DataFrame with all prices (columns: )
    :param engine: ECharts or Plotly
    :return:
    """
    if engine.lower() == "plotly":
        _build_chart_plotly(trades, ticks)
    else:
        _build_chart_echarts(trades, ticks)

def _build_chart_plotly(trades: pd.DataFrame, ticks: pd.DataFrame):
    import plotly.graph_objects as go
    from streamlit_plotly_events import plotly_events

    fig = go.Figure()

    # Plot the price line
    if not ticks.empty:
        fig.add_trace(
            go.Scatter(
                x=ticks["TIMESTAMP"],
                y=ticks["PRICE"],
                mode="lines",
                name="Price",
                line=dict(width=1),
                hoverinfo="x+y"
            )
        )

    # Plot trades
    if not trades.empty:
        trades = trades.sort_values("TRADING_TIME")
        side_colors = {"BUY": "#2e7d32", "SELL": "#c62828"}
        colors = trades["SIDE"].map(lambda s: side_colors.get(s, "#1976d2"))

        sizes = trades["PROFIT"].fillna(0).abs().clip(lower=6, upper=18)

        hover_texts = (
            "Time: " + trades["TRADING_TIME"].astype(str) +
            "<br>Price: " + trades["TRADING_STRIKE"].astype(str) +
            "<br>Side: " + trades["SIDE"] +
            "<br>Volume: " + trades["VOLUME"].astype(str) +
            "<br>PnL: " + trades["PROFIT"].astype(str)
        )

        fig.add_trace(
            go.Scatter(
                x=trades["TRADING_TIME"],
                y=trades["TRADING_STRIKE"],
                mode="markers",
                name="Trades",
                marker=dict(
                    size=sizes,
                    color=colors,
                    opacity=0.8,
                    line=dict(width=0.5, color="black"),
                ),
                hovertext=hover_texts,
                customdata=trades[["TRADING_TIME", "TRADING_STRIKE", "SIDE", "VOLUME", "PROFIT", "DURATION", "ASSET_ID"]],
            )
        )

    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Price",
        height=500,
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=40, b=40),
    )

    # Use streamlit-plotly-events to capture clicks
    selected_points = plotly_events(fig, click_event=True, hover_event=False, select_event=False, key="plotly-trade-click")

    # Handle click event
    if selected_points:
        selected = selected_points[0]  # Get first click
        custom_data = selected["customdata"]
        st.info(f"Clicked Trade:\n\n• Time: {custom_data[0]}\n• Price: {custom_data[1]}\n• Side: {custom_data[2]}\n• Volume: {custom_data[3]}\n• PnL: {custom_data[4]}\n• Duration ID: {custom_data[5]}\n• Asset ID: {custom_data[6]}")

    # Show table + download
    with st.expander("Show trades in this group"):
        if not trades.empty:
            st.dataframe(
                trades[["TRADING_TIME", "SIDE", "TRADING_STRIKE", "VOLUME", "PROFIT", "DURATION", "ASSET_ID"]],
                use_container_width=True,
                hide_index=True
            )
            st.download_button(
                "Download CSV",
                trades.to_csv(index=False).encode("utf-8"),
                file_name=f"trader_{-1}_asset_{-1}_group_{-1}.csv",
                mime="text/csv"
            )
        else:
            st.write("No trades in this group.")

def _build_chart_echarts(trades: pd.DataFrame, ticks: pd.DataFrame):
    """
    Constructs the actual graph with ECharts
    :param trades: DataFrame with trades (columns: )
    :param ticks: DataFrame with all prices (columns: )
    :return:
    """
    from streamlit_echarts import st_echarts
    from pyecharts.commons.utils import JsCode

    def _to_iso(s: pd.Series) -> pd.Series:
        # ensure naive UTC ISO strings
        s = pd.to_datetime(s, utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
        # return s.dt.strftime("%Y-%m-%dT%H:%M:%S")
        return s.astype('int64') / 10**9

    # Prepare datasets for ECharts (use array order to carry extra fields to tooltip)
    # ticks dataset [TIMESTAMP, PRICE]
    ds_ticks = []
    if not ticks.empty:
        ticks = ticks.sort_values("TIMESTAMP").reset_index()
        for col_name in ["TIMESTAMP", "SENDER_TIMESTAMP"]:
            ticks[col_name] = _to_iso(ticks[col_name])
        ticks["PRICE"] = ticks["PRICE"].astype(float)
        ds_ticks = ticks[["TIMESTAMP", "PRICE"]].values.tolist()

    # trades dataset [TRADING_TIME, TRADING_STRIKE, SIDE, VOLUME, PROFIT, DURATION, ASSET_ID]
    ds_trades = []
    if not trades.empty:
        # times
        trades = trades.sort_values("TRADING_TIME")
        for col_name in ["TRADING_TIME", "CLOSE_TIME"]:
            trades[col_name] = _to_iso(trades[col_name])

        # numerics
        trades["TRADING_STRIKE"] = trades["TRADING_STRIKE"].astype(float)
        trades["CLOSE_STRIKE"] = trades["CLOSE_STRIKE"].astype(float)
        trades["VOLUME"] = trades["VOLUME"].astype(float)
        trades["PROFIT"] = trades["PROFIT"].astype(float)
        trades["color"] = 'green'
        trades.loc[trades["SIDE"] == "SELL", "color"] = 'red'

        ds_trades = trades[["TRADING_TIME","TRADING_STRIKE","CLOSE_TIME","CLOSE_STRIKE",
                            "SIDE","VOLUME","PROFIT","DURATION","ASSET_ID","color"]].values.tolist()

    option = {
        "animation": False,
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "legend": {"data": ["Price", "Open", "Close"]},
        "grid": {"left": 45, "right": 20, "top": 30, "bottom": 60},
        "dataZoom": [
            {"type": "inside", "xAxisIndex": 0},
            {"type": "slider", "xAxisIndex": 0},
        ],
        "xAxis": {
            "type": "time",
            "axisLabel": {"rotate": 0},
        },
        "yAxis": [
            {"type": "value", "scale": True, "axisLabel": {"formatter": "{value}"}},
        ],
        "dataset": [
            {"id": "ticks",  "source": ds_ticks,  "dimensions": ["ts","price"]},
            {"id": "trades", "source": ds_trades, "dimensions": ["tt","tstrike","ct","cstrike","side","vol","pnl","dur","asset"]},
        ],
        "series": [
            {
                "name": "Price",
                "type": "line",
                "datasetIndex": 0,
                "encode": {"x": "ts", "y": "price"},
                "symbol": "none",
                "step": "start",
                "lineStyle": {"width": 1}
            },
            {   # open markers
                "name": "Open",
                "type": "scatter",
                "datasetIndex": 1,
                "encode": {"x": "tt", "y": "tstrike"},
                "symbol": "pin",
                "symbolSize":"""--x_x--0_0--
                        function (data) { 
                            return Number(Math.sqrt(data[5] / 1000) * 5).toFixed(2);
                        }--x_x--0_0--
                    """.replace('\n', ' '),
                "itemStyle": {
                    "color": """--x_x--0_0--
                        function (params) { 
                            const side = params.data[4]; 
                            if (side === 'BUY')  
                                return 'green'; 
                            if (side === 'SELL') 
                                return 'red'; 
                            return '#1976d2'; 
                        }--x_x--0_0--
                    """.replace('\n', ' ')
                },
                "tooltip": {
                    "formatter": """--x_x--0_0--
                        function (params) {
                            return 'Close ' 
                                + '<br/>Strike: ' + params.data[3]
                                + '<br/>Side: ' + params.data[4]
                                + '<br/>Vol: ' + params.data[5]
                                + '<br/>PnL: ' + params.data[6];
                        }--x_x--0_0--
                    """.replace('\n', ' ')
                }
            },
            {   # close markers
                "name": "Close",
                "type": "scatter",
                "datasetIndex": 1,
                "encode": {"x": "ct", "y": "cstrike"},
                "symbol": "pin",
                "symbolKeepAspect": True,
                "symbolSize": 20,
                "itemStyle": {
                    "color": "blue",
                    "opacity": 0.85,
                    "borderColor": "#000",
                    "borderWidth": 0.5
                },
                "tooltip": {
                    "formatter": JsCode("function (params) {return 'Hello Tooltip!';}").js_code
                }
            }
        ],
    }

    with st.expander("ECharts Options"):
        st.write(option)

    # Render chart + capture click/hover events
    events = {
        "click": "function(params) { return params; }",
        "mouseover": "function(params) { return params; }"
    }

    with st.expander('Sample Data'):
        st.write("Trades rows:", len(ds_trades), "example:", ds_trades[:2])
        st.write("Ticks rows:", len(ds_ticks), "example:", ds_ticks[:2])

    # ev = st_echarts_event(option, events=events, height="420px", key=f"trade_group_chart")
    ev = st_echarts(option, events=events, height="420px", key="tg_chart")
    if isinstance(ev, dict) and ev.get("type") == "click":
        st.write("Clicked:", ev)  # handle your click here

    # Show event info / drive navigation
    if ev and "seriesName" in ev:
        if ev["seriesName"] == "Trades":
            # ev.data will be like [TS, PRICE, SIDE, VOLUME, PROFIT, DURATION_ID, ASSET_ID]
            st.info(f"Clicked trade • ts={ev['data'][0]} • price={ev['data'][1]} • side={ev['data'][2]} • PnL={ev['data'][4]}")
        else:
            st.caption(f"Hovered {ev['seriesName']} at x={ev.get('value')}")

    # Optional: table + download for the group
    with st.expander("Show trades in this group"):
        if not trades.empty:
            st.dataframe(trades[["SIDE","TRADING_TIME","TRADING_STRIKE","CLOSE_TIME","CLOSE_STRIKE",
                                 "VOLUME","PROFIT","DURATION","ASSET_ID"]], use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV",
                trades.to_csv(index=False).encode("utf-8"),
                file_name=f"trader_{-1}_asset_{-1}_group_{-1}.csv",
                mime="text/csv"
            )
        else:
            st.write("No trades in this group.")

def _build_group_controls(idx_key: str, num_trade_groups: int):
    """
    Buttons Prev, Next and integer input for desired group
    :return:
    """
    prev_col, val_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        st.write("\n")
        if st.button("◀ Prev", disabled=st.session_state[idx_key] <= 1, key="trade_group_prev"):
            st.session_state[idx_key] -= 1
    with next_col:
        st.write("\n")
        if st.button("Next ▶", disabled=st.session_state[idx_key] >= int(num_trade_groups), key="trade_group_next"):
            st.session_state[idx_key] += 1
    with val_col:
        st.number_input(
            "Group #", min_value=1, max_value=num_trade_groups,
            value=st.session_state[idx_key],
            label_visibility="hidden",
            step=1, key=idx_key,
        )





def _get_rtd(trades):
    pass

def _group_trades(trades: pd.DataFrame, grouping_gap_threshold: timedelta) -> pd.DataFrame:
    """
    Adds a 'group_label' column to df where each asset/time-gap cluster gets a unique ID.
    Returns the modified DataFrame (sorted).
    """
    if trades.empty:
        trades["group_label"] = []
        return trades

    # Ensure proper sort
    trades = trades.sort_values(["ASSET_ID", "TRADING_TIME"]).reset_index(drop=True)

    # Calculate time difference from previous row
    trades["time_diff"] = trades["TRADING_TIME"].diff()

    # Also check if asset changes compared to previous row
    trades["asset_change"] = trades["ASSET_ID"].ne(trades["ASSET_ID"].shift())

    # Boolean: does this row start a new group?
    trades["new_group"] = trades["asset_change"] | (trades["time_diff"] > grouping_gap_threshold)

    # Assign group numbers
    trades["group_label"] = trades["new_group"].cumsum()

    # Drop helper cols
    trades = trades.drop(columns=["time_diff", "asset_change", "new_group"])

    return trades