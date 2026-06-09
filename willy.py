import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date, datetime, time, timedelta
import calendar
import uuid

# =========================================================
# 基本設定
# =========================================================
st.set_page_config(
    page_title="智慧資源預約系統",
    page_icon="🏢",
    layout="wide"
)

st.title("鋒霈環境科技股份有限公司")
st.caption("會議室 / 公務車 智慧預約管理系統")

conn = st.connection("gsheets", type=GSheetsConnection)

WORKSHEET_NAME = "Bookings"

# =========================================================
# 系統設定
# =========================================================
MEETING_ROOMS = [
    "第一會議室",
    "第二會議室",
    "第三會議室",
]

COMPANY_CARS = [
    "公務車A",
    "公務車B",
    "公務車C"
]

RESOURCE_OPTIONS = {
    "會議室": MEETING_ROOMS,
    "公務車": COMPANY_CARS
}

STATUS_OPTIONS = ["閒置中", "使用中", "已預約"]
CHECKIN_OPTIONS = ["未簽到", "已簽到"]

STATUS_ICON = {
    "閒置中": "🟢",
    "使用中": "🟠",
    "已預約": "🔴"
}

STATUS_COLOR = {
    "閒置中": "#e8f8ef",
    "使用中": "#fff3df",
    "已預約": "#fdecec"
}

STATUS_BORDER = {
    "閒置中": "#2ecc71",
    "使用中": "#f39c12",
    "已預約": "#e74c3c"
}

TIME_OPTIONS = [
    "08:00", "08:30",
    "09:00", "09:30",
    "10:00", "10:30",
    "11:00", "11:30",
    "12:00", "12:30",
    "13:00", "13:30",
    "14:00", "14:30",
    "15:00", "15:30",
    "16:00", "16:30",
    "17:00", "17:30",
    "18:00"
]

REQUIRED_COLUMNS = [
    "id",
    "resource_type",
    "resource_name",
    "booking_date",
    "start_time",
    "end_time",
    "applicant",
    "status",
    "checkin",
    "purpose",
    "created_at",
    "checkin_time"
]

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
}

.feature-box {
    border: 1px solid #e4e4e4;
    border-radius: 14px;
    padding: 16px;
    background: #fafafa;
    height: 100%;
}

.status-card {
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 8px solid #ddd;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.status-title {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 4px;
}

.status-sub {
    color: #666;
    font-size: 14px;
}

.calendar-day {
    min-height: 165px;
    border: 1px solid #e2e2e2;
    border-radius: 12px;
    padding: 10px;
    background: white;
}

.calendar-day-muted {
    min-height: 165px;
    border: 1px solid #f1f1f1;
    border-radius: 12px;
    padding: 10px;
    background: #f8f8f8;
    color: #aaa;
}

.calendar-date {
    font-weight: 700;
    font-size: 18px;
    margin-bottom: 8px;
}

.slot-pill {
    border-radius: 999px;
    padding: 4px 8px;
    margin: 3px 0;
    font-size: 12px;
    display: inline-block;
    border: 1px solid #ddd;
}

