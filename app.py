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
        'font_slider': "🔍 調整字體大小"
    },
    'en': {
        'title': "☁️ Cloud Gauge System",
        'role_select': "Select Role",
        'role_user': "User (Operation)",
        'role_admin': "Admin (Backend)",
        'password': "Admin Password",
        'login_first': "Please select your name",
        'tab_borrow': "Borrow 📥",
        'tab_return': "Return 📤",
        'tab_status': "Status 🔍",
        'btn_borrow': "Borrow",
        'btn_return_request': "Request Return",
        'btn_confirm_return': "Confirm & Close",
        'btn_not_owner': "Not Owner",
        'status_avail': "Available",
        'status_borrowed': "Borrowed",
        'status_pending': "Pending Inspection",
        'category_filter': "📂 Filter by Category",
        'user_filter': "👤 Filter by User",
        'all_options': "Show All",
        'admin_tab_status': "📊 Dashboard",
        'admin_tab_verify': "✅ Verification",
        'admin_tab_users': "👥 Users",
        'admin_tab_gauges': "➕ Gauges",
        'admin_tab_logs': "📝 Logs",
        'col_id': "ID", 'col_cat': "Category", 'col_spec': "Spec",
        'col_user': "Holder", 'col_status': "Status", 'col_time': "Time",
        'col_days': "Days", 'col_note': "Note",
        'msg_no_data': "No Data", 'msg_success_add': "Added Successfully", 'msg_success_del': "Deleted Successfully",
        'label_name': "Enter Name", 'label_id': "Gauge ID", 'label_cat': "Category", 'label_spec': "Spec",
        'label_note': "Inspection Note", 'ph_note': "If repair/scrap, enter reason...",
        'days_unit': "days",
        'font_slider': "🔍 Adjust Font Size"
    }
}


# --- 1. 資料庫操作函數 (已加入快取與效能優化) ---

@st.cache_data(ttl=30)
def get_gauges():
    data = ws_gauges.get_all_records()
    cols = ['id', 'category', 'spec', 'status', 'current_user', 'borrow_time', 'note']
    if not data:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(data)


@st.cache_data(ttl=600)
def get_users():
    data = ws_users.get_all_records()
    if not data: return pd.DataFrame(columns=['name'])
    return pd.DataFrame(data)


@st.cache_data(ttl=30)
def get_logs():
    data = ws_logs.get_all_records()
    if not data: return pd.DataFrame(columns=['gauge_id', 'action', 'user', 'timestamp'])
    df = pd.DataFrame(data)
    if not df.empty: df = df.iloc[::-1]
    return df


def add_user(name):
    try:
        cell = ws_users.find(name)
        if cell: return False
    except:
        pass
    ws_users.append_row([name])
    st.cache_data.clear()
    return True


def delete_user(name):
    try:
        cell = ws_users.find(name)
        ws_users.delete_rows(cell.row)
        st.cache_data.clear()
        return True
    except:
        return False


def add_gauge(gauge_id, category, spec):
    try:
        cell = ws_gauges.find(gauge_id)
        if cell: return False
    except:
        pass
    ws_gauges.append_row([gauge_id, category, spec, '可借出', '', '', ''])
    st.cache_data.clear()
    return True


def delete_gauge(gauge_id):
    try:
        cell = ws_gauges.find(gauge_id)
        ws_gauges.delete_rows(cell.row)
        st.cache_data.clear()
        return True
    except:
        return False


