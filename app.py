import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os  # <--- 新增這行，用來檢查檔案是否存在

# --- 0. 設定與連線 (改良版：優先檢查本地檔案) ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_NAME = 'gauge_db'
JSON_FILE = 'service_account.json'


@st.cache_resource
def connect_google_sheet():
    # 邏輯修改：先檢查本地有沒有 json 檔案
    if os.path.exists(JSON_FILE):
        # --- 本地模式 (你的電腦) ---
        # 找到了 json 檔，直接使用它
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, SCOPE)
    else:
        # --- 雲端模式 (Streamlit Cloud) ---
        # 找不到 json 檔，代表在雲端，改讀 Secrets
        # 注意：這行只有在雲端才會被執行，所以本地不會報錯
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME)
    return sheet


# 嘗試連線
try:
    sh = connect_google_sheet()
    ws_gauges = sh.worksheet('gauges')
    ws_logs = sh.worksheet('logs')
    ws_users = sh.worksheet('users')
except Exception as e:
    st.error(f"連線失敗！\n錯誤訊息: {e}")
    st.stop()

# --- i18n 多語言字典 ---
TRANSLATIONS = {
    'zh': {
        'title': "☁️  量具借出系統",
        'role_select': "請選擇您的身份",
        'role_user': "使用者 (操作)",
        'role_admin': "管理員 (後台)",
        'password': "管理員密碼",
        'login_first': "請先選擇您的姓名",
        'tab_borrow': "我要借出 📥",
        'tab_return': "我要歸還 📤",
        'tab_status': "查詢狀態 🔍",
        'btn_borrow': "借出",
        'btn_return': "歸還",
        'btn_not_owner': "非本人",
        'status_avail': "可借出",
        'status_borrowed': "已借出",
        'category_filter': "📂 篩選分類",
        'all_categories': "全部顯示",
        'admin_tab_status': "📊 現況",
        'admin_tab_users': "👥 人員",
        'admin_tab_gauges': "➕ 量具",
        'admin_tab_logs': "📝 紀錄",
        'col_id': "編號", 'col_cat': "分類", 'col_spec': "規格",
        'col_user': "目前持有人", 'col_status': "狀態", 'col_time': "借出時間", 'col_days': "天數",
        'msg_no_data': "查無資料", 'msg_success_add': "新增成功", 'msg_success_del': "刪除成功",
        'label_name': "輸入姓名", 'label_id': "量具編號 (ID)", 'label_cat': "分類",
        'label_spec': "規格", 'ph_spec': "例如: 0-25mm", 'days_unit': "天"
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
        'btn_borrow': "Borrow", 'btn_return': "Return", 'btn_not_owner': "Not Owner",
        'status_avail': "Available", 'status_borrowed': "Borrowed",
        'category_filter': "📂 Filter by Category", 'all_categories': "Show All",
        'admin_tab_status': "📊 Dashboard", 'admin_tab_users': "👥 Users",
        'admin_tab_gauges': "➕ Gauges", 'admin_tab_logs': "📝 Logs",
        'col_id': "ID", 'col_cat': "Category", 'col_spec': "Spec",
        'col_user': "Holder", 'col_status': "Status", 'col_time': "Time", 'col_days': "Days",
        'msg_no_data': "No Data", 'msg_success_add': "Added Successfully", 'msg_success_del': "Deleted Successfully",
        'label_name': "Enter Name", 'label_id': "Gauge ID", 'label_cat': "Category",
        'label_spec': "Specification", 'ph_spec': "e.g., 0-25mm", 'days_unit': "days"
    }
}


# --- 1. 資料庫操作函數 (含空值防呆) ---

def get_gauges():
    data = ws_gauges.get_all_records()
    if not data:
        return pd.DataFrame(columns=['id', 'category', 'spec', 'status', 'current_user', 'borrow_time'])
    return pd.DataFrame(data)


def get_users():
    data = ws_users.get_all_records()
    if not data:
        return pd.DataFrame(columns=['name'])
    return pd.DataFrame(data)


def get_logs():
    data = ws_logs.get_all_records()
    if not data:
        return pd.DataFrame(columns=['gauge_id', 'action', 'user', 'timestamp'])

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.iloc[::-1]
    return df


def add_user(name):
    try:
        cell = ws_users.find(name)
        if cell: return False
    except:
        pass
    ws_users.append_row([name])
    return True


def delete_user(name):
    try:
        cell = ws_users.find(name)
        ws_users.delete_rows(cell.row)
        return True
    except:
        return False


def add_gauge(gauge_id, category, spec):
    try:
        cell = ws_gauges.find(gauge_id)
        if cell: return False
    except:
        pass
    ws_gauges.append_row([gauge_id, category, spec, '可借出', '', ''])
    return True


def delete_gauge(gauge_id):
    try:
        cell = ws_gauges.find(gauge_id)
        ws_gauges.delete_rows(cell.row)
        return True
    except:
        return False


