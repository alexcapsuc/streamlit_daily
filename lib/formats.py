import streamlit as st
from datetime import datetime, time, timedelta


today = (datetime.today() + timedelta(hours=2)).date()

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