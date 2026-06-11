import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date, datetime, timedelta, timezone
import calendar
import uuid
import requests
from io import StringIO
import urllib3
import time


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
TW_TZ = timezone(timedelta(hours=8))
# =========================================================
# 基本設定
# =========================================================
st.set_page_config(
    page_title="視覺化預約系統",
    page_icon="🏢",
    layout="wide"
)
# 每 300 秒自動刷新一次，讓狀態可隨時間變化
components.html(
    """
    <script>
        setTimeout(function(){
            window.parent.location.reload();
        }, 300000);
    </script>
    """,
    height=0,
)

st.title("鋒霈環境科技股份有限公司_台中分公司")
st.caption("雲端同步視覺化預約系統")
st.caption("版本：2026-06-09 13:30 開發測試版")

WORKSHEET_NAME = "Tasks"

# =========================================================
# 系統設定
# =========================================================
RESOURCE_OPTIONS = {
    "會議室": ["大會議室", "中會議室", "小會議室"],
    "公務車": ["RDZ-6985 貨車小綠", "RDN-3519  Sienta", "RFX-8070  休旅Cross"],
}

STATUS_OPTIONS = [
    "閒置中",
    "部分預約",
    "已滿",
    "使用中",
    "已預約",
    "休假",
    "已取消",
    "已結束",
    "已失效",
]
CHECKIN_OPTIONS = ["未簽到", "已簽到"]

# 一般勞工不放假的國定紀念日 / 節日，允許預約
LABOR_WORKING_HOLIDAY_KEYWORDS = [
    "軍人節",
    "教師節",
    "光復節",
    "行憲紀念日",
    "蔣公誕辰紀念日",
    "國父誕辰紀念日",
]

STATUS_ICON = {
    "閒置中": "🟢",
    "部分預約": "🟠",
    "已滿": "🔴",
    "使用中": "🟠",
    "已預約": "🔴",
    "休假": "🚫",
    "已取消": "⚫",
    "已結束": "⚫",
    "已失效": "⚫",
}

STATUS_COLOR = {
    "閒置中": "#e8f8ef",
    "部分預約": "#fff3df",
    "已滿": "#fdecec",
    "使用中": "#fff3df",
    "已預約": "#fdecec",
    "休假": "#f5f5f5",
    "已取消": "#eeeeee",
    "已結束": "#eeeeee",
    "已失效": "#eeeeee",
}

STATUS_BORDER = {
    "閒置中": "#2ecc71",
    "部分預約": "#f39c12",
    "已滿": "#e74c3c",
    "使用中": "#f39c12",
    "已預約": "#e74c3c",
    "休假": "#999999",
    "已取消": "#999999",
    "已結束": "#999999",
    "已失效": "#999999",
}

def is_closed_status(status) -> bool:
    return normalize_status(status) in ["已取消", "已結束", "已失效"]

TIME_OPTIONS = [
    "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30", "13:00", "13:30",
    "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
    "17:00", "17:30", "18:00",
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
    "checkin_time",
    "closed_time",
]

# =========================================================
# Google Sheet 連線
# =========================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    conn = None
    st.sidebar.error("Google Sheet 連線初始化失敗")
    st.sidebar.exception(e)

