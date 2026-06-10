import streamlit as st

from utils import AppInitializer, render_sidebar_status, render_resource_page

AppInitializer.setup()

st.title("🚗 預約公務車")
st.caption("公務車預約、即時狀態、月曆與簽到管理")

render_sidebar_status()
render_resource_page("公務車")
