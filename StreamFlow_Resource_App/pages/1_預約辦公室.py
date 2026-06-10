import streamlit as st

from utils import AppInitializer, render_sidebar_status, render_resource_page

AppInitializer.setup()

st.title("🏢 預約辦公室")
st.caption("會議室預約、即時狀態、月曆與簽到管理")

render_sidebar_status()
render_resource_page("會議室")
