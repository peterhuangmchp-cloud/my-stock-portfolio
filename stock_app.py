import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 網頁基本設定
st.set_page_config(page_title="全球資產損益與趨勢分析", layout="wide", page_icon="📈")
st.title("📊 全球資產即時儀表板")

# 2. 讀取 Google Sheets 函數
def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    return data

# 3. 側邊欄設定
st.sidebar.header("⚙️ 系統設定")
gsheet_id = st.sidebar.text_input("Google Sheet ID", "15NuQ4YTC08NsC1cVtpJbLCgUHI2WrhGwyFpXFzcHOR4")

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("TWD=X").fast_info['last_price']
        return rate
    except:
        return 32.2 # 備用匯率

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

if not gsheet_id:
    st.info("請在側邊欄輸入您的 Google Sheet ID 開始使用。")
    st.stop()

# 4. 核心運算邏輯
try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在同步全球報價與計算數據...'):
        price_map = {}
        ma200_map = {}
        
        for sym in unique_symbols:
            ticker = yf.Ticker(sym)
            price_map[sym] = ticker.fast_info['last_price']
            # 抓取歷史計算 200MA
            hist = ticker.history(period="1y")
            ma200_map[sym] = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
        
        df['current_price'] = df['symbol'].map(price_map)
        df['ma200'] = df['symbol'].map(ma200_map)

    # 計算損益
    def calculate_metrics(row):
        mv_orig = row['current_price'] * row['shares']
        cost_total_orig = row['cost'] * row['shares']
        
        if row['currency'] == "USD":
            mv_twd = mv_orig * usd_to_twd
            cost_twd = cost_total_orig * usd_to_twd
        else:
            mv_twd = mv_orig
            cost_twd = cost_total_orig
            
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd != 0 else 0
        return pd.Series([mv_twd, profit_twd, roi])

    df[['mv_twd', 'profit_twd', 'roi']] = df.apply(calculate_metrics, axis=1)

    # --- 第一部分：資產總覽 (保留所有資訊) ---
    total_val = df['mv_twd'].sum()
    total_profit = df['profit_twd'].sum()
    total_roi = (total_profit / (total_val - total_profit)) * 100

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("總資產市值 (TWD)", f"${total_val:,.0f}")
    col_m2.metric("總累計損益 (TWD)", f"${total_profit:,.0f}", f"{total_roi:.2f}%")
    col_m3.metric("美金資產佔比", f"{(df[df['currency']=='USD']['mv_twd'].sum()/total_val*100):.1f}%")

    st.markdown("---")
    
    # 圖表區
    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with row1_c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    # 詳細清單
    st.subheader("📝 完整持倉清單")
    st.dataframe(df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }), use_container_width=True)

    # --- 第二部分：股票專屬趨勢分析 (排除債券) ---
    st.markdown("---")
    st.subheader("🔍 股票長期趨勢分析 (200MA)")
    
    bond_symbols = ['TLT', 'SHV', 'SGOV', 'LQD']
    stock_df = df[~df['symbol'].isin(bond_symbols)].copy()
    
    if not stock_df.empty:
        selected_stock = st.selectbox("選擇要查看趨勢圖的股票：", stock_df['symbol'].unique())
        
        with st.spinner('載入歷史走勢中...'):
            tk = yf.Ticker(selected_stock)
            h_data = tk.history(period="2y")
            h_data['MA200'] = h_data['Close'].rolling(window=200).mean()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], name='收盤價', line=dict(color='#1f77b4')))
            fig.add_trace(go.Scatter(x=h_data.index, y=h_data['MA200'], name='200MA', line=dict(color='#ff7f0e', dash='dash')))
            
            fig.update_layout(title=f"{selected_stock} 歷史走勢與長期均線", hovermode="x unified", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            # 乖離率計算
            cur_p = h_data['Close'].iloc[-1]
            ma_p = h_data['MA200'].iloc[-1]
            bias = ((cur_p - ma_p) / ma_p * 100) if ma_p else 0
            st.info(f"**{selected_stock}** 目前股價相對於 200MA 的乖離率為：**{bias:.2f}%** ({'多頭排列' if bias > 0 else '空頭排列'})")
    else:
        st.write("目前清單中沒有股票類標的。")

except Exception as e:
    st.error(f"執行出錯：{e}")
