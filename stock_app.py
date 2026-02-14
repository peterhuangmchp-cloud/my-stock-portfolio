import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 網頁基本設定
st.set_page_config(page_title="全球資產損益與現金流儀表板", layout="wide", page_icon="💰")
st.title("📊 全球資產損益與現金流儀表板")

# 2. 核心函數
def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    return data

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("TWD=X").fast_info['last_price']
        return rate
    except:
        return 32.2 # 備用匯率

# 3. 數據抓取
gsheet_id = st.sidebar.text_input("Google Sheet ID", "15NuQ4YTC08NsC1cVtpJbLCgUHI2WrhGwyFpXFzcHOR4")
usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

if not gsheet_id:
    st.info("請在側邊欄輸入您的 Google Sheet ID。")
    st.stop()

try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在同步全球報價、配息與均線數據...'):
        price_map = {}
        ma200_map = {}
        div_map = {} 
        
        for sym in unique_symbols:
            tk = yf.Ticker(sym)
            price_map[sym] = tk.fast_info['last_price']
            hist = tk.history(period="1y")
            ma200_map[sym] = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            divs = tk.dividends
            if not divs.empty:
                last_year = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))]
                div_map[sym] = last_year.sum()
            else:
                div_map[sym] = 0.0

    # 4. 邏輯運算 (含稅務處理)
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']

    def process_row(row):
        curr_price = price_map.get(row['symbol'], 0)
        mv_twd = curr_price * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        cost_twd = row['cost'] * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        div_per_share = div_map.get(row['symbol'], 0)
        total_div_raw = div_per_share * row['shares']
        
        if row['currency'] == "USD":
            tax_rate = 0.7 if row['symbol'] not in bond_list else 1.0
            net_div_twd = total_div_raw * tax_rate * usd_to_twd
        else:
            net_div_twd = total_div_raw
            
        yield_rate = (div_per_share / curr_price * 100) if curr_price > 0 else 0
        return pd.Series([curr_price, mv_twd, profit_twd, roi, net_div_twd, yield_rate])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'yield_rate']] = df.apply(process_row, axis=1)

    # --- A. 頂部摘要區 ---
    t_val = df['mv_twd'].sum()
    t_profit = df['profit_twd'].sum()
    t_div = df['net_div_twd'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("總資產市值 (TWD)", f"${t_val:,.0f}")
    m2.metric("總累計損益 (TWD)", f"${t_profit:,.0f}", f"{(t_profit/t_val*100):.2f}%")
    m3.metric("年度預估稅後配息 (TWD)", f"${t_div:,.0f}")

    # --- B. 配息統計表 (可排序 & 匯出) ---
    st.markdown("---")
    st.subheader("💰 年度個股配息與殖利率統計 (NTD)")
    div_df = df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'yield_rate', 'net_div_twd']].copy()
    
    if not div_df.empty:
        # 顯示可排序表格
        st.dataframe(div_df.sort_values('net_div_twd', ascending=False).style.format({
            'yield_rate': '{:.2f}%', 'net_div_twd': '{:,.0f}'
        }), use_container_width=True)
        # 匯出按鈕
        st.download_button("📥 匯出配息統計表", div_df.to_csv(index=False).encode('utf-8-sig'), "dividend_report.csv", "text/csv")
    else:
        st.info("目前持倉中尚未有配息記錄的標的。")

    # --- C. 持倉明細與圖表 (原有資訊) ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    st.subheader("📝 完整持倉清單 (可點擊標題排序)")
    detail_df = df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']]
    st.dataframe(detail_df.style.format({
        'current_price': '{:.2f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }), use_container_width=True)
    st.download_button("📥 匯出完整持倉明細", detail_df.to_csv(index=False).encode('utf-8-sig'), "portfolio_detail.csv", "text/csv")

    # --- D. 股票趨勢分析 (200MA) ---
    st.markdown("---")
    st.subheader("🔍 股票長期趨勢分析 (200MA)")
    stock_options = df[~df['symbol'].isin(bond_list)]['symbol'].unique()
    if len(stock_options) > 0:
        sel_stock = st.selectbox("請選擇要分析的股票：", stock_options)
        with st.spinner('載入走勢圖中...'):
            tk_obj = yf.Ticker(sel_stock)
            h_data = tk_obj.history(period="2y")
            h_data['ma200_line'] = h_data['Close'].rolling(window=200).mean()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], name='收盤價'))
            fig.add_trace(go.Scatter(x=h_data.index, y=h_data['ma200_line'], name='200MA', line=dict(dash='dash')))
            fig.update_layout(hovermode="x unified", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"系統執行錯誤: {e}")
