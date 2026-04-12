import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io

# --- 1. 驗證與標題 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📊 個股獲利與估值深度分析")

# --- 2. 數據讀取 (同步主程式 GID) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=3600) # 快取一小時，避免頻繁請求 API
def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            exclude = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
            return [str(s).strip() for s in df['symbol'].dropna().unique() if s not in exclude]
        return []
    except:
        return []

# --- 3. 獲取所有持倉的估值總表數據 ---
def get_all_valuation_data(symbols):
    all_data = []
    for sym in symbols:
        try:
            tick = yf.Ticker(sym)
            info = tick.info
            all_data.append({
                "Symbol": sym,
                "Current Price": info.get('currentPrice', info.get('regularMarketPrice', 0)),
                "EPS (Trailing)": info.get('trailingEps', 0),
                "Current P/E": info.get('trailingPE', 0),
                "Forward EPS": info.get('forwardEps', 0),
                "Forward P/E": info.get('forwardPE', 0)
            })
        except:
            continue
    return pd.DataFrame(all_data)

# --- 4. 執行與顯示 ---
symbols = load_symbols()

if symbols:
    # --- 第一部分：所有持倉估值總表 ---
    st.markdown("### 📋 持倉標的估值對照總表")
    
    if st.button("🔄 刷新總表數據"):
        st.session_state["valuation_df"] = get_all_valuation_data(symbols)
    
    # 確保有數據才顯示表格
    if "valuation_df" not in st.session_state:
        with st.spinner("首次載入數據中..."):
            st.session_state["valuation_df"] = get_all_valuation_data(symbols)
            
    df = st.session_state["valuation_df"]
    
    # 格式化表格
    st.dataframe(
        df.style.format({
            "Current Price": "{:.2f}",
            "EPS (Trailing)": "{:.2f}",
            "Current P/E": "{:.2f}",
            "Forward EPS": "{:.2f}",
            "Forward P/E": "{:.2f}"
        }).background_gradient(subset=['Forward P/E'], cmap='RdYlGn_r'),
        use_container_width=True
    )
    
    st.markdown("---")
    
    # --- 第二部分：原本的選單與深度分析 ---
    st.markdown("### 🔍 單一標的深度診斷")
    sel_stock = st.selectbox("請選擇代號查看詳細財報指標：", symbols)
    
    if sel_stock:
        tick = yf.Ticker(sel_stock)
        info = tick.info
        
        # 顯示獲利與營收細節
        d1, d2, d3 = st.columns(3)
        rev_growth = info.get('revenueGrowth', 0) * 100
        profit_margin = info.get('profitMargins', 0) * 100
        peg_ratio = info.get('pegRatio', 'N/A')
        
        d1.metric("營收成長 (YoY)", f"{rev_growth:.2f}%")
        d2.metric("淨利率 (Margin)", f"{profit_margin:.2f}%")
        d3.metric("PEG Ratio", f"{peg_ratio}")
        
        with st.expander(f"查看 {sel_stock} 更多財務細節"):
            st.write(f"**市值:** {info.get('marketCap', 0):,}")
            st.write(f"**分析師建議:** {info.get('recommendationKey', 'N/A').upper()}")
            st.write(f"**股息收益率:** {info.get('dividendYield', 0)*100:.2f}%")
            
else:
    st.error("無法取得代號清單，請檢查 Google Sheet 連線。")
