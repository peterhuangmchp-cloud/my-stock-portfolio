import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 🔐 分頁安全檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 安全考量：請先回到主頁進行身分驗證。")
    if st.button("⬅️ 回到主頁登入"):
        st.switch_page("stock_app.py")
    st.stop()

# --- 2. 技術分析功能 ---
st.title("🔍 進階技術指標與深度分析")

if 'gsheet_id' in st.session_state:
    try:
        gsheet_id = st.session_state['gsheet_id']
        url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=0"
        df_list = pd.read_csv(url)
        df_list.columns = df_list.columns.str.strip()
        stock_list = df_list['代號'].unique().tolist()
        
        selected_stock = st.selectbox("選擇分析標的", stock_list)
        period = st.select_slider("分析區間", options=["3mo", "6mo", "1y", "2y", "5y"], value="1y")

        # 獲取歷史數據
        df = yf.download(selected_stock, period=period, progress=False)
        
        # 計算技術指標
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)

        # 繪圖 (保留四層指標功能)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, 
                           row_heights=[0.5, 0.1, 0.2, 0.2])

        # 價格 + 布林
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BBU_20_2.0'], line=dict(color='rgba(255,255,255,0.4)'), name="布林上軌"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BBL_20_2.0'], line=dict(color='rgba(255,255,255,0.4)'), name="布林下軌"), row=1, col=1)

        # 成交量
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量", marker_color='orange'), row=2, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name="RSI", line=dict(color='purple')), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        # MACD
        fig.add_trace(go.Bar(x=df.index, y=df['MACDh_12_26_9'], name="MACD 柱狀體"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], name="MACD 線"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], name="訊號線"), row=4, col=1)

        fig.update_layout(height=800, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"分析數據載入失敗: {e}")
else:
    st.info("請先回到主頁完成身分驗證。")
