import streamlit as st

 from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide")

st.title(" 階段 3.5：iterrows 迴圈解構點名現場實驗") 

st.caption("授權標註：edit by 闕河正")

conn = st.connection("gsheets", type=GSheetsConnection) 

df = conn.read(worksheet="Tasks", ttl="0")

todo_df = df[df["owner"] == "python"]

st.write("---") 

st.write("###  進入 Python 迴圈自動化點名現場：")

for idx, row in todo_df.iterrows(): 

    # 每一圈，我們用一個小紅框（st.error）來代表一次巡迴 

    st.error(f" 迴圈巡邏：目前點名點到了第 {idx} 行的任務：") 

    st.write(f" ➔ 【title 任務名稱】這一格拿到了： {row['title']}") 

    st.write(f" ➔ 【owner 負責人】這一格拿到了： {row['owner']}")
