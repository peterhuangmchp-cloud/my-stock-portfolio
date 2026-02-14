import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 網頁基本設定
st.set_page_config(page_title="全球資產損益、趨勢與配息分析", layout="wide", page_icon="💰")
st.title("📊 全球資產即時儀表板 (含年度配息統計)")

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
        return 32.2 

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

if not gsheet_id:
    st.info("請在側邊欄輸入您的 Google Sheet ID 開始使用。")
    st.stop()

# 4. 核心運算邏輯
try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在同步全球報價、200MA 及配息數據...'):
        price_map = {}
        ma200_map = {}
        div_map = {} # 儲存過去一年總配息
        
        for sym in unique_symbols:
            ticker = yf.Ticker(sym)
            # 即時價
            price_map[sym] = ticker.fast_info['last_price']
            
            # 歷史數據 (計算 200MA)
            hist = ticker.history(period="1y")
            ma200_map[sym] = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            
            # 配息數據 (過去一年)
            # yfinance 的 dividends 返回所有歷史配息，我們篩選過去 365 天
            divs = ticker.dividends
            last_year_divs = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum()
            div_map[sym] = last_year_divs
        
        df['current_price'] = df['symbol'].map(price_map)
        df['ma200'] = df['symbol'].map(ma200_map)
        df['annual_div_per_share'] = df['symbol'].map(div_map)

    # 計算損益與配息
    def calculate_metrics(row):
        mv_orig = row['current_price'] * row['shares']
        cost_total_orig = row['cost'] * row['shares']
        # 年度總配息 (原始幣別)
        total_div_orig = row['annual_div_per_share'] * row['shares']
        
        if row['currency'] == "USD":
            mv_twd = mv_orig * usd_to_twd
            cost_twd = cost_total_orig * usd_to_twd
            div_twd = total_div_orig * usd_to_twd
        else:
            mv_twd = mv_orig
            cost_twd = cost_total_orig
            div_twd = total_div_orig
            
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd != 0 else 0
        # 殖利率 (以目前市價計算)
        yield_rate = (row['annual_div_per_share'] / row['current_price'] * 100) if row['current_price'] > 0 else 0
        
        return pd.Series([mv_twd, profit_twd, roi, div_twd, yield_rate])

    df[['mv_twd', 'profit_twd', 'roi', 'annual_div_twd', 'yield_rate']] = df.apply(calculate_metrics, axis=1)

    # --- 第一部分：資產總覽 ---
    total_val = df['mv_twd'].sum()
    total_profit = df['profit_twd'].sum()
    total_ann_div = df['annual_div_twd'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總資產市值 (TWD)", f"${total_val:,.0f}")
    m2.metric("總累計損益 (TWD)", f"${total_profit:,.0f}")
    m3.metric("預估年配息 (TWD)", f"${total_ann_div:,.0f}")
    m4.metric("平均年化殖利率", f"{(total_ann_div / total_val * 100):.2f}%")

    st.markdown("---")
    
    # 圖表區 (原有資訊)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    # --- 第二部分：新增的配息統計表 ---
    st.subheader("📅 年度配息與殖利率統計 (NT$)")
    div_display = df[['name', 'symbol', 'shares', 'annual_div_per_share', 'annual_div_twd', 'yield_rate']].copy()
    st.dataframe(div_display.sort_values('annual_div_twd', ascending=False).style.format({
        'annual_div_per_share': '{:.4f}',
        'annual_div_twd': '{:,.0f}',
        'yield_rate': '{:.2f}%'
    }), use_container_width=True)

    # --- 第三部分：完整持倉與趨勢分析 (保留) ---
    st.markdown("---")
    st.subheader("📝 完整持倉清單")
    st.dataframe(df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }), use_container_width=True)

    st.markdown("---")
    st.subheader("🔍 股票長期趨勢分析 (200MA)")
    bond_symbols = ['TLT', 'SHV', 'SGOV', 'LQD']
    stock_df = df[~df['symbol'].isin(bond_symbols)].copy()
    
    if not stock_df.empty:
        selected_stock = st.selectbox("選擇要查看趨勢圖的股票：", stock_df['symbol'].unique())
        tk = yf.Ticker(selected_stock)
        h_data = tk.history(period="2y")
        h_data['MA200'] = h_data['Close'].rolling(window=200).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], name='收盤價'))
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['MA200'], name='200MA', line=dict(dash='dash')))
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"執行出錯：{e}")
