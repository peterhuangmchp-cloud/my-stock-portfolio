import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 網頁基本設定
st.set_page_config(page_title="全球資產損益、配息與全功能分析看板", layout="wide", page_icon="💰")
st.title("📊 全球資產損益與全功能技術分析看板")

# --- [安全加密讀取 Secrets] ---
# 優先讀取 Streamlit Secrets，沒設定才顯示輸入框，確保 GitHub Public 後 ID 不外洩
if "GSHEET_ID" in st.secrets:
    gsheet_id = st.secrets["GSHEET_ID"]
else:
    gsheet_id = st.sidebar.text_input("請輸入 Google Sheet ID")

if not gsheet_id:
    st.info("請於 Streamlit 後台設定 Secrets 或在側邊欄輸入 ID。")
    st.stop()
# -----------------------------

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

# 3. 數據抓取與計算
usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('同步全球即時行情與配息數據中...'):
        price_map, div_map = {}, {}
        
        for sym in unique_symbols:
            tk = yf.Ticker(sym)
            price_map[sym] = tk.fast_info['last_price']
            # 配息數據 (過去一年)
            divs = tk.dividends
            if not divs.empty:
                last_year = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))]
                div_map[sym] = last_year.sum()
            else:
                div_map[sym] = 0.0

    # 4. 邏輯運算 (包含原本要求的稅務處理與合計金額)
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']

    def process_row(row):
        curr_price = price_map.get(row['symbol'], 0)
        mv_twd = curr_price * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        cost_twd = row['cost'] * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        
        div_per_share = div_map.get(row['symbol'], 0)
        total_div_raw = div_per_share * row['shares']
        # 稅務邏輯：美股非債券扣 30%，債券/台股不扣
        if row['currency'] == "USD":
            tax_rate = 0.7 if row['symbol'] not in bond_list else 1.0
            net_div_twd = total_div_raw * tax_rate * usd_to_twd
        else:
            net_div_twd = total_div_raw
        
        yield_rate = (div_per_share / curr_price * 100) if curr_price > 0 else 0
        return pd.Series([curr_price, mv_twd, profit_twd, roi, net_div_twd, yield_rate])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'yield_rate']] = df.apply(process_row, axis=1)

    # --- A. 頂部摘要區 (保留原格式) ---
    t_val = df['mv_twd'].sum()
    t_profit = df['profit_twd'].sum()
    t_div = df['net_div_twd'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("總資產市值 (TWD)", f"${t_val:,.0f}")
    m2.metric("總累計損益 (TWD)", f"${t_profit:,.0f}", f"{(t_profit/t_val*100):.2f}%")
    m3.metric("年度預估稅後配息 (TWD)", f"${t_div:,.0f}", help="美股非債券已扣30%稅額")

    # --- B. 配息統計表 (保留排序與匯出) ---
    st.markdown("---")
    st.subheader("💰 年度個股配息與殖利率統計 (NTD)")
    div_df = df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'yield_rate', 'net_div_twd']].copy()
    st.dataframe(div_df.sort_values('net_div_twd', ascending=False).style.format({
        'yield_rate': '{:.2f}%', 'net_div_twd': '{:,.0f}'
    }), use_container_width=True)
    st.download_button("📥 匯出配息統計表", div_df.to_csv(index=False).encode('utf-8-sig'), "dividend_report.csv", "text/csv")

    # --- C. 持倉明細與圖表 (保留原本資訊) ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    st.subheader("📝 完整持倉清單 (可排序)")
    detail_df = df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']]
    st.dataframe(detail_df.style.format({
        'current_price': '{:.2f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }), use_container_width=True)
    st.download_button("📥 匯出完整持倉明細", detail_df.to_csv(index=False).encode('utf-8-sig'), "portfolio_detail.csv", "text/csv")

    # --- D. 全功能技術分析 (50/200MA + RSI + Volume + MACD + BB) ---
    st.markdown("---")
    st.subheader("🔍 進階技術指標分析 (測試版)")
    stock_options = df[~df['symbol'].isin(bond_list)]['symbol'].unique()
    if len(stock_options) > 0:
        sel_stock = st.selectbox("選擇要分析的股票：", stock_options)
        with st.spinner('繪製多層指標圖表中...'):
            h = yf.Ticker(sel_stock).history(period="2y")
            # 指標計算
            h['MA50'] = h['Close'].rolling(50).mean()
            h['MA200'] = h['Close'].rolling(200).mean()
            h['MA20'] = h['Close'].rolling(20).mean()
            h['STD'] = h['Close'].rolling(20).std()
            h['Upper'] = h['MA20'] + (h['STD'] * 2)
            h['Lower'] = h['MA20'] - (h['STD'] * 2)
            delta = h['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            h['RSI'] = 100 - (100 / (1 + gain/loss))
            h['MACD'] = h['Close'].ewm(span=12).mean() - h['Close'].ewm(span=26).mean()
            h['Signal'] = h['MACD'].ewm(span=9).mean()
            h['Hist'] = h['MACD'] - h['Signal']

            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.1, 0.2, 0.2])
            # 股價+均線+布林
            fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價'), row=1, col=1)
            fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA', line=dict(dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上軌', line=dict(width=1, color='rgba(200,0,0,0.3)')), row=1, col=1)
            fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下軌', line=dict(width=1, color='rgba(0,200,0,0.3)')), row=1, col=1)
            # 交易量
            fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='交易量', marker_color='lightgray'), row=2, col=1)
            # RSI
            fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
            # MACD
            fig.add_trace(go.Scatter(x=h.index, y=h['MACD'], name='MACD'), row=4, col=1)
            fig.add_trace(go.Scatter(x=h.index, y=h['Signal'], name='信號'), row=4, col=1)
            fig.add_trace(go.Bar(x=h.index, y=h['Hist'], name='柱狀圖'), row=4, col=1)

            fig.update_layout(height=1000, hovermode="x unified", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"系統錯誤: {e}")
