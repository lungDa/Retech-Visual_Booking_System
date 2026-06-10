import streamlit as st

from utils import AppInitializer, render_sidebar_status, load_data, RESOURCE_OPTIONS, TW_TZ
from datetime import datetime


st.set_page_config(
    page_title="智慧資源預約系統",
    page_icon="🏢",
    layout="wide",
)

AppInitializer.setup()

st.title("鋒霈環境科技股份有限公司")
st.caption("台中分公司雲端同步智慧資源預約系統")

render_sidebar_status()

st.write("---")
st.subheader("系統狀態概覽")

df = load_data()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("目前預約總筆數", len(df))

with col2:
    today_text = datetime.now(TW_TZ).strftime("%Y-%m-%d")
    today_count = len(df[df["booking_date"] == today_text]) if not df.empty else 0
    st.metric("今日預約筆數", today_count)

with col3:
    resource_count = sum(len(v) for v in RESOURCE_OPTIONS.values())
    st.metric("可管理資源數", resource_count)

st.info("請使用左側 Pages 選單進入：預約辦公室、預約公務車、未預約搜尋。")
