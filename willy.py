import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date, datetime

# ==========================================
# 基本設定
# ==========================================
st.set_page_config(layout="wide")

st.title("階段四終極完成版：GitHub 雲端同步 Trello 看板")
st.caption("授權標註：edit by 闕河正 | 完整功能版")

conn = st.connection("gsheets", type=GSheetsConnection)

WORKSHEET_NAME = "Tasks"

# ==========================================
# 讀取資料
# ==========================================
try:
    df = conn.read(worksheet=WORKSHEET_NAME, ttl=0)
except PermissionError:
    st.error("Google Sheet 權限不足")
    st.info("請到 Google Sheet 共用設定，把 Service Account Email 加入為檢視者或編輯者。")
    st.stop()
except Exception as e:
    st.error("讀取 Google Sheet 失敗")
    st.exception(e)
    st.stop()

# ==========================================
# 自動補齊欄位
# ==========================================
required_columns = {
    "id": "",
    "title": "",
    "status": "To Do",
    "owner": "",
    "priority": "一般",
    "due_date": "",
    "note": "",
    "created_at": ""
}

for col, default_value in required_columns.items():
    if col not in df.columns:
        df[col] = default_value

df = df[list(required_columns.keys())]

# 空資料處理
df = df.fillna("")

# 如果舊資料沒有 id，自動補 id
changed = False
for i in df.index:
    if str(df.at[i, "id"]).strip() == "":
        df.at[i, "id"] = f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}"
        changed = True

if changed:
    conn.update(worksheet=WORKSHEET_NAME, data=df)

# ==========================================
# 工具函式
# ==========================================
def save_data(dataframe):
    conn.update(worksheet=WORKSHEET_NAME, data=dataframe)

def priority_icon(priority):
    if priority == "高":
        return "🔴 高"
    elif priority == "中":
        return "🟠 中"
    elif priority == "低":
        return "🟢 低"
    return "⚪ 一般"

# ==========================================
# 上方統計
# ==========================================
st.write("### 任務總覽")

total_count = len(df)
todo_count = len(df[df["status"] == "To Do"])
progress_count = len(df[df["status"] == "In Progress"])
done_count = len(df[df["status"] == "Done"])

m1, m2, m3, m4 = st.columns(4)

m1.metric("全部任務", total_count)
m2.metric("待辦", todo_count)
m3.metric("執行中", progress_count)
m4.metric("已完成", done_count)

st.write("---")

# ==========================================
# 新增任務
# ==========================================
st.write("### 指派新任務")

with st.form("task_input_form", clear_on_submit=True):
    c_title, c_status, c_owner = st.columns([2, 1, 1])

    with c_title:
        new_title = st.text_input("任務名稱", placeholder="輸入任務名稱...")

    with c_status:
        new_status = st.selectbox("狀態", ["To Do", "In Progress", "Done"])

    with c_owner:
        new_owner = st.text_input("負責人", placeholder="誰來負責...")

    c_priority, c_due, c_note = st.columns([1, 1, 2])

    with c_priority:
        new_priority = st.selectbox("優先度", ["一般", "低", "中", "高"])

    with c_due:
        new_due_date = st.date_input("期限", value=date.today())

    with c_note:
        new_note = st.text_input("備註", placeholder="補充說明...")

    submit_btn = st.form_submit_button("確認指派並同步雲端")

if submit_btn:
    if not new_title.strip():
        st.warning("請輸入任務名稱")
    elif not new_owner.strip():
        st.warning("請輸入負責人")
    else:
        new_data = {
            "id": f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": new_title,
            "status": new_status,
            "owner": new_owner,
            "priority": new_priority,
            "due_date": str(new_due_date),
            "note": new_note,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        new_row = pd.DataFrame([new_data])
        updated_df = pd.concat([df, new_row], ignore_index=True)

        save_data(updated_df)

        st.success("任務已成功同步寫入 Google 試算表")
        st.rerun()

st.write("---")

# ==========================================
# 搜尋與篩選
# ==========================================
st.write("### 搜尋與篩選")

f1, f2, f3 = st.columns([2, 1, 1])

with f1:
    keyword = st.text_input("搜尋任務名稱 / 備註 / 負責人")

with f2:
    owners = ["全部"] + sorted(df["owner"].dropna().unique().tolist())
    selected_owner = st.selectbox("負責人篩選", owners)

with f3:
    selected_priority = st.selectbox("優先度篩選", ["全部", "一般", "低", "中", "高"])

filtered_df = df.copy()

if keyword.strip():
    keyword_lower = keyword.lower()
    filtered_df = filtered_df[
        filtered_df["title"].str.lower().str.contains(keyword_lower, na=False)
        | filtered_df["owner"].str.lower().str.contains(keyword_lower, na=False)
        | filtered_df["note"].str.lower().str.contains(keyword_lower, na=False)
    ]

if selected_owner != "全部":
    filtered_df = filtered_df[filtered_df["owner"] == selected_owner]

if selected_priority != "全部":
    filtered_df = filtered_df[filtered_df["priority"] == selected_priority]

st.write("---")

# ==========================================
# Trello 看板
# ==========================================
st.write("### 看板動態狀態監控")

trello_col1, trello_col2, trello_col3 = st.columns(3)

status_map = {
    "To Do": {
        "column": trello_col1,
        "title": "🔴 To Do（待辦）",
        "color": "red"
    },
    "In Progress": {
        "column": trello_col2,
        "title": "🟠 In Progress（執行中）",
        "color": "orange"
    },
    "Done": {
        "column": trello_col3,
        "title": "🟢 Done（已完成）",
        "color": "green"
    }
}

for status_name, setting in status_map.items():
    with setting["column"]:
        st.markdown(
            f"### <span style='color:{setting['color']}'>{setting['title']}</span>",
            unsafe_allow_html=True
        )

        task_list = filtered_df[filtered_df["status"] == status_name]

        if task_list.empty:
            st.info("暫無任務")
        else:
            for idx, row in task_list.iterrows():
                task_id = row["id"]

                with st.container(border=True):
                    if row["status"] == "Done":
                        st.markdown(f"~~**{row['title']}**~~")
                    else:
                        st.markdown(f"**{row['title']}**")

                    st.caption(f"負責人：{row['owner']}")
                    st.caption(f"優先度：{priority_icon(row['priority'])}")
                    st.caption(f"期限：{row['due_date']}")

                    if str(row["note"]).strip():
                        st.write(f"備註：{row['note']}")

                    new_card_status = st.selectbox(
                        "修改狀態",
                        ["To Do", "In Progress", "Done"],
                        index=["To Do", "In Progress", "Done"].index(row["status"]),
                        key=f"status_{task_id}"
                    )

                    if new_card_status != row["status"]:
                        df.loc[df["id"] == task_id, "status"] = new_card_status
                        save_data(df)
                        st.success("狀態已更新")
                        st.rerun()

                    delete_btn = st.button("刪除任務", key=f"delete_{task_id}")

                    if delete_btn:
                        df = df[df["id"] != task_id]
                        save_data(df)
                        st.warning("任務已刪除")
                        st.rerun()
