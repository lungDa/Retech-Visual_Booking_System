import streamlit as st

from utils import AppInitializer, render_sidebar_status, render_unreserved_search

AppInitializer.setup()

st.title("🔍 未預約搜尋")
st.caption("依日期、時段與資源類型搜尋可預約資源")

render_sidebar_status()
render_unreserved_search()
