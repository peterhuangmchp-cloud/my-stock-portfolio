import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 驗證檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("🔍 進階技術指標分析")

# 讀取主頁傳遞的 ID
gsheet_id = st.secrets.get("GSHEET_ID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=1797698775"
    return pd.read_csv(url)['symbol'].unique()

try:
    symbols = load_symbols()
    sel_stock = st.selectbox("選擇分析標的：", [s for s in symbols if s not in ['TLT', 'SHV', 'SGOV', 'LQD']])
    
    with st.spinner('繪製多層指標中...'):
        h = yf.Ticker(sel_stock).history(period="2y")
        
        # 指標計算 (手動計算以避免依賴庫報錯)
        h['MA50'] = h['Close'].rolling(50).mean()
        h['MA200'] = h['Close'].rolling(200).mean()
        h['MA20'] = h['Close'].rolling(20).mean()
        h['Upper'] = h['MA20'] + (h['Close'].rolling(20).std() * 2)
        h['Lower'] = h['MA20'] - (h['Close'].rolling(20).std() * 2)
        
        # RSI
        delta = h['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        h['RSI'] = 100 - (100 / (1 + gain/loss))
        
        # MACD
        exp1 = h['Close'].ewm(span=12, adjust=False).mean()
        exp2 = h['Close'].ewm(span=26, adjust=False).mean()
        h['MACD'] = exp1 - exp2
        h['Signal'] = h['MACD'].ewm(span=9, adjust=False).mean()
        h['Hist'] = h['MACD'] - h['Signal']

        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.1, 0.2, 0.2])
        fig.add_trace(go.Candlestick(x=h.index, open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'], name='K線'), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA', line=dict(color='orange')), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上軌', line=dict(color='rgba(173,216,230,0.5)')), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下軌', line=dict(color='rgba(173,216,230,0.5)')), row=1, col=1)
        
        fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='成交量'), row=2, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['MACD'], name='MACD'), row=4, col=1)
        fig.add_trace(go.Bar(x=h.index, y=h['Hist'], name='柱狀圖'), row=4, col=1)

        fig.update_layout(height=1000, template="plotly_white", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"分析失敗: {e}")
