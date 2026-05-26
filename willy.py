import streamlit as st

import pandas as pd

from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide")

st.title(" 階段四終極完成版：GitHub 雲端同步 Trello 看板")

st.caption("授權標註：edit by 闕河正 | 完整功能版")

conn = st.connection("gsheets", type=GSheetsConnection)

df = conn.read(worksheet="Tasks", ttl="0")

# ==========================================

#  區塊一：上方新增任務輸入表單

# ==========================================

st.write("###  指派新任務")

with st.form("task_input_form", clear_on_submit=True):

    c_title, c_status, c_owner = st.columns([2, 1, 1]) # 運用權重比例切分表單

    with c_title:

        new_title = st.text_input(" 任務名稱", placeholder="輸入任務名稱...")

    with c_status:

        new_status = st.selectbox(" 狀態", ["To Do", "In Progress", "Done"])

    with c_owner:

        new_owner = st.text_input(" 負責人", placeholder="誰來負責...")

    

    submit_btn = st.form_submit_button("確認指派並同步雲端")

if submit_btn and new_title and new_owner:

    new_data = {"title": new_title, "status": new_status, "owner": new_owner}

    new_row = pd.DataFrame([new_data])

    #  核心安全：新版 Python 廢棄 .append()，在雲端必須改用 pd.concat() 進行表格拼接

    updated_df = pd.concat([df, new_row], ignore_index=True)

    conn.update(worksheet="Tasks", data=updated_df)

    st.success(" 資料已跨越限制，成功同步寫入 Google 試算表！")

    st.rerun() # 強制網頁自我重整，重新讀取，讓新卡片亮起來

st.write("---")

# ==========================================

#  區塊二：下方 Trello 三縱欄畫布與卡片渲染

# ==========================================

st.write("###  看板動態狀態監控")

trello_col1, trello_col2, trello_col3 = st.columns(3)

#  【第一欄：To Do】

with trello_col1:

    st.markdown("### <span style='color:red'> To Do (待辦)</span>", unsafe_allow_html=True)

    todo_list = df[df["status"] == "To Do"] # 階段三學的濾網分流

    

    if not todo_list.empty:

        for idx, row in todo_list.iterrows(): # 階段 3.5 學的迴圈點名

            #  呼叫 border=True，幫每筆點名到的資料揉出一個精緻卡片外框

            with st.container(border=True):

                st.write(f"** {row['title']}**")      # 粗體印出任務名稱

                st.caption(f"負責人: {row['owner']}")   # 灰色小字印出負責人

    else:

        st.info("暫無待辦任務")

#  【第二欄：In Progress】

with trello_col2:

    st.markdown("### <span style='color:orange'> In Progress (執行中)</span>", unsafe_allow_html=True)

    ip_list = df[df["status"] == "In Progress"]

    

    if not ip_list.empty:

        for idx, row in ip_list.iterrows():

            with st.container(border=True):

                st.write(f"** {row['title']}**")

                st.caption(f"負責人: {row['owner']}")

    else:

        st.info("暫無執行中任務")

#  【第三欄：Done】

with trello_col3:

    st.markdown("### <span style='color:green'> Done (已完成)</span>", unsafe_allow_html=True)

    done_list = df[df["status"] == "Done"]

    

    if not done_list.empty:

        for idx, row in done_list.iterrows():

            with st.container(border=True):

                #  貼心小視覺：用 文字 幫已完成的任務加上刪除線，更有完工的體感！

                st.write(f"** {row['title']}**")

                st.caption(f"負責人: {row['owner']}")

    else:

        st.info("暫無已完成任務")
