import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io

# --- 1. 驗證與標題 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📊 全標的獲利與估值分析")

# --- 2. 數據讀取 (同步主程式 GID) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=3600)
def load_holdings():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            exclude = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
            return [str(s).strip().upper() for s in df['symbol'].dropna().unique() if s not in exclude]
        return []
    except:
        return []

def get_valuation_row(sym):
    """ 抓取單一標的核心估值數據 """
    try:
        tick = yf.Ticker(sym)
        info = tick.info
        if not info or 'regularMarketPrice' not in info and 'currentPrice' not in info:
            return None
        return {
            "Symbol": sym.upper(),
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', 0)),
            "EPS (Trailing)": info.get('trailingEps', 0),
            "Current P/E": info.get('trailingPE', 0),
            "Forward EPS": info.get('forwardEps', 0),
            "Forward P/E": info.get('forwardPE', 0)
        }
    except:
        return None

# --- 3. 執行邏輯 ---
holdings = load_holdings()

# --- 第一部分：持倉標的估值總表 ---
st.markdown("### 📋 持倉標的快照 (自動更新)")
if st.button("🔄 刷新持倉數據"):
    with st.spinner("正在掃描持倉數據..."):
        all_data = []
        for sym in holdings:
            row = get_valuation_row(sym)
            if row: all_data.append(row)
        st.session_state["valuation_df"] = pd.DataFrame(all_data)

if "valuation_df" in st.session_state:
    st.dataframe(
        st.session_state["valuation_df"].style.format({
            "Current Price": "{:.2f}", "EPS (Trailing)": "{:.2f}",
            "Current P/E": "{:.2f}", "Forward EPS": "{:.2f}", "Forward P/E": "{:.2f}"
        }).background_gradient(subset=['Forward P/E'], cmap='RdYlGn_r'),
        use_container_width=True
    )

st.markdown("---")

# --- 第二部分：自定義查詢 (不限持倉) ---
st.markdown("### 🔍 自定義標的深度查詢")
# 使用 st.selectbox 的 label 加上手動輸入功能
# 在 Streamlit 中，selectbox 支援輸入文字搜尋，但若要完全自訂，可用 text_input 搭配建議
manual_sym = st.text_input("輸入美股代號 (例如: MRVL, NVDA, TSLA):", "").upper().strip()

# 如果沒輸入，預設提供持倉選單
if not manual_sym:
    sel_stock = st.selectbox("或從持倉清單選擇：", [""] + holdings)
else:
    sel_stock = manual_sym

if sel_stock:
    with st.spinner(f'正在分析 {sel_stock} ...'):
        data = get_valuation_row(sel_stock)
        tick = yf.Ticker(sel_stock)
        info = tick.info
        
        if data:
            # 顯示核心 5 指標表格
            st.write(f"#### {sel_stock} 核心估值對照")
            st.table(pd.DataFrame([data]).set_index("Symbol"))
            
            # 深度指標
            d1, d2, d3 = st.columns(3)
            rev_growth = info.get('revenueGrowth', 0) * 100
            profit_margin = info.get('profitMargins', 0) * 100
            peg_ratio = info.get('pegRatio', 'N/A')
            
            d1.metric("營收成長 (YoY)", f"{rev_growth:.2f}%")
            d2.metric("淨利率 (Margin)", f"{profit_margin:.2f}%")
            d3.metric("PEG Ratio", f"{peg_ratio}")
            
            with st.expander("🔍 更多財務細節"):
                st.write(f"**市值:** {info.get('marketCap', 0):,}")
                st.write(f"**分析師建議:** {info.get('recommendationKey', 'N/A').upper()}")
                st.write(f"**預估 Forward EPS 來源:** Yahoo Finance 分析師平均預測值")
        else:
            st.error(f"找不到標的 {sel_stock}，請確認代號是否正確。")
