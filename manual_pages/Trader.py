import streamlit as st
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pyarrow.lib


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
                grouping_gap_threshold=60, engine='plotly'):
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

    _build_trades_chart(cur_group, ticks, engine)

def _to_iso(s: pd.Series) -> pd.Series:
    # ensure naive UTC ISO strings
    s = pd.to_datetime(s, utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    return s.dt.strftime("%Y-%m-%dT%H:%M:%S")

def _to_epoch_ms(s: pd.Series) -> pd.Series:
    # pandas datetime -> int64 ns -> int ms (Python ints for JSON)
    ms = (pd.to_datetime(s, utc=True).astype("int64") // 10 ** 6)
    # ensure Python int, not numpy int64 (better for JSON)
    return ms.astype("int64").map(int)

def _to_dt_from_ms(ms: pd.Series) -> pd.Series:
    # epoch ms -> pandas datetime (UTC, tz-naive for Plotly)
    return pd.to_datetime(ms, unit="ms", utc=True).dt.tz_convert("UTC").dt.tz_localize(None)

def _prep_for_chart(trades: pd.DataFrame, ticks: pd.DataFrame):
    """
    Returns:
      ticks_dt  : DataFrame [TS, PRICE] (datetime)
      trades_dt : DataFrame with columns:
                  TT (open time dt), TSTRIKE, CT (close time dt), CSTRIKE,
                  SIDE, VOL, PNL, DUR, ASSET, SIZE (sqrt |pnl| scaling), COLOR
    """
    # --- ticks
    ticks_dt = pd.DataFrame(columns=["TIMESTAMP","PRICE"])
    if not ticks.empty:
        ticks_dt = ticks.copy()
        ticks_dt["PRICE"] = ticks_dt["PRICE"].astype(float)
        ticks_dt["PRICE"] = pd.to_numeric(ticks_dt["PRICE"], errors="coerce")
        ticks_dt = ticks_dt[["TIMESTAMP","PRICE"]].sort_values("TIMESTAMP").reset_index()

    # --- trades
    trades_dt = pd.DataFrame(columns=["TRADING_TIME","TRADING_STRIKE","CLOSE_TIME","CLOSE_STRIKE",
                                      "SIDE","VOLUME","PROFIT","DURATION","ASSET_ID","SIZE","COLOR"])
    if not trades.empty:
        # numerics & fields
        trades_dt = trades.copy()
        trades_dt["TRADING_STRIKE"] = trades_dt["TRADING_STRIKE"].astype(float)
        trades_dt["CLOSE_STRIKE"] = trades_dt["CLOSE_STRIKE"].astype(float)
        trades_dt["VOLUME"] = trades_dt["VOLUME"].astype(float)
        trades_dt["PROFIT"] = trades_dt["PROFIT"].astype(float)

        # size by |pnl| (tune scale)
        trades_dt["SIZE"] = 10 + 4 * np.sqrt(trades_dt["VOLUME"] / 1000)
        trades_dt["SIZE"] = trades_dt["SIZE"].clip(lower=5, upper=100)

        # color by side
        trades_dt["COLOR"] = np.where(trades_dt["SIDE"].astype(str).str.upper().eq("BUY"), "#2e7d32",
                                   np.where(trades_dt["SIDE"].astype(str).str.upper().eq("SELL"),
                                            "#c62828", "#1976d2"))

        trades_dt = trades_dt.sort_values(["TRADING_TIME", "CLOSE_TIME"])

        for col in ["TRADING_STRIKE", "CLOSE_STRIKE", "VOLUME", "PROFIT", "ASSET_ID", "SIZE"]:
            # trades_dt[col] = trades_dt[col].astype(str)
            trades_dt[col] = pd.to_numeric(trades_dt[col], errors="coerce")

    return trades_dt, ticks_dt

def _build_trades_chart(trades: pd.DataFrame, ticks: pd.DataFrame, engine):
    """
    Constructs the actual graph. Switch to use ECharts / Plotly / other
    :param trades: DataFrame with trades (columns: )
    :param ticks: DataFrame with all prices (columns: )
    :param engine: ECharts or Plotly
    :return:
    """
    if engine.lower() == "plotly":
        try:
            _build_chart_plotly(trades, ticks)
        except pyarrow.lib.ArrowInvalid as err:
            st.write(f"PyArrow Error: {err}")

    else:
        _build_chart_echarts(trades, ticks)

def _build_chart_plotly(trades: pd.DataFrame, ticks: pd.DataFrame):
    import plotly.graph_objects as go
    # Optional: capture clicks (pip install streamlit-plotly-events)
    try:
        from streamlit_plotly_events import plotly_events
    except Exception:
        plotly_events = None

    trades_dt, ticks_dt = _prep_for_chart(trades, ticks)
    # ticks_dt = ticks_dt.astype(str)

    with st.expander('Sample Data'):
        st.write("Trades rows:", trades_dt.shape[0], "example:", trades_dt.head())
        st.write("Ticks rows:", ticks_dt.shape[0], "example:", ticks_dt.head())

    fig = go.Figure()

    # Price line
    if not ticks_dt.empty:
        st.write(ticks_dt.dtypes.astype(str).rename("dtype").to_frame())
        fig.add_trace(go.Scatter(
            x=ticks_dt["TIMESTAMP"], y=[price for price in ticks_dt["PRICE"].values],
            mode="lines", name="Price",
            line=dict(width=1),
            hovertemplate="%{x|%Y-%m-%d %H:%M:%S.%3f}<br>Price=%{y}<extra></extra>",
        ))

    # Open markers
    if not trades_dt.empty:
        fig.add_trace(go.Scatter(
            x=trades_dt["TRADING_TIME"], y=[strike for strike in trades_dt["TRADING_STRIKE"].values],
            mode="markers", name="Open",
            marker=dict(color=trades_dt["COLOR"],
                        # size=[float(val) for val in trades_dt["SIZE"].values],
                        line=dict(width=0.5, color="black"), opacity=0.9, symbol="circle"),
            customdata=np.stack([
                trades_dt["SIDE"], trades_dt["VOLUME"], trades_dt["PROFIT"],
                trades_dt["DURATION"], trades_dt["ASSET_ID"], trades_dt["CLOSE_TIME"], trades_dt["CLOSE_STRIKE"]
            ], axis=1),
            hovertemplate=(
                "Open %{x|%Y-%m-%d %H:%M:%S.%3f}"
                "<br>Strike=%{y}"
                "<br>Side=%{customdata[0]}"
                "<br>Vol=%{customdata[1]:,.0f}"
                "<br>PnL=%{customdata[2]:,.2f}"
                "<extra></extra>"
            ),
        ))

        # Close markers (triangle)
        fig.add_trace(go.Scatter(
            x=trades_dt["CLOSE_TIME"], y=[strike for strike in trades_dt["CLOSE_STRIKE"].values],
            mode="markers", name="Close",
            marker=dict(color=trades_dt["COLOR"],
                        # size=10,
                        line=dict(width=0.5, color="black"), opacity=0.9, symbol="triangle-up"),
            customdata=np.stack([
                trades_dt["SIDE"], trades_dt["VOLUME"], trades_dt["PROFIT"],
                trades_dt["DURATION"], trades_dt["ASSET_ID"], trades_dt["TRADING_TIME"], trades_dt["TRADING_STRIKE"]
            ], axis=1),
            hovertemplate=(
                "Close %{x|%Y-%m-%d %H:%M:%S.%3f}"
                "<br>Strike=%{y}"
                "<br>Side=%{customdata[0]}"
                "<br>Vol=%{customdata[1]:,.0f}"
                "<br>PnL=%{customdata[2]:,.2f}"
                "<extra></extra>"
            ),
        ))

    # Layout with ms tick formatting + range slider
    fig.update_layout(
        height=520,
        margin=dict(l=40, r=20, t=30, b=40),
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(
            title="Time",
            showspikes=True,
            spikemode="across",
            rangeslider=dict(visible=True),
            tickformat="%Y-%m-%d %H:%M:%S.%3f",  # millisecond labels
            tickformatstops=[
                dict(dtickrange=[None, 1000], value="%H:%M:%S.%3f"),
                dict(dtickrange=[1000, 60000], value="%H:%M:%S.%3f"),
                dict(dtickrange=[60000, None], value="%Y-%m-%d %H:%M:%S"),
            ],
        ),
        yaxis=dict(title="Price", showspikes=True, spikemode="toaxis+across"),
    )

    # Render (with optional click capture)
    if plotly_events:
        selected = plotly_events(fig, click_event=True, hover_event=False, select_event=False, key="plotly-trade-click")
        if selected:
            p = selected[0]
            # Example: p["pointIndex"], p["curveNumber"], p["x"], p["y"], p["customdata"]
            st.info(f"Clicked • x={p.get('x')} • y={p.get('y')} • data={p.get('customdata')}")
    else:
        st.plotly_chart(fig, use_container_width=True)

def _build_chart_echarts(trades: pd.DataFrame, ticks: pd.DataFrame):
    """
    Constructs the actual graph with ECharts
    :param trades: DataFrame with trades (columns: )
    :param ticks: DataFrame with all prices (columns: )
    :return:
    """
    from streamlit_echarts import st_echarts

    # Prepare datasets for ECharts (use array order to carry extra fields to tooltip)
    # ticks dataset [TIMESTAMP, PRICE]
    ds_ticks = []
    if not ticks.empty:
        ticks = ticks.sort_values("TIMESTAMP").reset_index()
        for col_name in ["TIMESTAMP", "SENDER_TIMESTAMP"]:
            ticks[col_name] = _to_epoch_ms(ticks[col_name])
        ticks["PRICE"] = ticks["PRICE"].astype(float)
        ds_ticks = ticks[["TIMESTAMP", "PRICE"]].values.tolist()

    # trades dataset [TRADING_TIME, TRADING_STRIKE, SIDE, VOLUME, PROFIT, DURATION, ASSET_ID]
    ds_trades = []
    if not trades.empty:
        # times
        trades = trades.sort_values("TRADING_TIME")
        for col_name in ["TRADING_TIME", "CLOSE_TIME"]:
            trades[col_name] = _to_epoch_ms(trades[col_name])

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
        # "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        # "tooltip": {
        #     "trigger": "item",          # ← IMPORTANT: 'item', not 'axis'
        #     "confine": True             # avoids clipping in Streamlit iframe
        # },
        "legend": {"data": ["Price", "Open", "Close"]},
        "grid": {"left": 45, "right": 20, "top": 30, "bottom": 70},
        "dataZoom": [
            {"type": "inside", "xAxisIndex": 0},
            {"type": "slider", "xAxisIndex": 0},
        ],
        "xAxis": {
            "type": "time",
            "axisLabel": {
                "rotate": 0,
                "formatter": """--x_x--0_0--
                    function (value) {
                        var tt = new Date(value);
                        return tt.toISOString().slice(0, 23).replace("T", " ")
                    }--x_x--0_0--
                """.replace('\n', ' ')
            }
        },
        "yAxis": [
            {"type": "value", "scale": True, "axisLabel": {"formatter": "{value}"}},
        ],
        "dataset": [
            {"id": "ticks", "source": ds_ticks, "dimensions": ["ts","price"]},
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
                "lineStyle": {"width": 1},
            },
            {   # open markers
                "name": "Open",
                "type": "scatter",
                "datasetIndex": 1,
                "encode": {"x": "tt", "y": "tstrike"},
                "symbol": "pin",
                "symbolSize":"""--x_x--0_0--
                        function (data) { 
                            return Number(10 + 3 * Math.sqrt(data[5] / 1000)).toFixed(2);
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
                    "trigger": "item",
                    "formatter": """--x_x--0_0--
                        function (params) {
                            var tt = new Date(params.data[0]);
                            return 'Open: ' + tt.toISOString().slice(0, 23).replace("T", " ")
                                + '<br/>Strike: ' + params.data[1]
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
                    "trigger": "item",
                    "formatter": """--x_x--0_0--
                        function (params) {
                            var tt = new Date(params.data[2]);
                            return 'Close: ' + tt.toISOString().slice(0, 23).replace("T", " ")
                                + '<br/>Strike: ' + params.data[3]
                                + '<br/>Side: ' + params.data[4]
                                + '<br/>Vol: ' + params.data[5]
                                + '<br/>PnL: ' + params.data[6];
                        }--x_x--0_0--
                    """.replace('\n', ' ')
                }
            }
        ],
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
            # "formatter": JsCode(
            #     """--x_x--0_0--
            #         function (value) {
            #             var tt = new Date(value);
            #             return tt.toISOString().slice(0, 23).replace("T", " ")
            #         }--x_x--0_0--
            #     """
            # ).js_code.replace('\n', ' ')
        }
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