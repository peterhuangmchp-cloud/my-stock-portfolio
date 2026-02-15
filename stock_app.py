import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# --- 1. 網頁配置與門禁系統 ---
st.set_page_config(page_title="私人投資實驗室", layout="wide", page_icon="💰")

def check_password():
    """驗證密碼，成功則記錄在 session_state"""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔐 私人資產管理系統")
        st.info("此為受保護之實驗室，請輸入存取密碼以解鎖數據。")
        
        pwd_input = st.text_input("請輸入密碼", type="password")
        if st.button("確認解鎖"):
            if pwd_input == st.secrets["APP_PASSWORD"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤，拒絕存取。")
        st.stop() 

# 執行驗證
check_password()

# --- 2. 核心功能：讀取資料與顯示儀表板 ---
st.title("📊 全球資產損益與現金流儀表板")

# 從 Secrets 讀取試算表 ID
gsheet_id = st.secrets["GSHEET_ID"]
# 存入 session_state 供分頁使用
st.session_state['gsheet_id'] = gsheet_id

@st.cache_data(ttl=3600)
def load_data(gid):
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    return pd.read_csv(url)

try:
    # 讀取資產明細 (假設 gid=0)
    df = load_data(0)
    
    # --- 數據清理與計算 ---
    # 確保庫存量與成本為數值
    df['庫存量'] = pd.to_numeric(df['庫存量'], errors='coerce')
    df['平均成本'] = pd.to_numeric(df['平均成本'], errors='coerce')
    
    # 抓取即時股價 (使用 yfinance)
    tickers = df['代號'].unique()
    with st.spinner('正在獲取即時報價...'):
        data = yf.download(list(tickers), period="1d")['Close']
        if isinstance(data, pd.Series): # 處理單一股票情況
            current_prices = {tickers[0]: data.iloc[-1]}
        else:
            current_prices = data.iloc[-1].to_dict()

    df['現價'] = df['代號'].map(current_prices)
    df['現值'] = df['現價'] * df['庫存量']
    df['總成本'] = df['平均成本'] * df['庫存量']
    df['損益'] = df['現值'] - df['總成本']
    df['報酬率'] = (df['損益'] / df['總成本']) * 100

    # --- 儀表板上方總結欄 (KPI) ---
    total_value = df['現值'].sum()
    total_profit = df['損益'].sum()
    avg_return = (total_profit / df['總成本'].sum()) * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("總資產現值", f"${total_value:,.0f}")
    col2.metric("累計未實現損益", f"${total_profit:,.0f}", f"{avg_return:.2f}%")
    col3.metric("持有股數", f"{len(df)} 標的")

    # --- 圖表展示 ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("💰 資產配置比例")
        fig_pie = px.pie(df, values='現值', names='名稱', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("📈 個股損益狀況")
        fig_bar = px.bar(df, x='名稱', y='損益', color='損益', 
                         color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- 詳細表格 ---
    st.subheader("📋 資產明細表")
    st.dataframe(df[['名稱', '代號', '庫存量', '平均成本', '現價', '現值', '損益', '報酬率']].style.format({
        '現值': '{:,.0f}', '損益': '{:,.0f}', '報酬率': '{:.2f}%', '現價': '{:.2f}'
    }), use_container_width=True)

except Exception as e:
    st.error(f"數據讀取失敗，請檢查 Google Sheet ID 或資料格式。錯誤訊息: {e}")
