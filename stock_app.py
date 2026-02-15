import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests

# --- 1. 網頁配置與密碼鎖 ---
st.set_page_config(page_title="私人投資實驗室", layout="wide", page_icon="💰")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if not st.session_state["authenticated"]:
        st.title("🔐 私人資產管理系統")
        pwd_input = st.text_input("請輸入實驗室密碼", type="password")
        if st.button("確認解鎖"):
            if pwd_input == st.secrets.get("APP_PASSWORD"):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤")
        st.stop() 

check_password()

# --- 2. 核心功能：讀取您的 Google 試算表 ---
st.title("📊 全球資產損益儀表板")

gsheet_id = st.secrets["GSHEET_ID"]
st.session_state['gsheet_id'] = gsheet_id

@st.cache_data(ttl=600)
def load_data_robust(gid):
    # 根據您的截圖，gid 應該是 1797698775
    csv_url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={gid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(csv_url, headers=headers)
    if response.status_code == 200:
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = df.columns.str.strip().str.lower() # 統一轉小寫並去空格
        return df
    else:
        st.error(f"無法讀取資料。代碼：{response.status_code}")
        return None

# 讀取資料（自動使用您截圖中的 gid）
df_raw = load_data_robust(1797698775)

if df_raw is not None:
    try:
        # 對接您的英文欄位：name, symbol, shares, cost
        df = df_raw.copy()
        
        # 數據清洗
        df['shares'] = pd.to_numeric(df['shares'], errors='coerce').fillna(0)
        df['cost'] = pd.to_numeric(df['cost'], errors='coerce').fillna(0)
        
        # 獲取股價
        tickers = df['symbol'].unique().tolist()
        with st.spinner('同步市場報價中...'):
            price_data = yf.download(tickers, period="1d", progress=False)['Close']
            if len(tickers) == 1:
                current_prices = {tickers[0]: price_data.iloc[-1]}
            else:
                current_prices = price_data.iloc[-1].to_dict()

        # 計算損益
        df['現價'] = df['symbol'].map(current_prices)
        df['現值'] = df['現價'] * df['shares']
        df['總成本'] = df['cost'] * df['shares']
        df['損益'] = df['現值'] - df['總成本']
        df['報酬率'] = (df['損益'] / df['總成本']) * 100

        # KPI 展示
        c1, c2, c3 = st.columns(3)
        c1.metric("總資產現值 (USD)", f"${df['現值'].sum():,.0f}")
        c2.metric("累計損益", f"${df['損益'].sum():,.0f}")
        c3.metric("標的總數", f"{len(df)} 檔")

        # 圖表
        st.markdown("---")
        col_left, col_right = st.columns(2)
        with col_left:
            st.plotly_chart(px.pie(df, values='現值', names='name', hole=0.4, title="資產權重"), use_container_width=True)
        with col_right:
            st.plotly_chart(px.bar(df, x='name', y='損益', color='損益', color_continuous_scale='RdYlGn', title="各標的盈虧"), use_container_width=True)

        # 表格顯示（轉換回中文標題方便閱讀）
        st.subheader("📋 詳細持股清單")
        display_df = df[['name', 'symbol', 'shares', 'cost', '現價', '現值', '損益', '報酬率']]
        display_df.columns = ['名稱', '代號', '股數', '成本', '現價', '現值', '損益', '報酬率']
        st.dataframe(display_df.style.format({
            '現值': '{:,.0f}', '損益': '{:,.0f}', '報酬率': '{:.2f}%', '現價': '{:.2f}', '成本': '{:.2f}'
        }), use_container_width=True)

    except Exception as e:
        st.error(f"運算錯誤: {e}")