# =========================================================
# CSS
# =========================================================
st.markdown(
    """
<style>
.block-container {
    padding-top: 1.5rem;
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

.calendar-day,
.calendar-day-muted {
    height: 210px;
    max-height: 210px;
    overflow-y: auto;
    border-radius: 12px;
    padding: 10px;
    box-sizing: border-box;
}

.calendar-day {
    border: 1px solid #e2e2e2;
    background: white;
}

.calendar-day-muted {
    border: 1px solid #f1f1f1;
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

.closed-pill {
    border-radius: 999px;
    padding: 4px 8px;
    margin: 3px 0;
    font-size: 12px;
    display: inline-block;
    background: #f5f5f5;
    border: 1px solid #999;
    color: #555;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 共用工具
# =========================================================
def empty_booking_df() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def safe_rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def normalize_status(value) -> str:
    text = str(value).strip() if value is not None else ""

    if text in STATUS_OPTIONS:
        return text

    return "已預約"

def status_icon(status: str) -> str:
    return STATUS_ICON.get(normalize_status(status), "🔴")


def status_color(status: str) -> str:
    return STATUS_COLOR.get(normalize_status(status), STATUS_COLOR["已預約"])


def status_border(status: str) -> str:
    return STATUS_BORDER.get(normalize_status(status), STATUS_BORDER["已預約"])


def to_date_text(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

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
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if isinstance(value, datetime):
        return value.strftime("%H:%M")

    text = str(value).strip()
    if not text:
        return ""

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        return parsed.strftime("%H:%M")

    return text[:5] if len(text) >= 5 else text


# =========================================================
# 台灣政府行政機關辦公日曆
# =========================================================
@st.cache_data(ttl=60 * 60 * 24)
def load_taiwan_calendar() -> pd.DataFrame:
    """
    使用政府行政機關辦公日曆資料。
    isholiday = 是：休假日
    isholiday = 否：上班日，包含補班日

    使用 requests + verify=False 避免 Streamlit Cloud SSL 憑證錯誤。
    """
    url = "https://data.ntpc.gov.tw/api/datasets/308dcd75-6434-45bc-a95f-584da4fed251/csv?page=0&size=2000"

    try:
        response = requests.get(
            url,
            timeout=15,
            verify=False,
        )
        response.raise_for_status()

        holiday_df = pd.read_csv(StringIO(response.text))
        holiday_df.columns = [str(c).strip().lower() for c in holiday_df.columns]

        # 欄位相容處理
        rename_map = {}
        for col in holiday_df.columns:
            if col in ["日期"]:
                rename_map[col] = "date"
            elif col in ["是否放假"]:
                rename_map[col] = "isholiday"
            elif col in ["節日"]:
                rename_map[col] = "name"
            elif col in ["說明", "備註"]:
                rename_map[col] = "description"

        holiday_df = holiday_df.rename(columns=rename_map)

        if "date" not in holiday_df.columns:
            st.sidebar.error("國定假日資料缺少 date 欄位")
            return pd.DataFrame()

        if "isholiday" not in holiday_df.columns:
            st.sidebar.error("國定假日資料缺少 isholiday 欄位")
            return pd.DataFrame()

        if "name" not in holiday_df.columns:
            holiday_df["name"] = ""

        if "description" not in holiday_df.columns:
            holiday_df["description"] = ""

        holiday_df["date"] = (
            holiday_df["date"]
            .astype(str)
            .str.replace("-", "", regex=False)
            .str.strip()
        )

        holiday_df["isholiday"] = (
            holiday_df["isholiday"]
            .astype(str)
            .str.strip()
        )

        return holiday_df

    except Exception as e:
        st.sidebar.error("國定假日資料讀取失敗")
        st.sidebar.exception(e)
        return pd.DataFrame()


def is_closed_day(day_value: date) -> bool:
    """
    回傳是否不開放預約。

    規則：
    1. 若是一般勞工不放假的節日，例如軍人節，允許預約
    2. 若政府日曆 isholiday = 是，視為休假不開放
    3. 若政府日曆 isholiday = 否，視為上班日可預約
    4. 若政府日曆讀不到，退回六日不開放
    """
    day_text = day_value.strftime("%Y%m%d")
    holiday_df = load_taiwan_calendar()

    if holiday_df.empty:
        return day_value.weekday() >= 5

    row = holiday_df[holiday_df["date"].astype(str) == day_text]

    if row.empty:
        return day_value.weekday() >= 5

    if is_labor_working_holiday(day_value):
        return False

    isholiday = str(row.iloc[0].get("isholiday", "")).strip()

    if isholiday == "是":
        return True

    if isholiday == "否":
        return False

    return day_value.weekday() >= 5


def closed_day_name(day_value):
    day_text = day_value.strftime("%Y%m%d")
    holiday_df = load_taiwan_calendar()

    if holiday_df.empty:
        return ""

    row = holiday_df[
        holiday_df["date"].astype(str) == day_text
    ]

    if row.empty:
        return ""

    name = str(row.iloc[0]["name"])

    if is_labor_working_holiday(day_value):
        return f"🟢 {name}"

    if str(row.iloc[0]["isholiday"]) == "否":
        return f"🟦 {name}"

    return f"🚫 {name}"
    
def is_labor_working_holiday(day_value: date) -> bool:
    day_text = day_value.strftime("%Y%m%d")
    holiday_df = load_taiwan_calendar()

    if holiday_df.empty:
        return False

    row = holiday_df[holiday_df["date"].astype(str) == day_text]

    if row.empty:
        return False

    text = (
        str(row.iloc[0].get("name", "")) +
        str(row.iloc[0].get("description", ""))
    )

    return any(keyword in text for keyword in LABOR_WORKING_HOLIDAY_KEYWORDS)    


# =========================================================
# 資料處理
# =========================================================
def normalize_df(dataframe: pd.DataFrame | None) -> pd.DataFrame:
    if dataframe is None or dataframe.empty:
        return empty_booking_df()

    dataframe = dataframe.copy()

    for col in REQUIRED_COLUMNS:
        if col not in dataframe.columns:
            dataframe[col] = ""

    dataframe = dataframe[REQUIRED_COLUMNS].fillna("")

    # 移除 Google Sheet 完全空白列
    key_cols = ["resource_type", "resource_name", "booking_date", "start_time", "end_time", "applicant"]
    dataframe = dataframe[
        dataframe[key_cols]
        .astype(str)
        .apply(lambda row: any(cell.strip() for cell in row), axis=1)
    ].copy()

    if dataframe.empty:
        return empty_booking_df()

    dataframe["resource_type"] = dataframe["resource_type"].astype(str).str.strip()
    dataframe["resource_name"] = dataframe["resource_name"].astype(str).str.strip()
    dataframe["applicant"] = dataframe["applicant"].astype(str).str.strip()
    dataframe["purpose"] = dataframe["purpose"].astype(str).str.strip()
    dataframe["booking_date"] = dataframe["booking_date"].apply(to_date_text)
    dataframe["start_time"] = dataframe["start_time"].apply(to_time_text)
    dataframe["end_time"] = dataframe["end_time"].apply(to_time_text)

    dataframe.loc[~dataframe["resource_type"].isin(RESOURCE_OPTIONS.keys()), "resource_type"] = ""
    dataframe["status"] = dataframe["status"].apply(normalize_status)
    dataframe.loc[~dataframe["checkin"].isin(CHECKIN_OPTIONS), "checkin"] = "未簽到"

    blank_id_mask = dataframe["id"].astype(str).str.strip() == ""
    dataframe.loc[blank_id_mask, "id"] = [str(uuid.uuid4()) for _ in range(int(blank_id_mask.sum()))]

    return dataframe.reset_index(drop=True)


def load_data(force_fresh: bool = False) -> pd.DataFrame:
    if conn is None:
        st.sidebar.warning("目前使用本機空資料，尚未連線 Google Sheet")
        return empty_booking_df()

    try:
        dataframe = conn.read(worksheet=WORKSHEET_NAME, ttl=0 if force_fresh else 30)
        dataframe = normalize_df(dataframe)
        st.sidebar.success("雲端資料讀取成功")
        st.sidebar.caption(f"工作表：{WORKSHEET_NAME}")
        st.sidebar.caption(f"資料筆數：{len(dataframe)}")
        return dataframe

    except PermissionError:
        st.sidebar.error("Google Sheet 權限不足")
        st.error("Google Sheet 權限不足，請把 Service Account Email 加入 Google Sheet 編輯者。")
        return empty_booking_df()

    except Exception as e:
        st.sidebar.error("Google Sheet 讀取失敗")
        st.error("讀取 Google Sheet 失敗，系統暫時以空資料啟動。")
        st.exception(e)
        return empty_booking_df()


def save_data(dataframe: pd.DataFrame) -> bool:
    if conn is None:
        st.error("尚未連線 Google Sheet，無法同步資料。")
        return False

    try:
        dataframe = normalize_df(dataframe)

        if dataframe.empty:
            st.error("資料為空，已阻止覆蓋 Google Sheet。")
            return False

        dataframe = dataframe[REQUIRED_COLUMNS].copy()

        conn.update(
            worksheet=WORKSHEET_NAME,
            data=dataframe
        )

        return True

    except Exception as e:
        st.error("寫入 Google Sheet 失敗，詳細錯誤如下：")
        st.exception(e)
        return False

df = load_data()

# =========================================================
# 預約邏輯
# =========================================================
def parse_booking_datetime(booking_date_value, time_value) -> datetime | None:
    try:
        booking_date_text = to_date_text(booking_date_value)
        time_text = to_time_text(time_value)

        if not booking_date_text or not time_text:
            return None

        dt = datetime.strptime(
            f"{booking_date_text} {time_text}",
            "%Y-%m-%d %H:%M"
        )

        # 補上台灣時區
        return dt.replace(tzinfo=TW_TZ)

    except Exception:
        return None


def is_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a

def active_bookings(dataframe: pd.DataFrame) -> pd.DataFrame:
    """只回傳仍會佔用時段的有效預約。"""
    if dataframe is None or dataframe.empty:
        return empty_booking_df()

    return dataframe[
        ~dataframe["status"].isin(["已取消", "已結束", "已失效"])
    ].copy()


def has_booking_conflict(
    resource_type: str,
    resource_name: str,
    booking_date_value,
    start_time: str,
    end_time: str,
) -> bool:
    return get_conflict_booking(
        resource_type,
        resource_name,
        booking_date_value,
        start_time,
        end_time
    ) is not None


def get_conflict_booking(
    resource_type,
    resource_name,
    booking_date_value,
    start_time,
    end_time
):
    try:
        day_value = (
            booking_date_value
            if isinstance(booking_date_value, date)
            else pd.to_datetime(booking_date_value).date()
        )
    except Exception:
        return None

    if is_closed_day(day_value):
        return None

    query_start = parse_booking_datetime(booking_date_value, start_time)
    query_end = parse_booking_datetime(booking_date_value, end_time)

    if query_start is None or query_end is None or query_start >= query_end:
        return None

    related = active_bookings(df)
    related = related[
        (related["resource_type"] == resource_type)
        & (related["resource_name"] == resource_name)
        & (related["booking_date"] == to_date_text(booking_date_value))
    ]

    for _, row in related.iterrows():
        row_start = parse_booking_datetime(row["booking_date"], row["start_time"])
        row_end = parse_booking_datetime(row["booking_date"], row["end_time"])

        if row_start and row_end and is_overlap(
            query_start,
            query_end,
            row_start,
            row_end
        ):
            return row

    return None


def auto_release_expired_unchecked_bookings(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    自動釋出規則：
    1. 未簽到：只處理今天、已預約、開始後 15 分鐘仍未簽到，改成已失效並保留資料。
    2. 已簽到 / 使用中：只處理今天、結束時間到，改成已結束並保留資料。
    """
    now = datetime.now(TW_TZ)
    keep_rows = []
    released_count = 0

    for _, row in dataframe.iterrows():
        row = row.copy()
        row_status = normalize_status(row.get("status", ""))

        if row_status in ["已取消", "已結束", "已失效"]:
            keep_rows.append(row)
            continue

        start_dt = parse_booking_datetime(row["booking_date"], row["start_time"])
        end_dt = parse_booking_datetime(row["booking_date"], row["end_time"])

        if start_dt is None or end_dt is None:
            keep_rows.append(row)
            continue

        no_checkin_expired = (
            row_status == "已預約"
            and row["checkin"] == "未簽到"
            and start_dt.date() == now.date()
            and now > start_dt + timedelta(minutes=15)
        )

        usage_finished = (
            row_status == "使用中"
            and row["checkin"] == "已簽到"
            and end_dt.date() == now.date()
            and now >= end_dt
        )

        if no_checkin_expired:
            row["status"] = "已失效"
            row["closed_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            keep_rows.append(row)
            released_count += 1
            continue

        if usage_finished:
            row["status"] = "已結束"
            row["closed_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            keep_rows.append(row)
            released_count += 1
            continue

        keep_rows.append(row)

    result = pd.DataFrame(keep_rows) if keep_rows else empty_booking_df()
    return normalize_df(result), released_count


def cleanup_old_deleted_bookings(
    dataframe: pd.DataFrame
) -> tuple[pd.DataFrame, int]:
    """
    已取消 / 已結束 / 已失效資料保留 30 天。
    以 closed_time 起算；closed_time 為空則不刪除。
    """
    now = datetime.now(TW_TZ)
    keep_rows = []
    deleted_count = 0

    for _, row in dataframe.iterrows():
        row_status = normalize_status(row.get("status", ""))

        if row_status not in ["已取消", "已結束", "已失效"]:
            keep_rows.append(row)
            continue

        closed_time = str(row.get("closed_time", "")).strip()

        if not closed_time:
            keep_rows.append(row)
            continue

        closed_dt = pd.to_datetime(closed_time, errors="coerce")

        if pd.isna(closed_dt):
            keep_rows.append(row)
            continue

        if (now - closed_dt.to_pydatetime().replace(tzinfo=TW_TZ)).days >= 30:
            deleted_count += 1
            continue

        keep_rows.append(row)

    result = pd.DataFrame(keep_rows) if keep_rows else empty_booking_df()
    return normalize_df(result), deleted_count


def available_resources(resource_type: str, booking_date_value, start_time: str, end_time: str) -> list[str]:
    try:
        day_value = booking_date_value if isinstance(booking_date_value, date) else pd.to_datetime(booking_date_value).date()
    except Exception:
        return []

    if is_closed_day(day_value):
        return []

    return [
        resource_name
        for resource_name in RESOURCE_OPTIONS[resource_type]
        if not has_booking_conflict(resource_type, resource_name, booking_date_value, start_time, end_time)
    ]


def get_resource_status(resource_type: str, resource_name: str, target_date=None, target_start=None, target_end=None) -> str:
    """
    若 target_start / target_end 為 None，代表依現在時間判斷狀態。
    """
    now = datetime.now(TW_TZ)
    today_text = to_date_text(date.today())

    # 依現在時間判斷
    if target_start is None or target_end is None:
        related = active_bookings(df)
        related = related[
            (related["resource_type"] == resource_type)
            & (related["resource_name"] == resource_name)
            & (related["booking_date"] == today_text)
        ]

        if related.empty:
            return "閒置中"

        for _, row in related.iterrows():
            row_start = parse_booking_datetime(row["booking_date"], row["start_time"])
            row_end = parse_booking_datetime(row["booking_date"], row["end_time"])

            if row_start and row_end and row_start <= now <= row_end:
                return "使用中" if row["checkin"] == "已簽到" else "已預約"

        for _, row in related.iterrows():
            row_start = parse_booking_datetime(row["booking_date"], row["start_time"])
            if row_start and now < row_start:
                return "已預約"

        return "閒置中"

    query_start = parse_booking_datetime(target_date, target_start)
    query_end = parse_booking_datetime(target_date, target_end)

    if query_start is None or query_end is None or query_start >= query_end:
        return "已預約"

    related = active_bookings(df)
    related = related[
        (related["resource_type"] == resource_type)
        & (related["resource_name"] == resource_name)
        & (related["booking_date"] == to_date_text(target_date))
    ]

    if related.empty:
        return "閒置中"

    for _, row in related.iterrows():
        row_start = parse_booking_datetime(row["booking_date"], row["start_time"])
        row_end = parse_booking_datetime(row["booking_date"], row["end_time"])

        if row_start and row_end and is_overlap(query_start, query_end, row_start, row_end):
            return "使用中" if row["checkin"] == "已簽到" else "已預約"

    return "閒置中"


def day_status(resource_type: str, resource_name: str, day_value: date) -> str:

    if is_closed_day(day_value):
        return "休假"

    day_bookings = active_bookings(df)
    day_bookings = day_bookings[
        (day_bookings["resource_type"] == resource_type)
        & (day_bookings["resource_name"] == resource_name)
        & (day_bookings["booking_date"] == to_date_text(day_value))
    ]

    if day_bookings.empty:
        return "閒置中"

    # ==================================================
    # 計算當日已被預約總分鐘數
    # ==================================================

    total_minutes = 0

    for _, row in day_bookings.iterrows():

        start_dt = parse_booking_datetime(
            row["booking_date"],
            row["start_time"]
        )

        end_dt = parse_booking_datetime(
            row["booking_date"],
            row["end_time"]
        )

        if start_dt and end_dt:
            total_minutes += int(
                (end_dt - start_dt).total_seconds() / 60
            )

    # 08:00 ~ 18:00 = 10 小時 = 600 分鐘
    FULL_DAY_MINUTES = 600

    if total_minutes >= FULL_DAY_MINUTES:
        return "已滿"

    return "部分預約"


# 讀取主要資料：平常快取 30 秒，降低 Google Sheets API 429 風險
df = load_data()

# 自動釋出 / 30天清理：最多每 60 秒執行一次，且一定讀最新雲端資料，避免用舊資料覆蓋簽到時間
if "last_maintenance_time" not in st.session_state:
    st.session_state.last_maintenance_time = 0

if time.time() - st.session_state.last_maintenance_time >= 60:
    st.session_state.last_maintenance_time = time.time()

    latest_df = load_data(force_fresh=True)
    latest_df, released_count = auto_release_expired_unchecked_bookings(latest_df)
    latest_df, deleted_count = cleanup_old_deleted_bookings(latest_df)

    if released_count > 0 or deleted_count > 0:
        save_data(latest_df)

    df = latest_df
# =========================================================
# UI 元件
# =========================================================
def time_range_selector(prefix: str, default_index: int = 2) -> tuple[str, str]:
    start_time = st.selectbox(
        "開始時間",
        TIME_OPTIONS[:-1],
        index=default_index,
        key=f"{prefix}_start",
    )

    end_options = [t for t in TIME_OPTIONS if t > start_time]

    end_time = st.selectbox(
        "結束時間",
        end_options,
        index=0,
        key=f"{prefix}_end",
    )

    return start_time, end_time


def render_status_cards(resource_type: str, target_date=None, target_start=None, target_end=None) -> None:
    global df

    st.write(f"### {resource_type}即時狀態")
    st.caption(f"目前時間：{datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}")

    resources = RESOURCE_OPTIONS[resource_type]
    cols = st.columns(min(3, len(resources)))

    for idx, resource_name in enumerate(resources):
        status = get_resource_status(
            resource_type,
            resource_name,
            target_date,
            target_start,
            target_end
        )

        with cols[idx % len(cols)]:
            st.markdown(
                f'<div class="status-card" style="background:{status_color(status)}; border-left-color:{status_border(status)};">'
                f'<div class="status-title">{resource_name}</div>'
                f'<div style="font-size:24px; font-weight:700;">{status_icon(status)} {normalize_status(status)}</div>'
                f'<div class="status-sub">依目前時間自動判斷</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_booking_form(resource_type: str) -> None:
    st.write(f"### 新增{resource_type}預約")

    with st.form(f"{resource_type}_booking_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            booking_date_value = st.date_input(
                "預約日期",
                value=date.today(),
                key=f"{resource_type}_date",
            )
            resource_name = st.selectbox(
                f"選擇{resource_type}",
                RESOURCE_OPTIONS[resource_type],
                key=f"{resource_type}_name",
            )

        with c2:
            start_time, end_time = time_range_selector(f"{resource_type}_booking")

        with c3:
            applicant = st.text_input(
                "預約人",
                placeholder="請輸入姓名",
                key=f"{resource_type}_applicant",
            )
            purpose = st.text_input(
                "用途",
                placeholder="例：內部會議 / 外出洽公",
                key=f"{resource_type}_purpose",
            )

        submitted = st.form_submit_button(f"確認預約{resource_type}")

    if not submitted:
        return
    
    if is_closed_day(booking_date_value):
        st.error(f"{booking_date_value} 為 {closed_day_name(booking_date_value)}，不開放預約。")
        return

    if not applicant.strip():
        st.warning("請輸入預約人")
        return

    global df
    df = load_data(force_fresh=True)

    conflict = get_conflict_booking(
        resource_type,
        resource_name,
        booking_date_value,
        start_time,
        end_time
    )

    if conflict is not None:
    
        st.error(
            f"""
    ⚠️ 該時間已有預約！
    
    資源：{resource_name}
    
    預約人：{conflict['applicant']}
    
    時間：
    {conflict['start_time']} ~ {conflict['end_time']}
    """
        )
    
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
    "created_at": datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S"),
    "checkin_time": "",
    "closed_time": "",
}
    latest_df = load_data(force_fresh=True)
    
    updated_df = pd.concat(
        [latest_df, pd.DataFrame([new_row])],
        ignore_index=True
    )
    
    if save_data(updated_df):
        st.success(f"{resource_name} 已成功預約：{booking_date_value} {start_time}~{end_time}")
        safe_rerun()


def render_calendar(resource_type: str) -> None:
    st.write(f"### {resource_type}月曆")

    today = date.today()
    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        year = st.number_input(
            "年份",
            min_value=2024,
            max_value=2035,
            value=today.year,
            step=1,
            key=f"{resource_type}_calendar_year",
        )

    with c2:
        month = st.selectbox(
            "月份",
            list(range(1, 13)),
            index=today.month - 1,
            key=f"{resource_type}_calendar_month",
        )

    with c3:
        selected_resource = st.selectbox(
            f"選擇{resource_type}",
            RESOURCE_OPTIONS[resource_type],
            key=f"{resource_type}_calendar_resource",
        )

    st.caption("圖例：🟢 閒置中　🟠 使用中　🔴 已預約　🚫 休假不開放")

    weekday_cols = st.columns(7)
    for col, name in zip(weekday_cols, ["日", "一", "二", "三", "四", "五", "六"]):
        col.markdown(f"**{name}**")

    month_calendar = calendar.Calendar(firstweekday=6).monthdatescalendar(int(year), int(month))

    for week in month_calendar:
        cols = st.columns(7)

        for col, day_value in zip(cols, week):
            in_current_month = day_value.month == int(month)
            css_class = "calendar-day" if in_current_month else "calendar-day-muted"

            if not in_current_month:
                col.markdown(
                    f'<div class="{css_class}"><div class="calendar-date">{day_value.day}</div></div>',
                    unsafe_allow_html=True,
                )
                continue

            if is_closed_day(day_value):
                name = closed_day_name(day_value)
                col.markdown(
                    f'<div class="{css_class}">'
                    f'<div class="calendar-date">{day_value.day} 🚫</div>'
                    f'<div class="closed-pill">{name}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                continue

            status = normalize_status(day_status(resource_type, selected_resource, day_value))

            day_bookings = df[
                (df["resource_type"] == resource_type)
                & (df["resource_name"] == selected_resource)
                & (df["booking_date"] == to_date_text(day_value))
            ].sort_values(["start_time"])

            booking_lines = ""

            if day_bookings.empty:
                booking_lines = (
                    f'<div class="slot-pill" '
                    f'style="background:{STATUS_COLOR["閒置中"]}; border-color:{STATUS_BORDER["閒置中"]};">'
                    f'🟢 全天可預約</div>'
                )
            else:
                booking_lines = ""

            for _, row in day_bookings.iterrows():
                row_status = normalize_status(row.get("status", "已預約"))
                row_start = to_time_text(row.get("start_time", ""))
                row_end = to_time_text(row.get("end_time", ""))
                applicant = str(row.get("applicant", "")).strip()
            
                if not row_start or not row_end:
                    continue
            
                if is_closed_status(row_status):
                    booking_lines += (
                        f'<div class="slot-pill" '
                        f'style="background:#eeeeee; '
                        f'border-color:#999; '
                        f'color:#888; '
                        f'text-decoration:line-through; '
                        f'display:block; width:100%; box-sizing:border-box; '
                        f'white-space:normal;">'
                        f'{row_start}-{row_end}'
                        f'<br><span style="font-size:11px;">{applicant}</span>'
                        f'</div>'
                    )
                else:
                    booking_lines += (
                        f'<div class="slot-pill" '
                        f'style="background:{status_color(row_status)}; '
                        f'border-color:{status_border(row_status)}; '
                        f'display:block; width:100%; box-sizing:border-box; '
                        f'white-space:normal;">'
                        f'{status_icon(row_status)} {row_start}-{row_end}'
                        f'<br><span style="font-size:11px; color:#555;">{applicant}</span>'
                        f'</div>'
                    )

                if not booking_lines:
                    booking_lines = (
                        f'<div class="slot-pill" '
                        f'style="background:{STATUS_COLOR["閒置中"]}; border-color:{STATUS_BORDER["閒置中"]};">'
                        f'🟢 全天可預約</div>'
                    )

            col.markdown(
                f'<div class="{css_class}">'
                f'<div class="calendar-date">{day_value.day} {status_icon(status)}</div>'
                f'{booking_lines}'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_booking_table(resource_type: str) -> None:
    st.write(f"### {resource_type}預約紀錄 / 簽到管理")

    sub_df = df[(df["resource_type"] == resource_type) & (~df["status"].isin(["已取消", "已結束", "已失效"]))].copy()

    if sub_df.empty:
        st.info(f"目前沒有{resource_type}預約紀錄。")
        return

    sub_df = sub_df.sort_values(["booking_date", "start_time"])

    for _, row in sub_df.iterrows():
        row_id = str(row["id"])

        is_deleted_style = is_closed_status(row["status"])
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

            
###########################################################################################################################################################
            with c1:
                if is_deleted_style:
                    st.markdown(f"<span style='color:#888;'>~~**{row['resource_name']}**~~</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:#888;'>~~{row['booking_date']} {row['start_time']}~{row['end_time']}~~</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{row['resource_name']}**")
                    st.caption(f"{row['booking_date']} {row['start_time']}~{row['end_time']}")
            
            with c2:
                if is_deleted_style:
                    st.markdown(f"<span style='color:#888;'>~~預約人：{row['applicant']}~~</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:#888;'>~~用途：{row['purpose'] if row['purpose'] else '未填寫'}~~</span>", unsafe_allow_html=True)
                else:
                    st.write(f"預約人：{row['applicant']}")
                    st.write(f"用途：{row['purpose'] if row['purpose'] else '未填寫'}")
            
            with c3:
                if is_deleted_style:
                    st.markdown(f"<span style='color:#888;'>~~狀態：{normalize_status(row['status'])}~~</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:#888;'>~~簽到：{row['checkin']}~~</span>", unsafe_allow_html=True)
                else:
                    st.write(f"狀態：{status_icon(row['status'])} {normalize_status(row['status'])}")
                    st.write(f"簽到：{row['checkin']}")

            with c4:
                if row["checkin"] == "未簽到":
                    if st.button("簽到並開始使用", key=f"checkin_{row_id}"):
                        latest_df = load_data(force_fresh=True)
                        latest_df["id"] = latest_df["id"].astype(str)
                    
                        mask = latest_df["id"] == row_id
                    
                        if not mask.any():
                            st.error("找不到這筆預約資料，請重新同步後再試。")
                            return
                    
                        latest_df.loc[mask, "checkin"] = "已簽到"
                        latest_df.loc[mask, "status"] = "使用中"
                        latest_df.loc[mask, "checkin_time"] = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
                        latest_df.loc[mask, "closed_time"] = ""
                    
                        if save_data(latest_df):
                            st.success("簽到成功，已開始使用。")
                            safe_rerun()
                        else:
                            st.error("簽到失敗，Google Sheet 沒有寫入成功。")
                else:
                    if st.button("結束使用並釋出", key=f"finish_{row_id}"):
                        new_df = df.copy()
                        new_df.loc[new_df["id"] == row_id, "status"] = "已結束"
                        new_df.loc[new_df["id"] == row_id,"closed_time"] = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    
                        if save_data(new_df):
                            safe_rerun()

                if st.button("取消預約", key=f"cancel_{row_id}"):
                    new_df = df.copy()
                    new_df.loc[new_df["id"] == row_id, "status"] = "已取消"
                    new_df.loc[new_df["id"] == row_id,"closed_time"] = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    new_df.loc[new_df["id"] == row_id, "checkin"] = "未簽到"
                
                    if save_data(new_df):
                        safe_rerun()


def render_unreserved_search() -> None:
    st.write("### 未預約搜尋")

    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        search_date = st.date_input("搜尋日期", value=date.today(), key="search_date")

    with c2:
        start_time, end_time = time_range_selector("search")

    with c3:
        resource_filter = st.selectbox(
            "資源類型",
            ["全部", "會議室", "公務車"],
            key="search_resource_type",
        )

    st.write("---")

    if is_closed_day(search_date):
        st.warning(f"{search_date} 為 {closed_day_name(search_date)}，不開放預約。")
        return

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
    st.info("可任選日期與時段預約；開始後 15 分鐘未簽到會自動釋出；六日與國定假日不開放預約。")

    render_status_cards(resource_type, date.today(), None, None)

    st.write("---")
    render_booking_form(resource_type)

    st.write("---")
    render_calendar(resource_type)

    st.write("---")
    render_booking_table(resource_type)


# =========================================================
# 側邊欄
# =========================================================
st.sidebar.write("### 系統狀態")
st.sidebar.write(f"目前時間：{datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}")

holiday_df = load_taiwan_calendar()
st.sidebar.caption(f"國定假日資料筆數：{len(holiday_df)}")

if st.sidebar.button("🔄 手動重新同步"):
    safe_rerun()

if st.sidebar.button("🧹 清除假日快取"):
    st.cache_data.clear()
    safe_rerun()

st.sidebar.caption("系統每 300 秒自動刷新一次。")
st.sidebar.caption("工作表名稱固定使用 Tasks。")

# =========================================================
# 主畫面：只保留三個分頁
# =========================================================
tab1, tab2, tab3 = st.tabs([
    "🏢 預約辦公室",
    "🚗 預約公務車",
    "🔍 未預約搜尋",
])

with tab1:
    render_resource_page("會議室")

with tab2:
    render_resource_page("公務車")

with tab3:
    render_unreserved_search()