def update_status(gauge_id, action, user, note=""):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df = get_gauges()
    try:
        idx = df[df['id'] == gauge_id].index[0]
        row_idx = int(idx) + 2
    except:
        return

    # 打包更新 (Batch Update) 減少 Google API 請求次數
    if action == 'borrow':
        ws_gauges.update(range_name=f'D{row_idx}:G{row_idx}', values=[['已借出', user, now_str, '']])
        log_action = "借出"
    elif action == 'return_request':
        ws_gauges.update(range_name=f'D{row_idx}', values=[['待確認']])
        log_action = "申請歸還"
    elif action == 'confirm_return':
        ws_gauges.update(range_name=f'D{row_idx}:G{row_idx}', values=[['可借出', '', '', note]])
        log_action = f"歸還驗收 ({note})" if note else "歸還驗收"
    elif action == 'takeover':
        ws_gauges.update(range_name=f'D{row_idx}:G{row_idx}', values=[['已借出', user, now_str, '']])
        log_action = f"急件接手 (原持有人: {note})"
    elif action == 'repair':
        ws_gauges.update(range_name=f'D{row_idx}:G{row_idx}', values=[['待修', '', '', note]])
        log_action = f"轉交送修 ({note})" if note else "轉交送修"
    elif action == 'scrap':
        ws_gauges.delete_rows(row_idx)
        log_action = f"報廢移除 ({note})" if note else "報廢移除"

    ws_logs.append_row([gauge_id, log_action, user, now_str])
    st.cache_data.clear()


