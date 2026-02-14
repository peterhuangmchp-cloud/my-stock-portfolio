import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# 設定網頁標題與圖示
st.set_page_config(page_title="我的個人投資組合", layout="wide", page_icon="📈")
st.title("📊 全球資產即時損益儀表板")

# --- 1. 讀取 Google Sheets 函數 ---
def load_data(sheet_id):
    # 強制轉換為 CSV 下載連結
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    data = pd.read_csv(url)
    # 清理欄位名稱多餘空白
    data.columns = data.columns.str.strip()
    return data

# --- 2. 側邊欄設定 ---
st.sidebar.header("⚙️ 系統設定")
# 你可以直接把你的 ID 填入第二個參數，以後打開網頁就不用再貼一次
gsheet_id = st.sidebar.text_input("Google Sheet ID", "15NuQ4YTC08NsC1cVtpJbLCgUHI2WrhGwyFpXFzcHOR4")

# 獲取即時匯率
@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        # 抓取美金對台幣匯率
        rate = yf.Ticker("TWD=X").fast_info['last_price']
        return rate
    except:
        return 32.0 # 備用匯率

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

if not gsheet_id:
    st.info("請在側邊欄輸入您的 Google Sheet ID 開始使用。")
    st.stop()

# --- 3. 核心運算邏輯 ---
try:
    df = load_data(gsheet_id)
    
    # 獲取唯一標記清單以節省 API 呼叫次數
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在同步 Yahoo Finance 全球即時報價...'):
        price_map = {}
        for sym in unique_symbols:
            try:
                price_map[sym] = yf.Ticker(sym).fast_info['last_price']
            except:
                price_map[sym] = 0
        
        df['current_price'] = df['symbol'].map(price_map)

    # 計算各項數值
    def calculate_metrics(row):
        # 原始幣別市值
        market_value_orig = row['current_price'] * row['shares']
        # 成本
        cost_total_orig = row['cost'] * row['shares']
        
        # 統一轉換為台幣
        if row['currency'] == "USD":
            mv_twd = market_value_orig * usd_to_twd
            cost_twd = cost_total_orig * usd_to_twd
        else:
            mv_twd = market_value_orig
            cost_twd = cost_total_orig
            
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd != 0 else 0
        return pd.Series([mv_twd, profit_twd, roi])

    df[['mv_twd', 'profit_twd', 'roi']] = df.apply(calculate_metrics, axis=1)

    # --- 4. 儀表板顯示 ---
    total_val = df['mv_twd'].sum()
    total_profit = df['profit_twd'].sum()
    total_roi = (total_profit / (total_val - total_profit)) * 100

    # 頂部指標
    c1, c2, c3 = st.columns(3)
    c1.metric("總資產市值 (TWD)", f"${total_val:,.0f}")
    c2.metric("總累計損益 (TWD)", f"${total_profit:,.0f}", f"{total_roi:.2f}%")
    c3.metric("美金資產佔比", f"{(df[df['currency']=='USD']['mv_twd'].sum()/total_val*100):.1f}%")

    # 圖表區
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📌 資產配置比例")
        fig_pie = px.pie(df, values='mv_twd', names='name', hole=0.3)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_right:
        st.subheader("📈 個股損益排行 (TWD)")
        # 按損益排序顯示
        df_sorted = df.sort_values('profit_twd', ascending=True)
        fig_bar = px.bar(df_sorted, x='profit_twd', y='name', orientation='h',
                         color='profit_twd', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_bar, use_container_width=True)

    # 詳細表格
    st.subheader("📝 持倉明細清單")
    st.dataframe(df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']].style.format({
        'cost': '{:.2f}',
        'current_price': '{:.2f}',
        'profit_twd': '{:,.0f}',
        'roi': '{:.2f}%'
    }), use_container_width=True)

except Exception as e:
    st.error(f"發生錯誤：{e}")