import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 網頁基本設定
st.set_page_config(page_title="全球資產損益與安全監控看板", layout="wide", page_icon="🛡️")
st.title("🛡️ 全球資產損益與全功能技術分析 (安全加密版)")

# --- [關鍵修改：安全讀取 Secrets] ---
if "GSHEET_ID" in st.secrets:
    gsheet_id = st.secrets["GSHEET_ID"]
else:
    # 如果 Secrets 沒設定，才顯示輸入框作為備援
    gsheet_id = st.sidebar.text_input("請輸入 Google Sheet ID")

if not gsheet_id:
    st.info("請於 Streamlit Secrets 設定 GSHEET_ID 或在側邊欄輸入。")
    st.stop()
# ----------------------------------

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
        return 32.5

# 3. 數據處理
usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('正在從安全來源同步數據...'):
        price_map, ma50_map, ma200_map, div_map = {}, {}, {}, {}
        for sym in unique_symbols:
            tk = yf.Ticker(sym)
            price_map[sym] = tk.fast_info['last_price']
            hist = tk.history(period="2y")
            ma50_map[sym] = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            ma200_map[sym] = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            divs = tk.dividends
            if not divs.empty:
                last_year = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))]
                div_map[sym] = last_year.sum()
            else:
                div_map[sym] = 0.0

    # 4. 損益與配息邏輯
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        curr_p = price_map.get(row['symbol'], 0)
        mv_twd = curr_p * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        cost_twd = row['cost'] * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        div_raw = div_map.get(row['symbol'], 0) * row['shares']
        if row['currency'] == "USD":
            tax = 0.7 if row['symbol'] not in bond_list else 1.0
            net_div = div_raw * tax * usd_to_twd
        else:
            net_div = div_raw
        y_rate = (div_map.get(row['symbol'], 0) / curr_p * 100) if curr_p > 0 else 0
        return pd.Series([curr_p, mv_twd, profit_twd, roi, net_div, y_rate])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'yield_rate']] = df.apply(process_row, axis=1)

    # --- 顯示區塊 ---
    # A. 摘要
    m1, m2, m3 = st.columns(3)
    m1.metric("總市值 (TWD)", f"${df['mv_twd'].sum():,.0f}")
    m2.metric("總累計損益", f"${df['profit_twd'].sum():,.0f}")
    m3.metric("年度稅後股息", f"${df['net_div_twd'].sum():,.0f}")

    # B. 配息表
    st.markdown("---")
    st.subheader("💰 年度配息統計")
    st.dataframe(df[df['net_div_twd']>0][['name','symbol','yield_rate','net_div_twd']].style.format({'yield_rate':'{:.2f}%','net_div_twd':'{:,.0f}'}), use_container_width=True)

    # C. 持倉明細
    st.markdown("---")
    st.subheader("📝 持倉明細")
    st.dataframe(df[['name','symbol','shares','cost','current_price','profit_twd','roi']].style.format({'current_price':'{:.2f}','profit_twd':'{:,.0f}','roi':'{:.2f}%'}), use_container_width=True)

    # D. 技術分析 (包含 RSI, Volume)
    st.markdown("---")
    st.subheader("🔍 進階技術分析")
    stock_opt = df[~df['symbol'].isin(bond_list)]['symbol'].unique()
    if len(stock_opt) > 0:
        sel = st.selectbox("選擇分析標的：", stock_opt)
        h_data = yf.Ticker(sel).history(period="1y")
        # RSI 計算
        diff = h_data['Close'].diff()
        gain = (diff.where(diff > 0, 0)).rolling(14).mean()
        loss = (-diff.where(diff < 0, 0)).rolling(14).mean()
        h_data['RSI'] = 100 - (100 / (1 + gain/loss))
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], name='收盤價'), row=1, col=1)
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['RSI'], name='RSI'), row=2, col=1)
        fig.add_trace(go.Bar(x=h_data.index, y=h_data['Volume'], name='交易量'), row=3, col=1)
        fig.update_layout(height=800, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"執行錯誤: {e}")
