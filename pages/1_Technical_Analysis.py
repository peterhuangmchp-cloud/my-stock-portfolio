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

# --- 2. 數據讀取 ---
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
                
                # 成交量均線 (判斷量增/量縮)
                h['Vol_MA5'] = h['Volume'].rolling(5).mean()

                # --- [數值抓取] ---
                last_c, last_m50, last_m200 = h['Close'].iloc[-1], h['MA50'].iloc[-1], h['MA200'].iloc[-1]
                last_rsi, last_bias = h['RSI'].iloc[-1], h['BIAS'].iloc[-1]
                last_vol, avg_vol = h['Volume'].iloc[-1], h['Vol_MA5'].iloc[-1]

                # --- [判斷邏輯] ---
                # 1. 趨勢判定
                if last_c > last_m200:
                    trend_label, trend_desc = ("📈 多頭排列", "股價 > 200MA 且 50MA > 200MA") if last_m50 > last_m200 else ("⚖️ 轉強整理", "股價已站上 200MA，但 50MA 尚未黃金交叉")
                else:
                    trend_label, trend_desc = "📉 空頭排列", "股價低於 200MA，趨勢偏弱"
                
                # 2. 成交量判定 (價量關係)
                price_change = h['Close'].iloc[-1] - h['Close'].iloc[-2]
                if last_vol > avg_vol * 1.5:
                    vol_label = "🔥 出量"
                    vol_desc = "成交量顯著放大 (超過5日均量1.5倍)，" + ("量增價漲 (攻擊)" if price_change > 0 else "量增價跌 (拋售)")
                elif last_vol < avg_vol * 0.7:
                    vol_label = "❄️ 縮量"
                    vol_desc = "成交量萎縮，市場觀望或籌碼沉澱。"
                else:
                    vol_label = "⚓ 平穩"
                    vol_desc = "成交量維持近期平均水準。"

                # --- [顯示看板] ---
                st.markdown("---")
                a1, a2, a3, a4, a5 = st.columns(5)
                a1.metric("長期趨勢", trend_label)
                a2.metric("50 / 200MA", f"{last_m50:.2f}", f"年線: {last_m200:.2f}", delta_color="normal")
                a3.metric("RSI (14)", f"{last_rsi:.1f}", "過熱" if last_rsi > 70 else ("超跌" if last_rsi < 30 else ""))
                a4.metric("200D 乖離", f"{last_bias:.1f}%")
                a5.metric("成交量狀態", vol_label, f"{(last_vol/1000000):.1f}M")

                with st.expander("📝 判定邏輯加註", expanded=True):
                    st.write(f"📌 **趨勢狀況**：{trend_desc}")
                    st.write(f"📌 **成交量狀況**：{vol_desc}")
                    st.write(f"📌 **數值參考**：RSI > 70 表過熱；200D 乖離率 ±15% 為極端值。")

                # --- [繪製四層圖表] ---
                fig = make_subplots(
                    rows=4, cols=1, shared_xaxes=True, 
                    vertical_spacing=0.06, 
                    row_heights=[0.5, 0.15, 0.15, 0.2],
                    subplot_titles=(
                        f"📊 {sel_stock} 收盤價 / 均線 / 布林通道", 
                        "📉 200D 乖離率 (BIAS %)", 
                        "📊 成交量 (與5日均量對比)", 
                        "💜 強弱指標 (RSI 14)"
                    )
                )
                
                # 1. 主圖
                fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價', line=dict(color='black', width=2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA', line=dict(color='orange', dash='dot')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(color='blue', dash='dash')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上軌', line=dict(color='rgba(173,216,230,0.5)')), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下軌', line=dict(color='rgba(173,216,230,0.5)'), fill='tonexty'), row=1, col=1)
                
                # 2. 乖離率
                fig.add_trace(go.Scatter(x=h.index, y=h['BIAS'], name='200D乖離%', line=dict(color='green')), row=2, col=1)
                
                # 3. 成交量 (加入5日均量線)
                colors = ['red' if h['Open'].iloc[i] < h['Close'].iloc[i] else 'green' for i in range(len(h))]
                fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='成交量', marker_color=colors, opacity=0.7), row=3, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['Vol_MA5'], name='5日均量', line=dict(color='black', width=1)), row=3, col=1)
                
                # 4. RSI
                fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI', line=dict(color='purple')), row=4, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

                fig.update_layout(height=1200, template="plotly_white", hovermode="x unified")
                fig.update_annotations(font_size=16) 
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("查無數據。")
except Exception as e:
    st.error(f"分析失敗: {e}")
