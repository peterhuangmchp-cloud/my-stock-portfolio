import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 網頁基本設定
st.set_page_config(page_title="全球資產與配息分析", layout="wide", page_icon="💰")
st.title("📊 全球資產損益與現金流儀表板")

# 2. 函數定義
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
        return 32.2

# 3. 數據抓取與計算
gsheet_id = st.sidebar.text_input("Google Sheet ID", "15NuQ4YTC08NsC1cVtpJbLCgUHI2WrhGwyFpXFzcHOR4")
usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

if not gsheet_id:
    st.info("請在側邊欄輸入 Google Sheet ID。")
    st.stop()

try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在同步全球數據與配息資訊...'):
        price_map = {}
        ma200_map = {}
        dividend_map = {} # 記錄過去一年每股配息總額
        
        for sym in unique_symbols:
            tk = yf.Ticker(sym)
            # 價格與 200MA
            price_map[sym] = tk.fast_info['last_price']
            hist = tk.history(period="1y")
            ma200_map[sym] = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            
            # 配息抓取 (過去一年)
            divs = tk.dividends
            if not divs.empty:
                # 篩選過去 365 天的配息
                last_year_divs = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))]
                dividend_map[sym] = last_year_divs.sum()
            else:
                dividend_map[sym] = 0.0

        df['current_price'] = df['symbol'].map(price_map)
        df['ma200'] = df['symbol'].map(ma200_map)
        df['div_per_share'] = df['symbol'].map(dividend_map)

    # 4. 核心邏輯：計算損益與配息
    bond_etfs = ['TLT', 'SHV', 'SGOV', 'LQD'] # 定義債券ETF清單

    def calculate_all(row):
        mv_twd = row['current_price'] * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        cost_twd = row['cost'] * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        profit_twd = mv_twd - cost_twd
        
        # 配息計算邏輯
        raw_div_total = row['div_per_share'] * row['shares']
        
        if row['currency'] == "USD":
            # 如果是美股且不在債券清單內，扣除 30% 稅
            if row['symbol'] not in bond_etfs:
                net_div_orig = raw_div_total * 0.7
            else:
                net_div_orig = raw_div_total
            net_div_twd = net_div_orig * usd_to_twd
        else:
            net_div_twd = raw_div_total # 台股暫不在此扣稅，可視需要調整
            
        yield_rate = (row['div_per_share'] / row['current_price'] * 100) if row['current_price'] > 0 else 0
        
        return pd.Series([mv_twd, profit_twd, net_div_twd, yield_rate])

    df[['mv_twd', 'profit_twd', 'net_div_twd', 'yield_rate']] = df.apply(calculate_all, axis=1)

    # --- 顯示區塊 ---
    # A. 頂部摘要
    t_val = df['mv_twd'].sum()
    t_pnl = df['profit_twd'].sum()
    t_div = df['net_div_twd'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("總市值 (TWD)", f"${t_val:,.0f}")
    c2.metric("總累計損益 (TWD)", f"${t_pnl:,.0f}")
    c3.metric("年度預估配息總額 (NTD)", f"${t_div:,.0f}", help="已扣除美股30%預扣稅 (債券除外)")

    # B. 配息統計表 (新功能)
    st.markdown("---")
    st.subheader("💰 年度配息統計表 (預估)")
    div_display = df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'yield_rate', 'net_div_twd']].copy()
    st.table(div_display.sort_values('net_div_twd', ascending=False).style.format({
        'yield_rate': '{:.2f}%',
        'net_div_twd': '{:,.0f}'
    }))

    # C. 原有圖表與持倉清單
    st.markdown("---")
    r1_1, r1_2 = st.columns(2)
    with r1_1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with r1_2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    # D. 200MA 趨勢分析
    st.markdown("---")
    st.subheader("🔍 股票趨勢分析 (200MA)")
    stock_list = df[~df['symbol'].isin(bond_etfs)]['symbol'].unique()
    sel_stock = st.selectbox("分析股票：", stock_list)
    if sel_stock:
        tk_h = yf.Ticker(sel_stock).history(period="2y")
        tk_h['200MA'] = tk_h['Close'].rolling(window=200).mean()
        fig = go.Figure([go.Scatter(x=tk_h.index, y=tk_h['Close'], name='價'), go.Scatter(x=tk_h.index, y=tk_h['MA200'], name='200MA', line=dict(dash='dash'))])
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"錯誤: {e}")
