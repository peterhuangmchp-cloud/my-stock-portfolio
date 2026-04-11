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

st.title("🔍 專業技術指標分析")

# --- 2. 核心數據讀取 (同步主程式 GID) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID") # 同步主程式使用的持倉分頁 ID

def load_symbols_from_main():
    # 這裡直接連動您的持倉分頁
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            
            # 取得代號，排除掉現金或不適合技術分析的標的
            exclude = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
            symbols = df['symbol'].dropna().unique()
            return [str(s).strip() for s in symbols if s not in exclude]
        else:
            st.error(f"無法讀取主分頁 (Status: {response.status_code})。請確認 MAIN_GID 正確。")
            return []
    except Exception as e:
        st.error(f"連線異常: {e}")
        return []

# --- 3. 執行技術分析 ---
try:
    available_symbols = load_symbols_from_main()
    
    if available_symbols:
        sel_stock = st.selectbox("選擇分析標的：", available_symbols)
        
        with st.spinner(f'正在分析 {sel_stock} ...'):
            # 抓取 2 年數據
            h = yf.Ticker(sel_stock).history(period="2y")
            
            if not h.empty:
                # 指標計算
                h['MA50'] = h['Close'].rolling(50).mean()
                h['MA200'] = h['Close'].rolling(200).mean()
                h['MA20'] = h['Close'].rolling(20).mean()
                h['Upper'] = h['MA20'] + (h['Close'].rolling(20).std() * 2)
                h['Lower'] = h['MA20'] - (h['Close'].rolling(20).std() * 2)
                h['BIAS'] = ((h['Close'] - h['MA200']) / h['MA200']) * 100
                
                # RSI 計算
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                h['RSI'] = 100 - (100 / (1 + gain/loss))

                # --- 診斷面板 ---
                lc, lr, lb = h['Close'].iloc[-1], h['RSI'].iloc[-1], h['BIAS'].iloc[-1]
                m50, m200 = h['MA50'].iloc[-1], h['MA200'].iloc[-1]
                
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("趨勢形態 (50/200MA)", "📈 多頭" if m50 > m200 else "📉 空頭")
                c2.metric("RSI (14)", f"{lr:.1f}", "⚠️ 過熱" if lr > 70 else ("✅ 超跌" if lr < 30 else "⚖️ 中性"))
                c3.metric("200日乖離率", f"{lb:.2f}%", "🔥 偏高" if lb > 15 else ("❄️ 偏低" if lb < -15 else "⚓ 正常"))

                # --- 專業繪圖 ---
                fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                                   vertical_spacing=0.04, row_heights=[0.5, 0.15, 0.15, 0.2])
                
                # 1. 主圖：股價/均線/布林
                fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價', line=dict(color='black', width=2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(color='blue', dash='dash')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA', line=dict(color='orange', dash='dot')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上軌', line=dict(color='rgba(173,216,230,0.5)')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下軌', fill='tonexty'), row=1, col=1)
                
                # 2. 乖離率 (BIAS)
                fig.add_trace(go.Scatter(x=h.index, y=h['BIAS'], name='乖離%', line=dict(color='green')), row=2, col=1)
                fig.add_hline(y=0, line_dash="solid", line_color="gray", row=2, col=1)
                
                # 3. 成交量
                fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='成交量'), row=3, col=1)
                
                # 4. RSI
                fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI', line=dict(color='purple')), row=4, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

                fig.update_layout(height=900, template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"Yahoo Finance 抓不到 {sel_stock} 資料，請確認代號（如台股需加 .TW）。")
    else:
        st.info("💡 提示：請確認 Secrets 中的 GSHEET_ID 與 MAIN_GID 是否為新試算表的數值。")

except Exception as e:
    st.error(f"分析失敗: {e}")
