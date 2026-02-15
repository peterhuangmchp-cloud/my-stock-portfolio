import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 驗證檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("🔍 專業技術指標分析與 AI 建議")

gsheet_id = st.secrets.get("GSHEET_ID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=1797698775"
    return pd.read_csv(url)['symbol'].unique()

try:
    symbols = load_symbols()
    sel_stock = st.selectbox("選擇分析標的：", [s for s in symbols if s not in ['TLT', 'SHV', 'SGOV', 'LQD']])
    
    with st.spinner('生成技術診斷報告中...'):
        h = yf.Ticker(sel_stock).history(period="2y")
        
        # 指標計算
        h['MA50'] = h['Close'].rolling(50).mean()
        h['MA200'] = h['Close'].rolling(200).mean()
        h['MA20'] = h['Close'].rolling(20).mean()
        h['Upper'] = h['MA20'] + (h['Close'].rolling(20).std() * 2)
        h['Lower'] = h['MA20'] - (h['Close'].rolling(20).std() * 2)
        
        # --- 修正：乖離率 (BIAS) 計算基準改為 MA200 ---
        h['BIAS'] = ((h['Close'] - h['MA200']) / h['MA200']) * 100
        
        # RSI 手動計算
        delta = h['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        h['RSI'] = 100 - (100 / (1 + gain/loss))

        # --- 技術指標分析診斷邏輯 ---
        last_close = h['Close'].iloc[-1]
        last_rsi = h['RSI'].iloc[-1]
        last_ma50 = h['MA50'].iloc[-1]
        last_ma200 = h['MA200'].iloc[-1]
        last_upper = h['Upper'].iloc[-1]
        last_lower = h['Lower'].iloc[-1]
        last_bias = h['BIAS'].iloc[-1]

        # 診斷狀態
        trend = "📈 多頭排列" if last_ma50 > last_ma200 else "📉 空頭排列"
        rsi_status = "⚠️ 超買 (過熱)" if last_rsi > 70 else ("✅ 超賣 (超跌)" if last_rsi < 30 else "⚖️ 中性平衡")
        # 長線乖離判斷標準通常較寬，此處設為 15% 作為警示參考
        bias_status = "🔥 長線乖離過高" if last_bias > 15 else ("❄️ 長線乖離過低" if last_bias < -15 else "⚓ 長線乖離正常")

        # --- 顯示診斷面板 ---
        st.markdown("---")
        a1, a2, a3 = st.columns(3)
        a1.metric("長期趨勢判斷", trend)
        a2.metric("RSI 指標狀態", rsi_status, f"{last_rsi:.1f}")
        a3.metric("200日乖離率", bias_status, f"{last_bias:.2f}%")

        with st.expander("💡 綜合操作建議", expanded=True):
            advice = []
            if last_ma50 > last_ma200:
                advice.append("- **趨勢面**：當前處於多頭市場，MA200 具備強力支撐。")
            else:
                advice.append("- **趨勢面**：當前處於空頭市場，股價長期低於 MA200，走勢偏弱。")
            
            if last_bias > 20:
                advice.append("- **長線風險**：目前股價與 MA200 的正乖離率過大，代表長線基期已高，需預防均值回歸的拉回壓力。")
            elif last_bias < -20:
                advice.append("- **長線機會**：目前股價與 MA200 的負乖離率極大，處於歷史低位區，可留意超跌反彈的長線佈局機會。")
            
            if last_rsi > 70:
                advice.append("- **短線提醒**：RSI 顯示股價短線過熱。")
            
            st.write("\n".join(advice))

        # --- 繪製四層圖表 ---
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.04, 
            row_heights=[0.5, 0.15, 0.15, 0.2]
        )
        
        # 1. 股價與均線與布林
        fig.add_trace(go.Scatter(x=h.index, y=h['Close'], name='收盤價', line=dict(color='black', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['MA50'], name='50MA', line=dict(color='orange', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['MA200'], name='200MA', line=dict(color='blue', dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['Upper'], name='布林上軌', line=dict(color='rgba(173,216,230,0.5)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=h['Lower'], name='布林下軌', line=dict(color='rgba(173,216,230,0.5)', width=1), fill='tonexty'), row=1, col=1)
        
        # 2. 乖離率 BIAS (相對於 MA200)
        fig.add_trace(go.Scatter(x=h.index, y=h['BIAS'], name='200D乖離率%', line=dict(color='green', width=1.5)), row=2, col=1)
        fig.add_hline(y=0, line_dash="solid", line_color="gray", row=2, col=1)
        
        # 3. 成交量
        fig.add_trace(go.Bar(x=h.index, y=h['Volume'], name='成交量', marker_color='rgba(100,100,100,0.5)'), row=3, col=1)
        
        # 4. RSI
        fig.add_trace(go.Scatter(x=h.index, y=h['RSI'], name='RSI', line=dict(color='purple')), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

        fig.update_layout(height=1000, template="plotly_white", hovermode="x unified", showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"分析失敗: {e}")
