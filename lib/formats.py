import streamlit as st
from datetime import datetime, time, timedelta
from pyecharts.commons.utils import JsCode


today = (datetime.today() + timedelta(hours=2)).date()

ALL = "__ALL__"

sections = ["Overview", "Trader"]
default_section = sections[0]

date_ranges = {
    "Today": [today, today],
    "This Week": [today - timedelta(days=today.weekday()), today],
    "This Month": [today.replace(day=1), today],
    "This Year": [today.replace(month=1, day=1), today]
}
durations = ['00:00:15', '00:00:30', '00:01:00', '00:03:00', '00:05:00',
             '00:15:00', '01:00:00', 'daily']
assets = {
    1: "USD/JPY"
}

colors_all = {
    "dark": {
        "background_area": "rgb(50, 50, 50, .1)",
        "normal line": "white",
        "normal reverted line": "black",
        "win": "green",
        "lose": "red"
    },
    "light": {
        "background_area": "rgb(220, 220, 220, .1)",
        "normal line": "black",
        "normal reverted line": "white",
        "win": "green",
        "lose": "red"
    }
}

colors_context = colors_all["dark" if st.context.theme.type == "dark" else "light"]