.benefit-box {
    background: linear-gradient(135deg, #f8fbff, #eef7ff);
    border: 1px solid #d9ecff;
    border-radius: 16px;
    padding: 16px;
    margin-top: 12px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 資料處理
# =========================================================
def empty_booking_df():
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def normalize_df(dataframe):
    if dataframe is None or dataframe.empty:
        dataframe = empty_booking_df()

    for col in REQUIRED_COLUMNS:
        if col not in dataframe.columns:
            dataframe[col] = ""

    dataframe = dataframe[REQUIRED_COLUMNS].fillna("")

    # 避免舊資料或空白狀態造成錯誤
    dataframe.loc[~dataframe["status"].isin(STATUS_OPTIONS), "status"] = "已預約"
    dataframe.loc[~dataframe["checkin"].isin(CHECKIN_OPTIONS), "checkin"] = "未簽到"

    return dataframe


def load_data():
    try:
        dataframe = conn.read(worksheet=WORKSHEET_NAME, ttl=0)
        return normalize_df(dataframe)
    except Exception:
        # 若 Google Sheet 尚未建立 Bookings 工作表，可先用空表讓系統啟動
        return empty_booking_df()


def save_data(dataframe):
    dataframe = normalize_df(dataframe)
    conn.update(worksheet=WORKSHEET_NAME, data=dataframe)


df = load_data()

# =========================================================
# 時間 / 狀態邏輯
# =========================================================
def parse_datetime(booking_date, time_text):
    try:
        return datetime.strptime(f"{booking_date} {time_text}", "%Y-%m-%d %H:%M")
    except Exception:
        return None


def is_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def auto_release_expired_unchecked_bookings(dataframe):
    """
    智慧簽到管理：
    會議室或公務車開始後 15 分鐘仍未簽到，系統自動釋出。
    做法：將該筆資料從預約資料中移除，等同重新開放預約。
    """
    now = datetime.now()
    keep_rows = []
    released_count = 0

    for _, row in dataframe.iterrows():
        start_dt = parse_datetime(row["booking_date"], row["start_time"])
        if (
            start_dt
            and row["checkin"] == "未簽到"
            and row["status"] in ["已預約", "使用中"]
            and now > start_dt + timedelta(minutes=15)
        ):
            released_count += 1
            continue

        keep_rows.append(row)

    new_df = pd.DataFrame(keep_rows) if keep_rows else empty_booking_df()
    new_df = normalize_df(new_df)

    return new_df, released_count


df, released_count = auto_release_expired_unchecked_bookings(df)
if released_count > 0:
    save_data(df)
    st.warning(f"系統已自動釋出 {released_count} 筆超過 15 分鐘未簽到的預約。")


def get_resource_status(resource_type, resource_name, target_date=None, target_start=None, target_end=None):
    """
    回傳指定資源在指定日期/時段的狀態。
    若未指定時段，則以今天目前時間判斷。
    """
    if target_date is None:
        target_date = str(date.today())

    related = df[
        (df["resource_type"] == resource_type)
        & (df["resource_name"] == resource_name)
        & (df["booking_date"] == str(target_date))
    ]

    if related.empty:
        return "閒置中"

    if target_start and target_end:
        query_start = parse_datetime(str(target_date), target_start)
        query_end = parse_datetime(str(target_date), target_end)

        for _, row in related.iterrows():
            row_start = parse_datetime(row["booking_date"], row["start_time"])
            row_end = parse_datetime(row["booking_date"], row["end_time"])
            if row_start and row_end and is_overlap(query_start, query_end, row_start, row_end):
                return row["status"]

        return "閒置中"

    now = datetime.now()

    for _, row in related.iterrows():
        row_start = parse_datetime(row["booking_date"], row["start_time"])
        row_end = parse_datetime(row["booking_date"], row["end_time"])

        if row_start and row_end:
            if row_start <= now <= row_end:
                return "使用中" if row["checkin"] == "已簽到" else row["status"]
            if now < row_start:
                return "已預約"

    return "閒置中"


def has_booking_conflict(resource_type, resource_name, booking_date, start_time, end_time):
    query_start = parse_datetime(str(booking_date), start_time)
    query_end = parse_datetime(str(booking_date), end_time)

    related = df[
        (df["resource_type"] == resource_type)
        & (df["resource_name"] == resource_name)
        & (df["booking_date"] == str(booking_date))
    ]

    for _, row in related.iterrows():
        row_start = parse_datetime(row["booking_date"], row["start_time"])
        row_end = parse_datetime(row["booking_date"], row["end_time"])
        if row_start and row_end and is_overlap(query_start, query_end, row_start, row_end):
            return True

    return False


def available_resources(resource_type, booking_date, start_time, end_time):
    result = []
    for resource_name in RESOURCE_OPTIONS[resource_type]:
        if not has_booking_conflict(resource_type, resource_name, booking_date, start_time, end_time):
            result.append(resource_name)
    return result


def day_status(resource_type, resource_name, day):
    day_text = str(day)
    day_bookings = df[
        (df["resource_type"] == resource_type)
        & (df["resource_name"] == resource_name)
        & (df["booking_date"] == day_text)
    ]

    if day_bookings.empty:
        return "閒置中"

    if "使用中" in day_bookings["status"].tolist():
        return "使用中"

    return "已預約"


# =========================================================
# UI 共用元件
# =========================================================
def render_feature_section(resource_type):
    if resource_type == "會議室":
        title1 = "多元預約模式"
        title2 = "會議室狀態可視化"
        title3 = "智慧簽到管理"
        desc2 = "🟢 閒置中　🟠 使用中　🔴 已預約"
        desc3 = "搭配簽到模組，會議開始後 15 分鐘未簽到，系統自動釋出會議室。"
    else:
        title1 = "多元預約模式"
        title2 = "公務車狀態可視化"
        title3 = "智慧簽到管理"
        desc2 = "🟢 閒置中　🟠 使用中　🔴 已預約"
        desc3 = "搭配簽到模組，開始後 15 分鐘未簽到，系統自動釋出公務車。"

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"""
        <div class="feature-box">
            <h4>1. {title1}</h4>
            <div>・任選日期預約</div>
            <div>・任選時段預約</div>
            <div>・彈性安排{'會議' if resource_type == '會議室' else '用車'}時間</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="feature-box">
            <h4>2. {title2}</h4>
            <div>{desc2}</div>
            <div style="margin-top:8px;">以卡片與月曆方式呈現可用狀態。</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="feature-box">
            <h4>3. {title3}</h4>
            <div>{desc3}</div>
        </div>
        """, unsafe_allow_html=True)


def render_status_cards(resource_type, target_date=None, target_start=None, target_end=None):
    st.write(f"### {resource_type}狀態可視化")

    resources = RESOURCE_OPTIONS[resource_type]
    cols = st.columns(min(3, len(resources)))

    for idx, resource_name in enumerate(resources):
        status = get_resource_status(resource_type, resource_name, target_date, target_start, target_end)
        icon = STATUS_ICON[status]
        bg = STATUS_COLOR[status]
        border = STATUS_BORDER[status]

        with cols[idx % len(cols)]:
            st.markdown(f"""
            <div class="status-card" style="background:{bg}; border-left-color:{border};">
                <div class="status-title">{resource_name}</div>
                <div style="font-size:24px; font-weight:700;">{icon} {status}</div>
                <div class="status-sub">日期：{target_date if target_date else date.today()}</div>
            </div>
            """, unsafe_allow_html=True)


def render_booking_form(resource_type):
    st.write(f"### 新增{resource_type}預約")

    with st.form(f"{resource_type}_booking_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            booking_date = st.date_input("預約日期", value=date.today(), key=f"{resource_type}_date")
            resource_name = st.selectbox(f"選擇{resource_type}", RESOURCE_OPTIONS[resource_type], key=f"{resource_type}_name")

        with c2:
            start_time = st.selectbox("開始時間", TIME_OPTIONS[:-1], index=2, key=f"{resource_type}_start")
            valid_end_options = [t for t in TIME_OPTIONS if t > start_time]
            end_time = st.selectbox("結束時間", valid_end_options, index=0, key=f"{resource_type}_end")

        with c3:
            applicant = st.text_input("預約人", placeholder="請輸入姓名", key=f"{resource_type}_applicant")
            purpose = st.text_input("用途", placeholder="例：內部會議 / 外出洽公", key=f"{resource_type}_purpose")

        submit = st.form_submit_button(f"確認預約{resource_type}")

    if submit:
        if not applicant.strip():
            st.warning("請輸入預約人")
            return

        if has_booking_conflict(resource_type, resource_name, booking_date, start_time, end_time):
            st.error(f"{resource_name} 在 {booking_date} {start_time}~{end_time} 已有預約，請改選其他時段。")
            return

        new_row = {
            "id": str(uuid.uuid4()),
            "resource_type": resource_type,
            "resource_name": resource_name,
            "booking_date": str(booking_date),
            "start_time": start_time,
            "end_time": end_time,
            "applicant": applicant,
            "status": "已預約",
            "checkin": "未簽到",
            "purpose": purpose,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "checkin_time": ""
        }

        updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(updated_df)
        st.success(f"{resource_name} 已成功預約：{booking_date} {start_time}~{end_time}")
        st.rerun()


def render_calendar(resource_type):
    st.write(f"### {resource_type}月曆預約狀態")

    c1, c2, c3 = st.columns([1, 1, 2])

    today = date.today()

    with c1:
        year = st.number_input("年份", min_value=2024, max_value=2035, value=today.year, step=1, key=f"{resource_type}_calendar_year")

    with c2:
        month = st.selectbox("月份", list(range(1, 13)), index=today.month - 1, key=f"{resource_type}_calendar_month")

    with c3:
        selected_resource = st.selectbox(f"月曆顯示{resource_type}", RESOURCE_OPTIONS[resource_type], key=f"{resource_type}_calendar_resource")

    st.caption("圖例：🟢 閒置中　🟠 使用中　🔴 已預約")

    month_calendar = calendar.Calendar(firstweekday=6).monthdatescalendar(int(year), int(month))

    weekday_cols = st.columns(7)
    for col, name in zip(weekday_cols, ["日", "一", "二", "三", "四", "五", "六"]):
        col.markdown(f"**{name}**")

    for week in month_calendar:
        cols = st.columns(7)

        for col, day in zip(cols, week):
            in_current_month = day.month == month
            status = day_status(resource_type, selected_resource, day) if in_current_month else "閒置中"
            icon = STATUS_ICON[status]

            day_bookings = df[
                (df["resource_type"] == resource_type)
                & (df["resource_name"] == selected_resource)
                & (df["booking_date"] == str(day))
            ].sort_values(["start_time"])

            css_class = "calendar-day" if in_current_month else "calendar-day-muted"

            if not in_current_month:
                col.markdown(f"""
                <div class="{css_class}">
                    <div class="calendar-date">{day.day}</div>
                </div>
                """, unsafe_allow_html=True)
                continue

            booking_lines = ""
            if day_bookings.empty:
                booking_lines = f"""
                <div class="slot-pill" style="background:{STATUS_COLOR['閒置中']}; border-color:{STATUS_BORDER['閒置中']};">
                    🟢 全天可預約
                </div>
                """
            else:
                for _, row in day_bookings.iterrows():
                    row_status = row["status"]
                    booking_lines += f"""
                    <div class="slot-pill" style="background:{STATUS_COLOR[row_status]}; border-color:{STATUS_BORDER[row_status]};">
                        {STATUS_ICON[row_status]} {row["start_time"]}-{row["end_time"]}
                    </div><br>
                    """

            col.markdown(f"""
            <div class="{css_class}">
                <div class="calendar-date">{day.day} {icon}</div>
                <div>{booking_lines}</div>
            </div>
            """, unsafe_allow_html=True)


def render_booking_table(resource_type):
    st.write(f"### {resource_type}預約紀錄 / 簽到管理")

    sub_df = df[df["resource_type"] == resource_type].copy()

    if sub_df.empty:
        st.info(f"目前沒有{resource_type}預約紀錄。")
        return

    sub_df = sub_df.sort_values(["booking_date", "start_time"], ascending=[True, True])

    for _, row in sub_df.iterrows():
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
                    if st.button("簽到並開始使用", key=f"checkin_{row['id']}"):
                        df.loc[df["id"] == row["id"], "checkin"] = "已簽到"
                        df.loc[df["id"] == row["id"], "status"] = "使用中"
                        df.loc[df["id"] == row["id"], "checkin_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_data(df)
                        st.success("已完成簽到")
                        st.rerun()
                else:
                    if st.button("結束使用並釋出", key=f"finish_{row['id']}"):
                        new_df = df[df["id"] != row["id"]]
                        save_data(new_df)
                        st.success("已結束使用並釋出資源")
                        st.rerun()

                if st.button("取消預約", key=f"cancel_{row['id']}"):
                    new_df = df[df["id"] != row["id"]]
                    save_data(new_df)
                    st.warning("已取消預約")
                    st.rerun()


def render_unreserved_search():
    st.write("### 未預約搜尋")

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

    with c1:
        search_date = st.date_input("搜尋日期", value=date.today())

    with c2:
        start_time = st.selectbox("開始時間", TIME_OPTIONS[:-1], index=2, key="search_start")

    with c3:
        valid_end_options = [t for t in TIME_OPTIONS if t > start_time]
        end_time = st.selectbox("結束時間", valid_end_options, index=0, key="search_end")

    with c4:
        resource_filter = st.selectbox("資源類型", ["全部", "會議室", "公務車"])

    st.write("---")

    if resource_filter in ["全部", "會議室"]:
        rooms = available_resources("會議室", search_date, start_time, end_time)
        st.write("#### 可預約會議室")
        if rooms:
            cols = st.columns(min(3, len(rooms)))
            for idx, room in enumerate(rooms):
                with cols[idx % len(cols)]:
                    st.success(f"🟢 {room}")
        else:
            st.error("此時段沒有可預約會議室。")

    if resource_filter in ["全部", "公務車"]:
        cars = available_resources("公務車", search_date, start_time, end_time)
        st.write("#### 可預約公務車")
        if cars:
            cols = st.columns(min(3, len(cars)))
            for idx, car in enumerate(cars):
                with cols[idx % len(cols)]:
                    st.success(f"🟢 {car}")
        else:
            st.error("此時段沒有可預約公務車。")

# =========================================================
# 主畫面 Tab
# =========================================================
tab1, tab2, tab3 = st.tabs([
    "🏢 預約辦公室",
    "🚗 預約公務車",
    "🔍 未預約搜尋"
])

with tab1:
    render_feature_section("會議室")
    st.write("---")

    q1, q2, q3 = st.columns([1, 1, 1])
    with q1:
        status_date = st.date_input("狀態查詢日期", value=date.today(), key="room_status_date")
    with q2:
        status_start = st.selectbox("狀態查詢開始", TIME_OPTIONS[:-1], index=2, key="room_status_start")
    with q3:
        status_end_options = [t for t in TIME_OPTIONS if t > status_start]
        status_end = st.selectbox("狀態查詢結束", status_end_options, index=0, key="room_status_end")

    render_status_cards("會議室", status_date, status_start, status_end)
    st.write("---")

    render_booking_form("會議室")
    st.write("---")

    render_calendar("會議室")
    st.write("---")

    render_booking_table("會議室")
    render_benefits()

with tab2:
    render_feature_section("公務車")
    st.write("---")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        car_status_date = st.date_input("狀態查詢日期", value=date.today(), key="car_status_date")
    with c2:
        car_status_start = st.selectbox("狀態查詢開始", TIME_OPTIONS[:-1], index=2, key="car_status_start")
    with c3:
        car_status_end_options = [t for t in TIME_OPTIONS if t > car_status_start]
        car_status_end = st.selectbox("狀態查詢結束", car_status_end_options, index=0, key="car_status_end")

    render_status_cards("公務車", car_status_date, car_status_start, car_status_end)
    st.write("---")

    render_booking_form("公務車")
    st.write("---")

    render_calendar("公務車")
    st.write("---")

    render_booking_table("公務車")
    render_benefits()

with tab3:
    render_unreserved_search()
    render_benefits()
