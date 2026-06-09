import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date, datetime
import calendar
import uuid
from datetime import date, datetime, timedelta
# ==========================================
# 基本設定
# ==========================================
st.set_page_config(layout="wide")

st.title("鋒霈環境科技股份有限公司")
st.caption("台中分公司雲端同步智慧資源預約系統")

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
df = df.fillna("")

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
        return "高"
    elif priority == "中":
        return "中"
    elif priority == "低":
        return "低"
    return "一般"


# =========================================================
# 系統設定
# =========================================================
RESOURCE_OPTIONS = {
    "會議室": ["第一會議室", "第二會議室", "第三會議室",],
    "公務車": ["公務車A", "公務車B", "公務車C"],
}

STATUS_OPTIONS = ["閒置中", "使用中", "已預約"]
CHECKIN_OPTIONS = ["未簽到", "已簽到"]

STATUS_ICON = {"閒置中": "🟢", "使用中": "🟠", "已預約": "🔴"}
STATUS_COLOR = {"閒置中": "#e8f8ef", "使用中": "#fff3df", "已預約": "#fdecec"}
STATUS_BORDER = {"閒置中": "#2ecc71", "使用中": "#f39c12", "已預約": "#e74c3c"}

TIME_OPTIONS = [
    "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
    "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
    "17:00", "17:30", "18:00",
]

REQUIRED_COLUMNS = [
    "id", "resource_type", "resource_name", "booking_date", "start_time", "end_time",
    "applicant", "status", "checkin", "purpose", "created_at", "checkin_time",
]

# =========================================================
# CSS
# =========================================================
st.markdown(
    """
<style>
.block-container { padding-top: 1.5rem; }
.status-card {
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 8px solid #ddd;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.status-title { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.status-sub { color: #666; font-size: 14px; }
.calendar-day, .calendar-day-muted {
    min-height: 150px;
    border-radius: 12px;
    padding: 10px;
}
.calendar-day { border: 1px solid #e2e2e2; background: white; }
.calendar-day-muted { border: 1px solid #f1f1f1; background: #f8f8f8; color: #aaa; }
.calendar-date { font-weight: 700; font-size: 18px; margin-bottom: 8px; }
.slot-pill {
    border-radius: 999px;
    padding: 4px 8px;
    margin: 3px 0;
    font-size: 12px;
    display: inline-block;
    border: 1px solid #ddd;
}
</style>
""",
    unsafe_allow_html=True,
)



# =========================================================
# 資料處理
# =========================================================
def empty_booking_df() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def safe_rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def to_date_text(value) -> str:
    if pd.isna(value) or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    if not text:
        return ""

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        return parsed.strftime("%Y-%m-%d")
    return text[:10]


def to_time_text(value) -> str:
    if pd.isna(value) or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%H:%M")

    text = str(value).strip()
    if not text:
        return ""

    # Google Sheet 有時會讀成 09:00:00 或 1899-12-30 09:00:00
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        return parsed.strftime("%H:%M")

    if len(text) >= 5:
        return text[:5]
    return text


def normalize_df(dataframe: pd.DataFrame | None) -> pd.DataFrame:
    if dataframe is None or dataframe.empty:
        return empty_booking_df()

    dataframe = dataframe.copy()

    for col in REQUIRED_COLUMNS:
        if col not in dataframe.columns:
            dataframe[col] = ""

    dataframe = dataframe[REQUIRED_COLUMNS].fillna("")

    # 移除完全空白列，避免 Google Sheet 空白列造成畫面出現空預約
    dataframe = dataframe[
        dataframe[["resource_type", "resource_name", "booking_date", "start_time", "end_time"]]
        .astype(str)
        .apply(lambda row: any(cell.strip() for cell in row), axis=1)
    ].copy()

    if dataframe.empty:
        return empty_booking_df()

    dataframe["booking_date"] = dataframe["booking_date"].apply(to_date_text)
    dataframe["start_time"] = dataframe["start_time"].apply(to_time_text)
    dataframe["end_time"] = dataframe["end_time"].apply(to_time_text)

    dataframe.loc[~dataframe["resource_type"].isin(RESOURCE_OPTIONS.keys()), "resource_type"] = ""
    dataframe.loc[~dataframe["status"].isin(STATUS_OPTIONS), "status"] = "已預約"
    dataframe.loc[~dataframe["checkin"].isin(CHECKIN_OPTIONS), "checkin"] = "未簽到"

    blank_id_mask = dataframe["id"].astype(str).str.strip() == ""
    dataframe.loc[blank_id_mask, "id"] = [str(uuid.uuid4()) for _ in range(blank_id_mask.sum())]

    return dataframe.reset_index(drop=True)

    return False


