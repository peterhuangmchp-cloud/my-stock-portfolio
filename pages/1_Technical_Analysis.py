import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import requests

# --- 1. 驗證與標題 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("🔍 專業技術指標分析 (全指標完整版)")

# --- 2. 數據讀取 (同步主程式 GID) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            exclude = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
            symbols = df['symbol'].dropna().unique()
            return [str(s).strip() for s in symbols if s not in exclude]
        return []
    except:
        return []

# --- 3. 執行技術分析 ---
try:
    available_symbols = load_symbols()
    if available_symbols:
        sel_stock = st.selectbox("選擇分析標的：", available_symbols)
        
        with st.spinner(f'正在分析 {sel_stock} ...'):
            h = yf.Ticker(sel_stock).history(period="2y")
            
            if not h.empty:
                # --- [指標計算區] ---
                h['MA50'] = h['Close'].rolling(50).mean()
                h['MA200'] = h['Close'].rolling(200).mean()
                h['MA20'] = h['Close'].rolling(20).mean()
                h['Upper'] = h['MA20'] + (h['Close'].rolling(20).std() * 2)
                h['Lower'] = h['MA20'] - (h['Close'].rolling(20).std() * 2)
                h['BIAS'] = ((h['Close'] - h['MA200']) / h['MA200']) * 100
                
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                h['RSI'] = 100 - (100 / (1 + gain/loss))

                # --- [邏輯診斷區] ---
                last_c, last_m50, last_m200 = h['Close'].iloc[-1], h['MA50'].iloc[-1], h['MA200'].iloc[-1]
                last_rsi, last_bias = h['RSI'].iloc[-1], h['BIAS'].iloc[-1]

                if last_c > last_m200:
                    trend_label, trend_desc = ("📈 多頭排列", "股價 > 200MA 且 50MA > 200MA") if last_m50 > last_m200 else ("⚖️ 轉強整理", "股價已站上 200MA，但 50MA 尚未黃金交叉")
                else:
                    trend_label, trend_desc = "📉 空頭排列", "股價低於 200MA，趨勢偏弱"

                # --- [顯示指標面板] ---
                st.markdown("---")
                a1, a2, a3 = st.columns(3)
                a1.metric("長期趨勢形態", trend_label)
                a2.metric("RSI (14)", f"{last_rsi:.1f}", "⚠️ 過熱" if last_rsi > 70 else ("✅ 超跌" if last_rsi < 30 else ""))
                a3.metric("200D 乖離率", f"{last_bias:.1f}%", "🔥 偏高" if abs(last_bias) > 15 else "")

                with st.expander("📝 判定邏輯加註", expanded=True):
                    st.write(f"📌 **多空判定**：{trend_desc}")
                    st.write(f"📌 **數值參考**：RSI > 70 表過熱；200D 乖離率 ±15% 為極端值。")

                # --- [繪製四層圖表] ---
                fig = make_subplots(
                    rows=4, cols=1, shared_xaxes=True, 
                    vertical_spacing=0.04, row_heights=[0.5, 0.15, 0.15, 0.2]
                )
                
                # 1. 主圖：收盤價 + 均線 + 布林
                fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價', line=dict(color='black', width=2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA', line=dict(color='orange', dash='dot')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(color='blue', dash='dash')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上軌', line=dict(color='rgba(173,216,230,0.5)')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下軌', fill='tonexty'), row=1, col=1)
                
                # 2. 乖離率 (BIAS)
                fig.add_trace(go.Scatter(x=h.index, y=h['BIAS'], name='200D乖離%', line=dict(color='green')), row=2, col=1)
                fig.add_hline(y=0, line_dash="solid", line_color="gray", row=2, col=1)
                
                # 3. 成交量
                colors = ['red' if h['Open'].iloc[i] < h['Close'].iloc[i] else 'green' for i in range(len(h))]
                fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='成交量', marker_color=colors, opacity=0.7), row=3, col=1)
                
                # 4. RSI
                fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI', line=dict(color='purple')), row=4, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

                fig.update_layout(height=1100, template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("查無數據。")
except Exception as e:
    st.error(f"分析失敗: {e}")
