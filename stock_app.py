import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# 設定網頁標題
st.set_page_config(page_title="我的個人投資組合 (含200MA)", layout="wide", page_icon="📈")
st.title("📊 全球資產即時損益儀表板 (含長期趨勢分析)")

# --- 1. 讀取 Google Sheets 函數 ---
def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    return data

# --- 2. 側邊欄設定 ---
st.sidebar.header("⚙️ 系統設定")
gsheet_id = st.sidebar.text_input("Google Sheet ID", "15NuQ4YTC08NsC1cVtpJbLCgUHI2WrhGwyFpXFzcHOR4")

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("TWD=X").fast_info['last_price']
        return rate
    except:
        return 32.0

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

if not gsheet_id:
    st.info("請在側邊欄輸入您的 Google Sheet ID 開始使用。")
    st.stop()

# --- 3. 核心運算與 200MA 抓取 ---
try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在同步全球報價與計算 200MA...'):
        price_map = {}
        ma200_map = {}
        
        for sym in unique_symbols:
            try:
                ticker = yf.Ticker(sym)
                # 抓取即時價
                price_map[sym] = ticker.fast_info['last_price']
                
                # 抓取過去一年的歷史資料來計算 200MA
                hist = ticker.history(period="1y")
                if len(hist) >= 200:
                    ma200_map[sym] = hist['Close'].rolling(window=200).mean().iloc[-1]
                else:
                    ma200_map[sym] = None # 資料不足 200 天
            except:
                price_map[sym] = 0
                ma200_map[sym] = None
        
        df['current_price'] = df['symbol'].map(price_map)
        df['ma200'] = df['symbol'].map(ma200_map)

    # 計算損益與趨勢判斷
    def calculate_metrics(row):
        mv_orig = row['current_price'] * row['shares']
        cost_orig = row['cost'] * row['shares']
        
        if row['currency'] == "USD":
            mv_twd = mv_orig * usd_to_twd
            cost_twd = cost_orig * usd_to_twd
        else:
            mv_twd = mv_orig
            cost_twd = cost_orig
            
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd != 0 else 0
        
        # 判斷股價相對於 200MA 的位置
        if row['ma200'] and row['current_price'] > row['ma200']:
            trend = "☀️ 多頭 (高於200MA)"
        elif row['ma200'] and row['current_price'] < row['ma200']:
            trend = "🌧 偏空 (低於200MA)"
        else:
            trend = "❓ 資料不足"
            
        return pd.Series([mv_twd, profit_twd, roi, trend])

    df[['mv_twd', 'profit_twd', 'roi', 'trend']] = df.apply(calculate_metrics, axis=1)

    # --- 4. 顯示儀表板 ---
    total_val = df['mv_twd'].sum()
    total_profit = df['profit_twd'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("總資產市值 (TWD)", f"${total_val:,.0f}")
    c2.metric("總累計損益 (TWD)", f"${total_profit:,.0f}")
    c3.metric("美金匯率", f"{usd_to_twd:.2f}")

    # 詳細表格 (包含 200MA 與 趨勢)
    st.subheader("📝 完整持倉與長期趨勢 (200MA) 分析")
    
    # 格式化顯示
    st.dataframe(df[['name', 'symbol', 'current_price', 'ma200', 'trend', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}',
        'ma200': '{:.2f}',
        'profit_twd': '{:,.0f}',
        'roi': '{:.2f}%'
    }), use_container_width=True)

    # 圖表
    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with col_right:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

except Exception as e:
    st.error(f"發生錯誤：{e}")