df = load_data()

# =========================================================
# 預約邏輯
# =========================================================
def parse_datetime(booking_date_text: str, time_text: str) -> datetime | None:
    try:
        booking_date_text = to_date_text(booking_date_text)
        time_text = to_time_text(time_text)
        if not booking_date_text or not time_text:
            return None
        return datetime.strptime(f"{booking_date_text} {time_text}", "%Y-%m-%d %H:%M")
    except Exception:
        return None


def is_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def auto_release_expired_unchecked_bookings(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    now = datetime.now()
    keep_rows = []
    released_count = 0

    for _, row in dataframe.iterrows():
        start_dt = parse_datetime(row["booking_date"], row["start_time"])
        should_release = (
            start_dt is not None
            and row["checkin"] == "未簽到"
            and row["status"] in ["已預約", "使用中"]
            and now > start_dt + timedelta(minutes=15)
        )

        if should_release:
            released_count += 1
        else:
            keep_rows.append(row)

    result = pd.DataFrame(keep_rows) if keep_rows else empty_booking_df()
    return normalize_df(result), released_count


def has_booking_conflict(resource_type: str, resource_name: str, booking_date_value, start_time: str, end_time: str) -> bool:
    query_start = parse_datetime(str(booking_date_value), start_time)
    query_end = parse_datetime(str(booking_date_value), end_time)

    if query_start is None or query_end is None or query_start >= query_end:
        return True

    related = df[
        (df["resource_type"] == resource_type)
        & (df["resource_name"] == resource_name)
        & (df["booking_date"] == to_date_text(booking_date_value))
    ]

    for _, row in related.iterrows():
        row_start = parse_datetime(row["booking_date"], row["start_time"])
        row_end = parse_datetime(row["booking_date"], row["end_time"])
        if row_start and row_end and is_overlap(query_start, query_end, row_start, row_end):
            return True

    return False


def available_resources(resource_type: str, booking_date_value, start_time: str, end_time: str) -> list[str]:
    return [
        name for name in RESOURCE_OPTIONS[resource_type]
        if not has_booking_conflict(resource_type, name, booking_date_value, start_time, end_time)
    ]


def get_resource_status(resource_type: str, resource_name: str, target_date, target_start: str, target_end: str) -> str:
    query_start = parse_datetime(str(target_date), target_start)
    query_end = parse_datetime(str(target_date), target_end)

    if query_start is None or query_end is None or query_start >= query_end:
        return "已預約"

    related = df[
        (df["resource_type"] == resource_type)
        & (df["resource_name"] == resource_name)
        & (df["booking_date"] == to_date_text(target_date))
    ]

    if related.empty:
        return "閒置中"

    for _, row in related.iterrows():
        row_start = parse_datetime(row["booking_date"], row["start_time"])
        row_end = parse_datetime(row["booking_date"], row["end_time"])
        if row_start and row_end and is_overlap(query_start, query_end, row_start, row_end):
            return "使用中" if row["checkin"] == "已簽到" else "已預約"

    return "閒置中"


def day_status(resource_type: str, resource_name: str, day_value: date) -> str:
    day_bookings = df[
        (df["resource_type"] == resource_type)
        & (df["resource_name"] == resource_name)
        & (df["booking_date"] == to_date_text(day_value))
    ]

    if day_bookings.empty:
        return "閒置中"
    if "使用中" in day_bookings["status"].tolist():
        return "使用中"
    return "已預約"


df, released_count = auto_release_expired_unchecked_bookings(df)
if released_count > 0:
    if save_data(df):
        st.warning(f"系統已自動釋出 {released_count} 筆超過 15 分鐘未簽到的預約。")

# =========================================================
# UI 元件
# =========================================================
def time_range_selector(prefix: str, default_index: int = 2) -> tuple[str, str]:
    start_time = st.selectbox("開始時間", TIME_OPTIONS[:-1], index=default_index, key=f"{prefix}_start")
    end_options = [t for t in TIME_OPTIONS if t > start_time]
    end_time = st.selectbox("結束時間", end_options, index=0, key=f"{prefix}_end")
    return start_time, end_time


def render_status_cards(resource_type: str, target_date, target_start: str, target_end: str) -> None:
    st.write(f"### {resource_type}狀態")
    resources = RESOURCE_OPTIONS[resource_type]
    cols = st.columns(min(3, len(resources)))

    for idx, resource_name in enumerate(resources):
        status = get_resource_status(resource_type, resource_name, target_date, target_start, target_end)
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="status-card" style="background:{STATUS_COLOR[status]}; border-left-color:{STATUS_BORDER[status]};">
                    <div class="status-title">{resource_name}</div>
                    <div style="font-size:24px; font-weight:700;">{STATUS_ICON[status]} {status}</div>
                    <div class="status-sub">{to_date_text(target_date)}　{target_start}~{target_end}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_booking_form(resource_type: str) -> None:
    st.write(f"### 新增{resource_type}預約")

    with st.form(f"{resource_type}_booking_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            booking_date_value = st.date_input("預約日期", value=date.today(), key=f"{resource_type}_date")
            resource_name = st.selectbox(f"選擇{resource_type}", RESOURCE_OPTIONS[resource_type], key=f"{resource_type}_name")

        with c2:
            start_time, end_time = time_range_selector(f"{resource_type}_booking")

        with c3:
            applicant = st.text_input("預約人", placeholder="請輸入姓名", key=f"{resource_type}_applicant")
            purpose = st.text_input("用途", placeholder="例：內部會議 / 外出洽公", key=f"{resource_type}_purpose")

        submitted = st.form_submit_button(f"確認預約{resource_type}")

    if not submitted:
        return

    if not applicant.strip():
        st.warning("請輸入預約人")
        return

    if parse_datetime(str(booking_date_value), start_time) is None or parse_datetime(str(booking_date_value), end_time) is None:
        st.error("日期或時間格式錯誤，請重新選擇。")
        return

    if has_booking_conflict(resource_type, resource_name, booking_date_value, start_time, end_time):
        st.error(f"{resource_name} 在 {booking_date_value} {start_time}~{end_time} 已有預約，請改選其他時段。")
        return

    new_row = {
        "id": str(uuid.uuid4()),
        "resource_type": resource_type,
        "resource_name": resource_name,
        "booking_date": to_date_text(booking_date_value),
        "start_time": start_time,
        "end_time": end_time,
        "applicant": applicant.strip(),
        "status": "已預約",
        "checkin": "未簽到",
        "purpose": purpose.strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "checkin_time": "",
    }

    if save_data(pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)):
        st.success(f"{resource_name} 已成功預約：{booking_date_value} {start_time}~{end_time}")
        safe_rerun()


def render_calendar(resource_type: str) -> None:
    st.write(f"### {resource_type}月曆")

    today = date.today()
    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        year = st.number_input("年份", min_value=2024, max_value=2035, value=today.year, step=1, key=f"{resource_type}_calendar_year")
    with c2:
        month = st.selectbox("月份", list(range(1, 13)), index=today.month - 1, key=f"{resource_type}_calendar_month")
    with c3:
        selected_resource = st.selectbox(f"月曆顯示{resource_type}", RESOURCE_OPTIONS[resource_type], key=f"{resource_type}_calendar_resource")

    st.caption("圖例：🟢 閒置中　🟠 使用中　🔴 已預約")

    weekday_cols = st.columns(7)
    for col, name in zip(weekday_cols, ["日", "一", "二", "三", "四", "五", "六"]):
        col.markdown(f"**{name}**")

    month_calendar = calendar.Calendar(firstweekday=6).monthdatescalendar(int(year), int(month))

    for week in month_calendar:
        cols = st.columns(7)
        for col, day_value in zip(cols, week):
            in_month = day_value.month == int(month)
            css_class = "calendar-day" if in_month else "calendar-day-muted"

            if not in_month:
                col.markdown(f'<div class="{css_class}"><div class="calendar-date">{day_value.day}</div></div>', unsafe_allow_html=True)
                continue

            status = day_status(resource_type, selected_resource, day_value)
            day_bookings = df[
                (df["resource_type"] == resource_type)
                & (df["resource_name"] == selected_resource)
                & (df["booking_date"] == to_date_text(day_value))
            ].sort_values(["start_time"])

            if day_bookings.empty:
                booking_lines = f"""
                <div class="slot-pill" style="background:{STATUS_COLOR['閒置中']}; border-color:{STATUS_BORDER['閒置中']};">
                    🟢 全天可預約
                </div>
                """
            else:
                booking_lines = "".join(
                    f"""
                    <div class="slot-pill" style="background:{STATUS_COLOR.get(row['status'], STATUS_COLOR['已預約'])}; border-color:{STATUS_BORDER.get(row['status'], STATUS_BORDER['已預約'])};">
                        {STATUS_ICON.get(row['status'], '🔴')} {row['start_time']}-{row['end_time']}
                    </div><br>
                    """
                    for _, row in day_bookings.iterrows()
                )

            col.markdown(
                f"""
                <div class="{css_class}">
                    <div class="calendar-date">{day_value.day} {STATUS_ICON[status]}</div>
                    {booking_lines}
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_booking_table(resource_type: str) -> None:
    st.write(f"### {resource_type}預約紀錄 / 簽到管理")
    sub_df = df[df["resource_type"] == resource_type].copy()

    if sub_df.empty:
        st.info(f"目前沒有{resource_type}預約紀錄。")
        return

    sub_df = sub_df.sort_values(["booking_date", "start_time"])

    for _, row in sub_df.iterrows():
        row_id = str(row["id"])
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

            with c1:
                st.markdown(f"**{row['resource_name']}**")
                st.caption(f"{row['booking_date']} {row['start_time']}~{row['end_time']}")

            with c2:
                st.write(f"預約人：{row['applicant']}")
                st.write(f"用途：{row['purpose'] if row['purpose'] else '未填寫'}")

            with c3:
                st.write(f"狀態：{STATUS_ICON.get(row['status'], '')} {row['status']}")
                st.write(f"簽到：{row['checkin']}")

            with c4:
                if row["checkin"] == "未簽到":
                    if st.button("簽到並開始使用", key=f"checkin_{row_id}"):
                        new_df = df.copy()
                        new_df.loc[new_df["id"] == row_id, "checkin"] = "已簽到"
                        new_df.loc[new_df["id"] == row_id, "status"] = "使用中"
                        new_df.loc[new_df["id"] == row_id, "checkin_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if save_data(new_df):
                            safe_rerun()
                else:
                    if st.button("結束使用並釋出", key=f"finish_{row_id}"):
                        if save_data(df[df["id"] != row_id]):
                            safe_rerun()

                if st.button("取消預約", key=f"cancel_{row_id}"):
                    if save_data(df[df["id"] != row_id]):
                        safe_rerun()


def render_unreserved_search() -> None:
    st.write("### 未預約搜尋")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        search_date = st.date_input("搜尋日期", value=date.today(), key="search_date")
    with c2:
        start_time, end_time = time_range_selector("search")
    with c3:
        resource_filter = st.selectbox("資源類型", ["全部", "會議室", "公務車"], key="search_resource_type")

    st.write("---")

    for resource_type in ["會議室", "公務車"]:
        if resource_filter not in ["全部", resource_type]:
            continue

        st.write(f"#### 可預約{resource_type}")
        resources = available_resources(resource_type, search_date, start_time, end_time)

        if not resources:
            st.error(f"此時段沒有可預約{resource_type}。")
            continue

        cols = st.columns(min(3, len(resources)))
        for idx, resource_name in enumerate(resources):
            with cols[idx % len(cols)]:
                st.success(f"🟢 {resource_name}")


def render_resource_page(resource_type: str) -> None:
    st.info("可任選日期與時段預約；開始後 15 分鐘未簽到會自動釋出。")

    q1, q2 = st.columns([1, 2])
    with q1:
        status_date = st.date_input("狀態查詢日期", value=date.today(), key=f"{resource_type}_status_date")
    with q2:
        status_start, status_end = time_range_selector(f"{resource_type}_status")

    render_status_cards(resource_type, status_date, status_start, status_end)
    st.write("---")
    render_booking_form(resource_type)
    st.write("---")
    render_calendar(resource_type)
    st.write("---")
    render_booking_table(resource_type)


# =========================================================
# 主畫面
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs(["🏢 預約辦公室", "🚗 預約公務車", "🔍 未預約搜尋"])

with tab1:
    render_resource_page("會議室")

with tab2:
    render_resource_page("公務車")

with tab3:
    render_unreserved_search()


    st.write("#### 目前雲端欄位")
    st.dataframe(pd.DataFrame({"欄位名稱": REQUIRED_COLUMNS}), hide_index=True, use_container_width=True)
