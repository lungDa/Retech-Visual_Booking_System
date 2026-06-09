import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date, datetime, time, timedelta

# ==========================================
# 基本設定
# ==========================================
st.set_page_config(layout="wide")

st.title("鋒霈環境科技股份有限公司")
st.caption("台中分公司雲端同步｜辦公室 / 會議室 / 公務車預約系統")

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
    "resource_type": "辦公室/會議室",
    "title": "",
    "status": "閒置中",
    "owner": "",
    "reserve_date": "",
    "start_time": "",
    "end_time": "",
    "check_in": "未簽到",
    "note": "",
    "created_at": ""
}

for col, default_value in required_columns.items():
    if col not in df.columns:
        df[col] = default_value

df = df[list(required_columns.keys())]
df = df.fillna("")

changed = False

for i in df.index:
    if str(df.at[i, "id"]).strip() == "":
        df.at[i, "id"] = f"BOOK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}"
        changed = True

if changed:
    conn.update(worksheet=WORKSHEET_NAME, data=df)

# ==========================================
# 工具函式
# ==========================================
def save_data(dataframe):
    conn.update(worksheet=WORKSHEET_NAME, data=dataframe)


def status_icon(status):
    if status == "閒置中":
        return "🟢 閒置中"
    elif status == "準備中":
        return "🟠 準備中"
    elif status == "使用中":
        return "🔴 使用中"
    return status


def parse_hhmm(value):
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except Exception:
        return None


def is_time_overlap(start_a, end_a, start_b, end_b):
    if not all([start_a, end_a, start_b, end_b]):
        return False
    return start_a < end_b and start_b < end_a


def append_note(old_note, new_note):
    old_note = str(old_note).strip()
    if old_note:
        return old_note + "｜" + new_note
    return new_note


def auto_release_no_show(dataframe):
    """
    會議開始後 15 分鐘未簽到，自動釋出會議室。
    條件：
    1. 類型為辦公室/會議室
    2. 狀態為使用中
    3. check_in 不是已簽到
    4. 預約日期為今天
    5. 目前時間已超過開始時間 15 分鐘
    """
    now = datetime.now()
    today_str = str(date.today())
    updated = False

    for i in dataframe.index:
        if str(dataframe.at[i, "resource_type"]) != "辦公室/會議室":
            continue
        if str(dataframe.at[i, "status"]) != "使用中":
            continue
        if str(dataframe.at[i, "check_in"]) == "已簽到":
            continue
        if str(dataframe.at[i, "reserve_date"]) != today_str:
            continue

        start_t = parse_hhmm(dataframe.at[i, "start_time"])
        if start_t is None:
            continue

        meeting_start = datetime.combine(date.today(), start_t)
        release_time = meeting_start + timedelta(minutes=15)

        if now >= release_time:
            dataframe.at[i, "status"] = "閒置中"
            dataframe.at[i, "check_in"] = "逾時釋出"
            dataframe.at[i, "note"] = append_note(
                dataframe.at[i, "note"],
                f"系統於 {now.strftime('%Y-%m-%d %H:%M:%S')} 自動釋出：會議開始後 15 分鐘無人簽到"
            )
            updated = True

    return dataframe, updated


