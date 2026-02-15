import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# --- 1. 網頁配置與門禁系統 ---
st.set_page_config(page_title="私人投資實驗室", layout="wide", page_icon="💰")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔐 私人資產管理系統")
        st.info("此為受保護之實驗室，請輸入存取密碼以解鎖數據。")
        
        pwd_input = st.text_input("請輸入密碼", type="password")
        if st.button("確認解鎖"):
            # 請確保在 Streamlit Cloud Secrets 中設定了 APP_PASSWORD
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
st.session_state['gsheet_id'] = gsheet_id

@st.cache_data(ttl=600)
def load_data(gid):
    # 使用 export?format=csv 確保讀取穩定
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={gid}"
    data = pd.read_csv(url)
    # 自動修復標頭可能存在的空白字元，解決 '庫存量' 報錯問題
    data.columns = data.columns.str.strip()
    return data

try:
    # 讀取資產明細
    df = load_data(0)
    
    # 檢查必要欄位
    required_cols = ['名稱', '代號', '庫存量', '平均成本']
    if not all(col in df.columns for col in required_cols):
        st.error(f"試算表格式錯誤！請確認包含以下欄位：{required_cols}")
        st.info(f"目前偵測到的欄位為：{list(df.columns)}")
        st.stop()

    # 數據清理：確保數值格式
    df['庫存量'] = pd.to_numeric(df['庫存量'], errors='coerce').fillna(0)
    df['平均成本'] = pd.to_numeric(df['平均成本'], errors='coerce').fillna(0)
    
    # 獲取即時股價
    tickers = [t for t in df['代號'].unique() if isinstance(t, str)]
    with st.spinner('正在獲取最新市場報價...'):
        price_data = yf.download(tickers, period="1d")['Close']
        if isinstance(price_data, pd.Series):
            current_prices = {tickers[0]: price_data.iloc[-1]}
        else:
            current_prices = price_data.iloc[-1].to_dict()

    # 計算損益
    df['現價'] = df['代號'].map(current_prices)
    df['現值'] = df['現價'] * df['庫存量']
    df['總成本'] = df['平均成本'] * df['庫存量']
    df['損益'] = df['現值'] - df['總成本']
    df['報酬率'] = (df['損益'] / df['總成本']) * 100

    # KPI 指標欄
    total_value = df['現值'].sum()
    total_profit = df['損益'].sum()
    total_cost = df['總成本'].sum()
    avg_return = (total_profit / total_cost * 100) if total_cost != 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("總資產現值", f"${total_value:,.0f}")
    col2.metric("累計損益", f"${total_profit:,.0f}", f"{avg_return:.2f}%")
    col3.metric("持有標的", f"{len(df)} 檔")

    st.markdown("---")

    # 圖表呈現
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 資產配置")
        fig_pie = px.pie(df, values='現值', names='名稱', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
    with c2:
        st.subheader("📈 個股損益 (TWD)")
        fig_bar = px.bar(df, x='名稱', y='損益', color='損益', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_bar, use_container_width=True)

    # 詳細表格
    st.subheader("📋 持股明細")
    st.dataframe(df[['名稱', '代號', '庫存量', '平均成本', '現價', '現值', '損益', '報酬率']].style.format({
        '現值': '{:,.0f}', '損益': '{:,.0f}', '報酬率': '{:.2f}%', '現價': '{:.2f}', '平均成本': '{:.2f}'
    }), use_container_width=True)

except Exception as e:
    st.error(f"發生未預期錯誤：{e}")
