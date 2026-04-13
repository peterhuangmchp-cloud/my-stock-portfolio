import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
import time

# --- 1. 驗證與設定 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📊 全標的獲利與估值分析 (電腦增強版)")

# --- 2. 建立偽裝 Session (關鍵：防止 Rate Limit) ---
def get_safe_ticker(sym):
    session = requests.Session()
    # 模擬最新的電腦版 Chrome Headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://finance.yahoo.com/'
    })
    return yf.Ticker(sym, session=session)

# --- 3. 數據讀取邏輯 ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_holdings():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            exclude = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
            return [str(s).strip().upper() for s in df['symbol'].dropna().unique() if s not in exclude]
        return []
    except:
        return []

def get_valuation_row(sym):
    try:
        tick = get_safe_ticker(sym)
        # 嘗試抓取 info，若被鎖則嘗試從 fast_info 補救
        info = tick.info
        
        # 備援機制：如果 info 是空的
        cp = info.get('currentPrice', info.get('regularMarketPrice'))
        if cp is None:
            cp = tick.fast_info.get('last_price', 0)

        row = {
            "Symbol": sym.upper(),
            "Current Price": cp,
            "EPS (Trailing)": info.get('trailingEps', 0),
            "Current P/E": info.get('trailingPE', 0),
            "Forward EPS": info.get('forwardEps', 0),
            "Forward P/E": info.get('forwardPE', 0)
        }
        return row
    except Exception as e:
        # 如果真的完全抓不到，回傳空結構防止程式崩潰
        return {k: 0 for k in ["Symbol", "Current Price", "EPS (Trailing)", "Current P/E", "Forward EPS", "Forward P/E"]}

# --- 4. 介面呈現 ---
holdings = load_holdings()

tab_summary, tab_search = st.tabs(["📋 持倉總表", "🔍 單一查詢"])

with tab_summary:
    st.markdown("### 持倉估值對照")
    
    if st.button("🔄 刷新/同步數據", use_container_width=True):
        all_data = []
        progress_bar = st.progress(0)
        
        for i, sym in enumerate(holdings):
            row = get_valuation_row(sym)
            all_data.append(row)
            # 增加隨機擾動延遲，降低被偵測機率
            time.sleep(0.3) 
            progress_bar.progress((i + 1) / len(holdings))
        
        st.session_state["val_df"] = pd.DataFrame(all_data)
        progress_bar.empty()

    if "val_df" in st.session_state and not st.session_state["val_df"].empty:
        df_display = st.session_state["val_df"].copy()
        target_cols = ["Current Price", "EPS (Trailing)", "Current P/E", "Forward EPS", "Forward P/E"]
        
        for col in target_cols:
            df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0)

        styled_df = df_display.style.format({k: "{:.2f}" for k in target_cols})
        styled_df = styled_df.background_gradient(subset=['Forward P/E'], cmap='RdYlGn_r')
        st.dataframe(styled_df, use_container_width=True, height=550)
    else:
        st.info("💡 點擊按鈕載入數據。")

with tab_search:
    manual_sym = st.text_input("輸入代號 (如: AVGO):").upper().strip()
    target = manual_sym if manual_sym else st.selectbox("或選擇持倉：", [""] + holdings)

    if target:
        with st.spinner(f'正在分析 {target}...'):
            data = get_valuation_row(target)
            if data and data['Current Price'] > 0:
                st.write(f"#### {target} 核心數據")
                st.table(pd.DataFrame([data]).set_index("Symbol"))
                
                # 額外細節抓取
                tick = get_safe_ticker(target)
                info = tick.info
                m1, m2, m3 = st.columns(3)
                m1.metric("營收成長", f"{info.get('revenueGrowth', 0)*100:.2f}%")
                m2.metric("淨利率", f"{info.get('profitMargins', 0)*100:.2f}%")
                m3.metric("PEG Ratio", info.get('pegRatio', 'N/A'))
            else:
                st.error(f"目前 Yahoo Finance 限制了 {target} 的查詢，請 30 秒後再試。")