def update_status(gauge_id, action, user):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cell = ws_gauges.find(gauge_id)
        row_idx = cell.row
    except:
        return

    if action == 'borrow':
        # id(1), category(2), spec(3), status(4), current_user(5), borrow_time(6)
        ws_gauges.update_cell(row_idx, 4, '已借出')
        ws_gauges.update_cell(row_idx, 5, user)
        ws_gauges.update_cell(row_idx, 6, now_str)
    else:
        ws_gauges.update_cell(row_idx, 4, '可借出')
        ws_gauges.update_cell(row_idx, 5, '')
        ws_gauges.update_cell(row_idx, 6, '')

    ws_logs.append_row([gauge_id, '借出' if action == 'borrow' else '歸還', user, now_str])


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
    lang_opt = st.sidebar.radio("Language / 語言", ['中文', 'English'])
    st.session_state.lang = 'zh' if lang_opt == '中文' else 'en'
    t = TRANSLATIONS[st.session_state.lang]

    st.title(t['title'])
    role = st.sidebar.selectbox(t['role_select'], [t['role_user'], t['role_admin']])

    # --- 使用者介面 ---
    if role == t['role_user']:
        df_users = get_users()
        if df_users.empty:
            st.warning("No users found. / 尚無人員名單。")
        else:
            user_list = df_users['name'].astype(str).tolist()
            current_user_name = st.selectbox(t['login_first'], user_list)

            tab_borrow, tab_return, tab_status = st.tabs([t['tab_borrow'], t['tab_return'], t['tab_status']])
            df_gauges = get_gauges()

            with tab_borrow:
                if not df_gauges.empty:
                    categories = [t['all_categories']] + list(df_gauges['category'].unique())
                    selected_cat = st.selectbox(t['category_filter'], categories)
                    available = df_gauges[df_gauges['status'] == '可借出']
                    if selected_cat != t['all_categories']:
                        available = available[available['category'] == selected_cat]
                else:
                    available = pd.DataFrame()

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
                    st.warning(t['msg_no_data'])

            with tab_return:
                borrowed = df_gauges[df_gauges['status'] == '已借出']
                if not borrowed.empty:
                    for index, row in borrowed.iterrows():
                        days = calculate_days(row['borrow_time'])
                        is_owner = (str(row['current_user']) == str(current_user_name))
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            info_text = f"📍 {row['id']} | {row['category']} [{row['spec']}] - 👤 {row['current_user']} ({days} {t['days_unit']})"
                            if is_owner:
                                st.success(info_text)
                            else:
                                st.error(info_text)
                        with col2:
                            if is_owner:
                                if st.button(t['btn_return'], key=f"return_{row['id']}"):
                                    update_status(row['id'], 'return', current_user_name)
                                    st.rerun()
                            else:
                                st.button(t['btn_not_owner'], key=f"disabled_{row['id']}", disabled=True)
                else:
                    st.info(t['msg_no_data'])

            with tab_status:
                st.subheader(t['tab_status'])
                if not df_gauges.empty:
                    view_df = df_gauges[['id', 'category', 'spec', 'status', 'current_user', 'borrow_time']].copy()
                    view_df.columns = [t['col_id'], t['col_cat'], t['col_spec'], t['col_status'], t['col_user'],
                                       t['col_time']]
                    st.dataframe(view_df, use_container_width=True)
                else:
                    st.info(t['msg_no_data'])

    # --- 管理員介面 ---
    elif role == t['role_admin']:
        st.header("Backend")
        password = st.sidebar.text_input(t['password'], type="password")
        if password == "0000":
            tab1, tab2, tab3, tab4 = st.tabs(
                [t['admin_tab_status'], t['admin_tab_users'], t['admin_tab_gauges'], t['admin_tab_logs']])

            with tab1:
                df_gauges = get_gauges()
                borrowed = df_gauges[df_gauges['status'] == '已借出'].copy()
                if not borrowed.empty:
                    borrowed['Days'] = borrowed['borrow_time'].apply(calculate_days)
                    display_df = borrowed[['id', 'category', 'spec', 'current_user', 'Days']]
                    display_df.columns = [t['col_id'], t['col_cat'], t['col_spec'], t['col_user'], t['col_days']]
                    st.dataframe(display_df, use_container_width=True)
                else:
                    st.success(t['msg_no_data'])

            with tab2:
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    new_user = st.text_input(t['label_name'])
                    if st.button("Add / 新增"):
                        if new_user and add_user(new_user): st.success(t['msg_success_add']); st.rerun()
                with col_u2:
                    df_users = get_users()
                    if not df_users.empty:
                        del_user = st.selectbox("Delete / 刪除", df_users['name'].astype(str))
                        if st.button("Delete / 刪除"): delete_user(del_user); st.success(
                            t['msg_success_del']); st.rerun()

            with tab3:
                col_add, col_del = st.columns(2)
                with col_add:
                    st.markdown("#### Add New")
                    new_id = st.text_input(t['label_id'])
                    new_cat = st.text_input(t['label_cat'], placeholder="Micrometer")
                    new_spec = st.text_input(t['label_spec'], placeholder=t['ph_spec'])
                    if st.button("Add Gauge"):
                        if new_id and new_cat:
                            if add_gauge(new_id, new_cat, new_spec):
                                st.success(f"{t['msg_success_add']}: {new_id}"); st.rerun()
                            else:
                                st.error("Error / ID重複")
                        else:
                            st.error("Input missing")
                with col_del:
                    st.markdown("#### Delete")
                    df_all = get_gauges()
                    if not df_all.empty:
                        options = [f"{row['id']} ({row['spec']})" for i, row in df_all.iterrows()]
                        selection = st.selectbox("Select ID", options)
                        real_id = selection.split(" ")[0]
                        if st.button("Confirm Delete"): delete_gauge(real_id); st.success(
                            t['msg_success_del']); st.rerun()

            with tab4:
                st.dataframe(get_logs(), use_container_width=True)


if __name__ == "__main__":

    main()
