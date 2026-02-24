import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# --- 0. 設定與連線 ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_NAME = 'gauge_db'
JSON_FILE = 'service_account.json'

@st.cache_resource
def connect_google_sheet():
    if os.path.exists(JSON_FILE):
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, SCOPE)
    else:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME)
    return sheet

# 安全氣囊：捕捉超速錯誤
try:
    sh = connect_google_sheet()
    ws_gauges = sh.worksheet('gauges')
    ws_logs = sh.worksheet('logs')
    ws_users = sh.worksheet('users')
except Exception as e:
    if "429" in str(e):
        st.warning("⏳ 點擊速度太快囉！Google 伺服器正在喘氣，請等待 15 秒後再重新整理網頁。")
        st.stop()
    else:
        st.error(f"連線失敗！\n錯誤訊息: {e}")
        st.stop()

# --- i18n 多語言字典 ---
TRANSLATIONS = {
    'zh': {
        'title': "☁️ 雲端量具借出系統",
        'role_select': "請選擇您的身份",
        'role_user': "使用者 (操作)",
        'role_admin': "管理員 (後台)",
        'password': "管理員密碼",
        'login_first': "請先選擇您的姓名",
        'tab_borrow': "我要借出 📥",
        'tab_return': "我要歸還 📤",
        'tab_status': "查詢狀態 🔍",
        'btn_borrow': "借出",
        'btn_return_request': "申請歸還 (待驗收)",
        'btn_confirm_return': "確認入庫 (結案)",
        'btn_not_owner': "非本人",
        'status_avail': "可借出",
        'status_borrowed': "已借出",
        'status_pending': "待確認",
        'category_filter': "📂 篩選分類",
        'user_filter': "👤 篩選借用人",
        'all_options': "全部顯示",
        'admin_tab_status': "📊 現況",
        'admin_tab_verify': "✅ 歸還驗收",
        'admin_tab_repair': "🔧 待修回",
        'admin_tab_users': "👥 人員",
        'admin_tab_gauges': "➕ 量具",
        'admin_tab_logs': "📝 紀錄",
        'col_id': "編號", 'col_cat': "分類", 'col_spec': "規格",
        'col_user': "目前持有人", 'col_status': "狀態", 'col_time': "借出時間",
        'col_days': "天數", 'col_note': "備註",
        'msg_no_data': "查無資料", 'msg_success_add': "新增成功", 'msg_success_del': "刪除成功",
        'label_name': "輸入姓名", 'label_id': "量具編號", 'label_cat': "分類", 'label_spec': "規格",
        'label_note': "驗收/異常備註", 'ph_note': "若送修或報廢，請填寫原因...",
        'days_unit': "天",
        'font_slider': "🔍 調整字體大小",
        'avail_gauges': "✅ 庫存量具",
        'msg_no_avail