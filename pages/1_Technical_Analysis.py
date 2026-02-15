import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="進階技術分析", layout="wide")
st.title("🔍 進階技術指標與深度分析")

if 'gsheet_id' not in st.session_state:
    st.warning("請先回到主頁載入資料。")
    st.stop()

# 取得股票清單
@st.cache_data
def get_symbols(id):
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{id}/export?format=csv")
    return df['symbol'].unique().tolist()

symbols = get_symbols(st.session_state['gsheet_id'])
sel_stock = st.selectbox("選擇分析標的：", [s for s in symbols if s not in ['TLT','SHV','SGOV','LQD']])

if sel_stock:
    # 抓取 2 年數據確保均線計算正確 (解決圖 1 報錯)
    h = yf.Ticker(sel_stock).history(period="2y")
    
    # 指標計算
    h['MA50'] = h['Close'].rolling(50).mean()
    h['MA200'] = h['Close'].rolling(200).mean()
    h['MA20'] = h['Close'].rolling(20).mean()
    h['STD'] = h['Close'].rolling(20).std()
    h['Upper'] = h['MA20'] + (h['STD'] * 2)
    h['Lower'] = h['MA20'] - (h['STD'] * 2)
    # RSI
    delta = h['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    h['RSI'] = 100 - (100 / (1 + gain/loss))
    # MACD
    h['MACD'] = h['Close'].ewm(span=12).mean() - h['Close'].ewm(span=26).mean()
    h['Signal'] = h['MACD'].ewm(span=9).mean()
    h['Hist'] = h['MACD'] - h['Signal']

    # 繪圖
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.1, 0.2, 0.2])
    fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價'), row=1, col=1)
    fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上', line=dict(dash='dot', color='rgba(255,0,0,0.3)')), row=1, col=1)
    fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下', line=dict(dash='dot', color='rgba(0,255,0,0.3)')), row=1, col=1)
    fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA'), row=1, col=1)
    fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA'), row=1, col=1)
    fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='交易量', marker_color='gray'), row=2, col=1)
    fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI'), row=3, col=1)
    fig.add_trace(go.Scatter(x=h.index, y=h['MACD'], name='MACD'), row=4, col=1)
    fig.add_trace(go.Bar(x=h.index, y=h['Hist'], name='MACD柱狀圖'), row=4, col=1)
    
    fig.update_layout(height=900, template="plotly_white", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # --- 技術指標說明與分析 ---
    st.markdown("---")
    st.subheader("💡 技術指標深度分析報告")
    c1, c2 = st.columns(2)
    with c1:
        st.info("**📈 趨勢指標**")
        macd_txt = "🟢 MACD 多頭排列" if h['MACD'].iloc[-1] > h['Signal'].iloc[-1] else "🔴 MACD 空頭排列"
        ma_txt = "🌟 站上 200MA 長線看好" if h['Close'].iloc[-1] > h['MA200'].iloc[-1] else "⚠️ 低於 200MA 趨勢偏弱"
        st.write(f"- **MACD趨勢**: {macd_txt}")
        st.write(f"- **均線位置**: {ma_txt}")
    with c2:
        st.info("**📏 震盪指標**")
        rsi_v = h['RSI'].iloc[-1]
        rsi_txt = "🔥 過熱 (RSI>70)" if rsi_v > 70 else ("❄️ 超跌 (RSI<30)" if rsi_v < 30 else "⚖️ 中性")
        bb_p = h['Close'].iloc[-1]
        bb_txt = "🚀 觸碰上軌 (超漲)" if bb_p > h['Upper'].iloc[-1] else ("🩸 觸碰下軌 (超跌)" if bb_p < h['Lower'].iloc[-1] else "↔️ 通道內運行")
        st.write(f"- **RSI 強弱**: {rsi_txt} ({rsi_v:.1f})")
        st.write(f"- **布林狀態**: {bb_txt}")