# 恢復為：滿 24 小時才算 1 天
def calculate_days(borrow_time_str):
    if not borrow_time_str: return 0
    try:
        borrow_date = datetime.strptime(borrow_time_str, "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - borrow_date
        return delta.days
    except:
        return 0


# --- 2. 應用程式介面 (UI) ---

def main():
    st.set_page_config(page_title="Cloud Gauge System", page_icon="☁️", layout="wide")

    if 'lang' not in st.session_state: st.session_state.lang = 'zh'

    # 語言與字體調整放在側邊欄
    lang_opt = st.sidebar.radio("Language / 語言", ['中文', 'English'])
    st.session_state.lang = 'zh' if lang_opt == '中文' else 'en'
    t = TRANSLATIONS[st.session_state.lang]

    # 字體大小拉桿
    st.sidebar.markdown("---")
    font_size = st.sidebar.slider(t['font_slider'], min_value=14, max_value=32, value=18, step=2)

    # 動態注入 CSS 魔法來放大字體
    st.markdown(f"""
        <style>
        /* 一般文字、提示框 */
        p, div, span, label {{
            font-size: {font_size}px !important;
        }}

        /* 按鈕 */
        .stButton > button {{
            font-size: {font_size}px !important;
            font-weight: bold !important;
        }}

        /* 輸入框與選單 */
        div[data-baseweb="select"] *, 
        input[type="text"], input[type="password"] {{
            font-size: {font_size}px !important;
        }}

        /* 頁籤 Tabs */
        .stTabs [data-baseweb="tab-list"] button {{
            font-size: {font_size + 2}px !important;
            font-weight: bold !important;
        }}

        /* 資料表格 */
        [data-testid="stDataFrame"] * {{
            font-size: {font_size - 2}px !important;
        }}
        </style>
    """, unsafe_allow_html=True)

    st.title(t['title'])
    role = st.sidebar.selectbox(t['role_select'], [t['role_user'], t['role_admin']])

    # --- 使用者介面 ---
    if role == t['role_user']:
        df_users = get_users()
        if df_users.empty:
            st.warning(t['msg_no_data'])
        else:
            user_list = df_users['name'].astype(str).tolist()
            current_user_name = st.selectbox(t['login_first'], user_list)

            tab_borrow, tab_return, tab_status = st.tabs([t['tab_borrow'], t['tab_return'], t['tab_status']])
            df_gauges = get_gauges()

            # === 借出分頁 (含待驗收接手功能) ===
            with tab_borrow:
                if not df_gauges.empty:
                    categories = [t['all_options']] + list(df_gauges['category'].unique())
                    selected_cat = st.selectbox(t['category_filter'], categories)

                    available = df_gauges[df_gauges['status'] == '可借出']
                    pending = df_gauges[df_gauges['status'] == '待確認']

                    if selected_cat != t['all_options']:
                        available = available[available['category'] == selected_cat]
                        pending = pending[pending['category'] == selected_cat]
                else:
                    available = pd.DataFrame()
                    pending = pd.DataFrame()

                # 顯示正常可借出的
                st.markdown("#### ✅ 庫存量具")
                if not available.empty:
                    for index, row in available.iterrows():
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.info(f"📍 **{row['id']}** | {row['category']} | 📏 {row['spec']}")
                        with col2:
                            if st.button(t['btn_borrow'], key=f"borrow_{row['id']}"):
                                update_status(row['id'], 'borrow', current_user_name)
                                st.rerun()
                else:
                    st.write("此分類目前無可借出量具。")

                st.divider()

                # 顯示待驗收但可接手的
                st.markdown("#### ⏳ 待品保驗收 (若急用可直接接手)")
                if not pending.empty:
                    for index, row in pending.iterrows():
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.warning(
                                f"📍 **{row['id']}** | {row['category']} | 📏 {row['spec']} (原借用人: {row['current_user']})")
                        with col2:
                            if st.button("急件接手", key=f"takeover_{row['id']}",
                                         help="直接接手會將此量具轉移到您名下"):
                                update_status(row['id'], 'takeover', current_user_name, note=row['current_user'])
                                st.rerun()
                else:
                    st.write("目前無待驗收項目。")

            # === 歸還 ===
            with tab_return:
                df_gauges = get_gauges()

                borrowers = [t['all_options']] + list(
                    df_gauges[df_gauges['status'].isin(['已借出', '待確認'])]['current_user'].unique())
                borrowers = [x for x in borrowers if x]

                col_filter1, col_filter2 = st.columns(2)
                with col_filter1:
                    selected_user_filter = st.selectbox(t['user_filter'], borrowers)

                borrowed = df_gauges[df_gauges['status'].isin(['已借出', '待確認'])]
                if selected_user_filter != t['all_options']:
                    borrowed = borrowed[borrowed['current_user'] == selected_user_filter]

                if not borrowed.empty:
                    for index, row in borrowed.iterrows():
                        days = calculate_days(row['borrow_time'])
                        is_owner = (str(row['current_user']) == str(current_user_name))

                        col1, col2 = st.columns([4, 1])
                        with col1:
                            status_text = f" ({t['status_pending']})" if row['status'] == '待確認' else ""
                            info_text = f"📍 {row['id']} | {row['category']} [{row['spec']}] - 👤 {row['current_user']} ({days} {t['days_unit']}){status_text}"

                            if row['status'] == '待確認':
                                st.warning(info_text + " ⏳")
                            elif is_owner:
                                st.success(info_text)
                            else:
                                st.error(info_text)

                        with col2:
                            if row['status'] == '待確認':
                                st.write("⏳ Wait Admin")
                            elif is_owner:
                                if st.button(t['btn_return_request'], key=f"ret_req_{row['id']}"):
                                    update_status(row['id'], 'return_request', current_user_name)
                                    st.rerun()
                            else:
                                st.button(t['btn_not_owner'], key=f"dis_{row['id']}", disabled=True)
                else:
                    st.info(t['msg_no_data'])

            # === 查詢 ===
            with tab_status:
                st.subheader(t['tab_status'])
                if not df_gauges.empty:
                    view_df = df_gauges[
                        ['id', 'category', 'spec', 'status', 'current_user', 'borrow_time', 'note']].copy()
                    view_df.columns = [t['col_id'], t['col_cat'], t['col_spec'], t['col_status'], t['col_user'],
                                       t['col_time'], t['col_note']]
                    st.dataframe(view_df, use_container_width=True)
                else:
                    st.info(t['msg_no_data'])

    # --- 管理員介面 ---
    elif role == t['role_admin']:
        st.header("Backend")
        password = st.sidebar.text_input(t['password'], type="password")
        if password == "0000":  # 你的密碼
            tab1, tab_verify, tab2, tab3, tab4 = st.tabs(
                [t['admin_tab_status'], t['admin_tab_verify'], t['admin_tab_users'], t['admin_tab_gauges'],
                 t['admin_tab_logs']])

            # 1. 現況
            with tab1:
                df_gauges = get_gauges()
                borrowed = df_gauges[df_gauges['status'] == '已借出'].copy()
                if not borrowed.empty:
                    borrowed['Days'] = borrowed['borrow_time'].apply(calculate_days)
                    display_df = borrowed[['id', 'category', 'spec', 'current_user', 'Days']]
                    st.dataframe(display_df, use_container_width=True)
                else:
                    st.success("目前無借出項目")

            # 2. 歸還驗收 (三按鈕版)
            with tab_verify:
                st.subheader(t['admin_tab_verify'])
                df_gauges = get_gauges()
                pending_items = df_gauges[df_gauges['status'] == '待確認']

                if not pending_items.empty:
                    for index, row in pending_items.iterrows():
                        with st.container():
                            st.markdown(f"### 📦 {row['id']} - {row['category']}")

                            c1, c2, c3 = st.columns([2, 2, 3])
                            with c1:
                                st.write(f"**規格:** {row['spec']}")
                                st.write(f"**歸還人:** {row['current_user']}")
                            with c2:
                                note = st.text_input(t['label_note'], placeholder=t['ph_note'], key=f"note_{row['id']}")
                            with c3:
                                st.write("")
                                btn_c1, btn_c2, btn_c3 = st.columns(3)
                                with btn_c1:
                                    if st.button("✅ 入庫", key=f"ok_{row['id']}", use_container_width=True):
                                        update_status(row['id'], 'confirm_return', row['current_user'], note)
                                        st.success("已入庫！")
                                        st.rerun()
                                with btn_c2:
                                    if st.button("🔧 送修", key=f"rep_{row['id']}", use_container_width=True):
                                        update_status(row['id'], 'repair', row['current_user'], note)
                                        st.warning("已轉為待修狀態！")
                                        st.rerun()
                                with btn_c3:
                                    if st.button("🗑️ 報廢", type="primary", key=f"scr_{row['id']}",
                                                 use_container_width=True):
                                        update_status(row['id'], 'scrap', row['current_user'], note)
                                        st.error("已報廢並移出總表！")
                                        st.rerun()
                            st.divider()
                else:
                    st.info("目前沒有待驗收的歸還申請。")

            # 3. 人員
            with tab2:
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    new_user = st.text_input(t['label_name'])
                    if st.button("Add"):
                        if new_user and add_user(new_user): st.success("Added"); st.rerun()
                with col_u2:
                    df_users = get_users()
                    if not df_users.empty:
                        del_user = st.selectbox("Delete", df_users['name'].astype(str))
                        if st.button("Delete"): delete_user(del_user); st.success("Deleted"); st.rerun()

            # 4. 量具
            with tab3:
                col_add, col_del = st.columns(2)
                with col_add:
                    st.markdown("#### Add")
                    new_id = st.text_input(t['label_id'])
                    new_cat = st.text_input(t['label_cat'])
                    new_spec = st.text_input(t['label_spec'])
                    if st.button("Add Gauge"):
                        if new_id and new_cat:
                            if add_gauge(new_id, new_cat, new_spec):
                                st.success("Added");
                                st.rerun()
                            else:
                                st.error("ID Exists")
                with col_del:
                    st.markdown("#### Delete")
                    df_all = get_gauges()
                    if not df_all.empty:
                        options = [f"{row['id']} ({row['spec']})" for i, row in df_all.iterrows()]
                        selection = st.selectbox("Select ID", options)
                        real_id = selection.split(" ")[0]
                        if st.button("Confirm Delete"): delete_gauge(real_id); st.success("Deleted"); st.rerun()

            # 5. 紀錄
            with tab4:
                st.dataframe(get_logs(), use_container_width=True)


if __name__ == "__main__":
    main()