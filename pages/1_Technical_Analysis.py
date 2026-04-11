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

st.title("🔍 專業技術指標分析與邏輯診斷")

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
                # 計算關鍵指標
                h['MA50'] = h['Close'].rolling(50).mean()
                h['MA200'] = h['Close'].rolling(200).mean()
                h['MA20'] = h['Close'].rolling(20).mean()
                h['BIAS'] = ((h['Close'] - h['MA200']) / h['MA200']) * 100
                
                # RSI 
                delta = h['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                h['RSI'] = 100 - (100 / (1 + gain/loss))

                # --- 核心邏輯判斷 ---
                last_c = h['Close'].iloc[-1]
                last_m50 = h['MA50'].iloc[-1]
                last_m200 = h['MA200'].iloc[-1]
                last_rsi = h['RSI'].iloc[-1]
                last_bias = h['BIAS'].iloc[-1]

                # 趨勢邏輯：雙重確認
                if last_c > last_m200:
                    if last_m50 > last_m200:
                        trend_label = "📈 多頭排列"
                        trend_desc = "股價於 200MA 之上，且 50MA > 200MA (黃金交叉後)"
                    else:
                        trend_label = "⚖️ 轉強/整理"
                        trend_desc = "股價已站上 200MA，但短期均線(50MA)尚未穿過長期均線"
                else:
                    trend_label = "📉 空頭排列"
                    trend_desc = "股價低於 200MA，長線走勢偏弱"

                # RSI 邏輯
                rsi_label = "⚠️ 超買" if last_rsi > 70 else ("✅ 超賣" if last_rsi < 30 else "⚖️ 中性")
                rsi_desc = "RSI > 70 表短線過熱；RSI < 30 表短線超跌"

                # 乖離邏輯
                bias_label = "🔥 乖離過大" if last_bias > 15 else ("❄️ 乖離過低" if last_bias < -15 else "⚓ 正常")
                bias_desc = f"股價與 200MA 的距離 ({last_bias:.1f}%)。超過 ±15% 需警惕均值回歸。"

                # --- 顯示診斷看板 ---
                st.markdown("---")
                a1, a2, a3 = st.columns(3)
                a1.metric("長期趨勢形態", trend_label)
                a2.metric("RSI (14) 狀態", rsi_label, f"{last_rsi:.1f}")
                a3.metric("200D 乖離率", bias_label, f"{last_bias:.1f}%")

                # --- ⚠️ 重點：加註邏輯說明 ---
                with st.expander("📝 診斷邏輯說明 (FAE 專業基準)", expanded=False):
                    st.write(f"**1. 趨勢判斷基準：** {trend_desc}")
                    st.write(f"**2. RSI 判斷基準：** {rsi_desc}")
                    st.write(f"**3. 乖離率判斷基準：** {bias_desc}")
                    st.info("💡 註：本診斷以 200MA (年線) 作為長線牛熊分界點。")

                # --- 圖表與建議 (略) ---
                fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.5, 0.15, 0.15, 0.2])
                fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價'), row=1, col=1)
                fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(dash='dash')), row=1, col=1)
                fig.update_layout(height=900, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"分析失敗: {e}")
