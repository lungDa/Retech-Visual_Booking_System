# StreamFlow Resource App

智慧資源預約系統，已整理為 StreamFlow 標準多檔架構。

## 檔案結構

```text
StreamFlow_Resource_App
├── app.py
├── utils.py
├── requirements.txt
└── pages
    ├── 1_預約辦公室.py
    ├── 2_預約公務車.py
    └── 3_未預約搜尋.py
```

## 執行方式

```bash
streamlit run app.py
```

## Google Sheet

工作表名稱固定使用 `Tasks`。
必要欄位由 `utils.py` 的 `REQUIRED_COLUMNS` 管理。