def find_available_resources(dataframe, resource_type, reserve_date, start_time, end_time):
    """
    依照日期與時段查找未衝突的資源。
    若同一資源在同一天有重疊時段且狀態為準備中/使用中，視為不可用。
    """
    resource_names = sorted(
        dataframe[dataframe["resource_type"] == resource_type]["title"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )

    available = []

    for resource_name in resource_names:
        rows = dataframe[
            (dataframe["resource_type"] == resource_type)
            & (dataframe["title"] == resource_name)
            & (dataframe["reserve_date"] == str(reserve_date))
            & (dataframe["status"].isin(["準備中", "使用中"]))
        ]

        conflict = False
        for _, row in rows.iterrows():
            old_start = parse_hhmm(row["start_time"])
            old_end = parse_hhmm(row["end_time"])
            if is_time_overlap(start_time, end_time, old_start, old_end):
                conflict = True
                break

        if not conflict:
            available.append(resource_name)

    return available


# 先執行會議室逾時釋出
df, released = auto_release_no_show(df)
if released:
    save_data(df)

# ==========================================
# CSS
# ==========================================
st.markdown("""
<style>
.sticky-board-title {
    position: sticky;
    top: 0;
    z-index: 999;
    background-color: white;
    padding: 12px 0 8px 0;
    border-bottom: 1px solid #ddd;
}

.status-card {
    padding: 14px;
    border-radius: 12px;
    border: 1px solid #ddd;
    background-color: #fafafa;
    margin-bottom: 10px;
}

.small-caption {
    color: #666;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 建立 Tab 分頁
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "🏢 預約辦公室",
    "🚗 預約公務車",
    "🔎 未預約搜尋"
])

# ==========================================
# Tab 1：預約辦公室 / 會議室
# ==========================================
with tab1:
    st.write("### 預約辦公室")

    st.info(
        "會議室狀態可視化：🟢 閒置中　🟠 準備中　🔴 使用中。"
        "會議開始後 15 分鐘無人簽到，系統會自動釋出會議室。"
    )

    office_df = df[df["resource_type"] == "辦公室/會議室"].copy()

    st.write("### 會議室狀態可視化")

    if office_df.empty:
        st.warning("目前尚無辦公室 / 會議室資料。請先新增第一筆預約。")
    else:
        display_cols = st.columns(3)
        for idx, (_, row) in enumerate(office_df.iterrows()):
            with display_cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"#### {status_icon(row['status'])}")
                    st.write(f"**會議室 / 空間：** {row['title']}")
                    st.caption(f"預約人：{row['owner'] if str(row['owner']).strip() else '無'}")
                    st.caption(f"日期：{row['reserve_date']}")
                    st.caption(f"時段：{row['start_time']} ~ {row['end_time']}")
                    st.caption(f"簽到狀態：{row['check_in']}")

                    if str(row["note"]).strip():
                        st.write(f"備註：{row['note']}")

                    if row["status"] in ["準備中", "使用中"] and row["check_in"] != "已簽到":
                        if st.button("簽到", key=f"checkin_{row['id']}"):
                            df.loc[df["id"] == row["id"], "check_in"] = "已簽到"
                            df.loc[df["id"] == row["id"], "status"] = "使用中"
                            save_data(df)
                            st.success("簽到完成，狀態已更新為使用中")
                            st.rerun()

                    new_room_status = st.selectbox(
                        "修改狀態",
                        ["閒置中", "準備中", "使用中"],
                        index=["閒置中", "準備中", "使用中"].index(row["status"])
                        if row["status"] in ["閒置中", "準備中", "使用中"] else 0,
                        key=f"office_status_{row['id']}"
                    )

                    if new_room_status != row["status"]:
                        df.loc[df["id"] == row["id"], "status"] = new_room_status
                        save_data(df)
                        st.success("會議室狀態已更新")
                        st.rerun()

    st.write("---")
    st.write("### 新增辦公室 / 會議室預約")

    with st.form("office_booking_form", clear_on_submit=True):
        c_title, c_owner, c_status = st.columns([2, 1, 1])

        with c_title:
            room_name = st.text_input("會議室 / 空間名稱", placeholder="例如：A會議室、B會議室、主管會議室")

        with c_owner:
            room_owner = st.text_input("預約人", placeholder="輸入預約人")

        with c_status:
            room_status = st.selectbox("狀態", ["準備中", "使用中", "閒置中"])

        c_date, c_start, c_end = st.columns(3)

        with c_date:
            room_date = st.date_input("預約日期", value=date.today(), key="room_date")

        with c_start:
            room_start = st.time_input("開始時間", value=time(9, 0), key="room_start")

        with c_end:
            room_end = st.time_input("結束時間", value=time(10, 0), key="room_end")

        room_note = st.text_input("備註", placeholder="例如：週會、客戶會議、教育訓練")

        submit_room = st.form_submit_button("確認預約辦公室 / 會議室並同步雲端")

    if submit_room:
        if not room_name.strip():
            st.warning("請輸入會議室 / 空間名稱")
        elif not room_owner.strip():
            st.warning("請輸入預約人")
        elif room_start >= room_end:
            st.warning("結束時間必須晚於開始時間")
        else:
            new_data = {
                "id": f"BOOK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "resource_type": "辦公室/會議室",
                "title": room_name,
                "status": room_status,
                "owner": room_owner,
                "reserve_date": str(room_date),
                "start_time": room_start.strftime("%H:%M"),
                "end_time": room_end.strftime("%H:%M"),
                "check_in": "未簽到",
                "note": room_note,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(updated_df)

            st.success("辦公室 / 會議室預約已成功同步寫入 Google 試算表")
            st.rerun()

# ==========================================
# Tab 2：預約公務車
# ==========================================
with tab2:
    st.write("### 預約公務車")

    st.info("公務車支援多元預約模式，可任選日期與時段預約。")

    car_df = df[df["resource_type"] == "公務車"].copy()

    with st.form("car_booking_form", clear_on_submit=True):
        c_car, c_owner, c_status = st.columns([2, 1, 1])

        with c_car:
            car_name = st.text_input("公務車名稱 / 車號", placeholder="例如：公務車A、ABC-1234")

        with c_owner:
            car_owner = st.text_input("預約人", placeholder="輸入預約人")

        with c_status:
            car_status = st.selectbox("車輛狀態", ["準備中", "使用中", "閒置中"])

        c_date, c_start, c_end = st.columns(3)

        with c_date:
            car_date = st.date_input("預約日期", value=date.today(), key="car_date")

        with c_start:
            car_start = st.time_input("開始時間", value=time(9, 0), key="car_start")

        with c_end:
            car_end = st.time_input("結束時間", value=time(10, 0), key="car_end")

        car_note = st.text_input("用途 / 備註", placeholder="例如：外出洽公、工地勘查、送件")

        submit_car = st.form_submit_button("確認預約公務車並同步雲端")

    if submit_car:
        if not car_name.strip():
            st.warning("請輸入公務車名稱 / 車號")
        elif not car_owner.strip():
            st.warning("請輸入預約人")
        elif car_start >= car_end:
            st.warning("結束時間必須晚於開始時間")
        else:
            new_data = {
                "id": f"BOOK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "resource_type": "公務車",
                "title": car_name,
                "status": car_status,
                "owner": car_owner,
                "reserve_date": str(car_date),
                "start_time": car_start.strftime("%H:%M"),
                "end_time": car_end.strftime("%H:%M"),
                "check_in": "不適用",
                "note": car_note,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            updated_df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(updated_df)

            st.success("公務車預約已成功同步寫入 Google 試算表")
            st.rerun()

    st.write("---")
    st.write("### 公務車預約總覽")

    total_car = len(car_df)
    idle_car = len(car_df[car_df["status"] == "閒置中"])
    preparing_car = len(car_df[car_df["status"] == "準備中"])
    using_car = len(car_df[car_df["status"] == "使用中"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("全部公務車預約", total_car)
    m2.metric("閒置中", idle_car)
    m3.metric("準備中", preparing_car)
    m4.metric("使用中", using_car)

    if car_df.empty:
        st.info("目前尚無公務車預約資料")
    else:
        st.dataframe(
            car_df[["title", "status", "owner", "reserve_date", "start_time", "end_time", "note"]],
            use_container_width=True,
            hide_index=True
        )

# ==========================================
# Tab 3：未預約搜尋
# ==========================================
with tab3:
    st.write("### 未預約搜尋")

    st.info("可依日期、時段、類型一鍵查找可用資源。")

    s1, s2, s3, s4 = st.columns([1, 1, 1, 1])

    with s1:
        search_type = st.selectbox("搜尋類型", ["辦公室/會議室", "公務車"])

    with s2:
        search_date = st.date_input("搜尋日期", value=date.today(), key="search_date")

    with s3:
        search_start = st.time_input("開始時間", value=time(9, 0), key="search_start")

    with s4:
        search_end = st.time_input("結束時間", value=time(10, 0), key="search_end")

    keyword = st.text_input("關鍵字搜尋", placeholder="可搜尋會議室名稱、公務車名稱、預約人、備註")

    filtered_df = df[df["resource_type"] == search_type].copy()

    if keyword.strip():
        keyword_lower = keyword.lower()
        filtered_df = filtered_df[
            filtered_df["title"].astype(str).str.lower().str.contains(keyword_lower, na=False)
            | filtered_df["owner"].astype(str).str.lower().str.contains(keyword_lower, na=False)
            | filtered_df["note"].astype(str).str.lower().str.contains(keyword_lower, na=False)
        ]

    st.write("---")

    if search_start >= search_end:
        st.warning("結束時間必須晚於開始時間")
    else:
        available_resources = find_available_resources(
            dataframe=filtered_df,
            resource_type=search_type,
            reserve_date=search_date,
            start_time=search_start,
            end_time=search_end
        )

        st.write("### 一鍵查找空資源")

        if available_resources:
            st.success(f"找到 {len(available_resources)} 個可用資源")
            available_df = pd.DataFrame({
                "類型": search_type,
                "可用資源": available_resources,
                "日期": str(search_date),
                "可用時段": f"{search_start.strftime('%H:%M')} ~ {search_end.strftime('%H:%M')}",
                "狀態": "🟢 可預約"
            })
            st.dataframe(available_df, use_container_width=True, hide_index=True)
        else:
            st.warning("目前查無可用資源，可能尚未建立資源名稱，或指定時段皆已被預約。")

    st.write("---")

    st.markdown(
        '<div class="sticky-board-title"><h3>🔎 未預約搜尋與預約監控</h3></div>',
        unsafe_allow_html=True
    )

    trello_col1, trello_col2, trello_col3 = st.columns(3)

    status_map = {
        "閒置中": {
            "column": trello_col1,
            "title": "🟢 閒置中",
            "color": "green"
        },
        "準備中": {
            "column": trello_col2,
            "title": "🟠 準備中",
            "color": "orange"
        },
        "使用中": {
            "column": trello_col3,
            "title": "🔴 使用中",
            "color": "red"
        }
    }

    for status_name, setting in status_map.items():
        with setting["column"]:
            st.markdown(
                f"### <span style='color:{setting['color']}'>{setting['title']}</span>",
                unsafe_allow_html=True
            )

            booking_list = filtered_df[filtered_df["status"] == status_name]

            if booking_list.empty:
                st.info("暫無資料")
            else:
                for idx, row in booking_list.iterrows():
                    booking_id = row["id"]

                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"類型：{row['resource_type']}")
                        st.caption(f"預約人：{row['owner']}")
                        st.caption(f"日期：{row['reserve_date']}")
                        st.caption(f"時段：{row['start_time']} ~ {row['end_time']}")
                        st.caption(f"簽到狀態：{row['check_in']}")

                        if str(row["note"]).strip():
                            st.write(f"備註：{row['note']}")

                        new_card_status = st.selectbox(
                            "修改狀態",
                            ["閒置中", "準備中", "使用中"],
                            index=["閒置中", "準備中", "使用中"].index(row["status"])
                            if row["status"] in ["閒置中", "準備中", "使用中"] else 0,
                            key=f"status_{booking_id}"
                        )

                        if new_card_status != row["status"]:
                            df.loc[df["id"] == booking_id, "status"] = new_card_status
                            save_data(df)
                            st.success("狀態已更新")
                            st.rerun()

                        delete_btn = st.button("刪除預約", key=f"delete_{booking_id}")

                        if delete_btn:
                            df = df[df["id"] != booking_id]
                            save_data(df)
                            st.warning("預約已刪除")
                            st.rerun()
