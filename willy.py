# 第 1 行：導入 Streamlit 套件，用來製作網頁前端介面

import streamlit as st

# 第 2 行：導入 Pandas 套件，它是 Python 處理表格資料（DataFrame）的黃金工具

import pandas as pd

# 第 3 行：從安裝好的雲端連線庫中，導入「GSheetsConnection」這個連線核心元件

#  這裡踩過地雷：雖然下載叫 st-gsheets-connection，但寫代碼導入時必須叫 streamlit_gsheets

from streamlit_gsheets import GSheetsConnection

# 第 4 行：在網頁上印出大標題

st.title(" 闕老師的雲端資料庫連線測試")

# ==========================================

#  核心連線設定：呼叫 Streamlit 內建的連線工廠

# ==========================================

# 第 5 行：建立一個名為 conn 的連接器。

# 它會自動跑去讀取 Streamlit Cloud 後台 Secrets 裡的 [connections.gsheets] 設定

conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================

#  第一動：從雲端把試算表「讀取」出來

# ==========================================

st.write("### 1. 目前雲端資料庫的內容：")

# 第 6 行：透過連線器執行 .read() 指令，指定去讀取名為 "Tasks" 的分頁

#  這裡踩過地雷：ttl="0" 代表快取時間為 0 秒，強迫它每次重新整理都必須「即時」去雲端抓最新資料，不能用舊記憶

df = conn.read(worksheet="Tasks", ttl="0")

# 第 7 行：在網頁上直接把讀出來的 Pandas 表格（DataFrame）用網頁表格組件渲染出來

st.dataframe(df)

# ==========================================

#  第二動：從網頁「寫入」新資料回雲端

# ==========================================

st.write("---")

st.write("### 2. 測試寫入一筆新任務：")

# 第 8 行：建立一個網頁按鈕，當使用者點擊這個按鈕時，下方的變數 if 條件會成立

if st.button("點我！自動新增一筆資料到雲端"):

    # 第 9 行：運用前幾堂課學到的「字典結構」，包裝我們要塞進去的新資料

    # 裡面的 Key (title, status, owner) 必須和我們在 Excel 第一列手動打的字分毫不差

    new_data = {"title": "網頁新增的任務", "status": "To Do", "owner": "Python機器人"}

    # 第 10 行：把這個字典轉換成 Pandas 認得的單行表格物件（DataFrame）

    new_row = pd.DataFrame([new_data])

    # 第 11 行：將原本舊的表格（df）與新的單行表格（new_row）黏在一起

    #  這裡踩過地雷：新版 Python 廢棄了 .append()，在雲端環境必須改用 pd.concat() 進行表格拼接

    updated_df = pd.concat([df, new_row], ignore_index=True)

    # 第 12 行：透過連線器執行 .update() 指令，把拼接完的全新大表格，整砣蓋回雲端的 "Tasks" 分頁

    conn.update(worksheet="Tasks", data=updated_df)

    # 第 13 行：在網頁上噴出綠色的成功提示小框框

    st.success(" 恭喜！資料已成功跨越網路，寫入 Google 試算表！")

    # 第 14 行：強制網頁自我重新整理（Rerun），這會讓程式重新回到第 6 行，抓到剛剛寫進去的最新表格

    st.rerun()
