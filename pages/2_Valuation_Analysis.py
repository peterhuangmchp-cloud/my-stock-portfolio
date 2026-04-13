import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
import time

# --- 1. 驗證與行動端設定 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📊 全標的獲利與估值分析")

# --- 2. 數據讀取邏輯 (修復 400 錯誤) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_holdings():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            # 排除非股類代號
            exclude = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
            return [str(s).strip().upper() for s in df['symbol'].dropna().unique() if s not in exclude]
        return []
    except:
        return []

def get_valuation_row(sym):
    """ 安全抓取估值數據，預防 Rate Limit """
    try:
        tick = yf.Ticker(sym)
        # 優先使用 fast_info，負擔較小
        info = tick.info
        if not info or ('currentPrice' not in info and 'regularMarketPrice' not in info):
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

# --- 3. 執行介面 ---
holdings = load_holdings()

# 建立分頁，讓手機好操作
tab_summary, tab_search = st.tabs(["📋 持倉總表", "🔍 單一查詢"])

with tab_summary:
    st.markdown("### 持倉估值對照")
    if st.button("🔄 刷新/加載持倉數據", use_container_width=True):
        all_data = []
        progress_bar = st.progress(0)
        for i, sym in enumerate(holdings):
            row = get_valuation_row(sym)
            if row:
                all_data.append(row)
            # 關鍵緩衝：每抓一檔休息 0.2 秒，防止被鎖
            time.sleep(0.2)
            progress_bar.progress((i + 1) / len(holdings))
        
        st.session_state["val_df"] = pd.DataFrame(all_data)
        progress_bar.empty()

    if "val_df" in st.session_state:
        st.dataframe(
            st.session_state["val_df"].style.format({
                "Current Price": "{:.2f}", "EPS (Trailing)": "{:.2f}",
                "Current P/E": "{:.2f}", "Forward EPS": "{:.2f}", "Forward P/E": "{:.2f}"
            }).background_gradient(subset=['Forward P/E'], cmap='RdYlGn_r'),
            use_container_width=True
        )
    else:
        st.info("💡 點擊上方按鈕開始掃描持倉數據。")

with tab_search:
    st.markdown("### 深度查詢 (不限持倉)")
    manual_sym = st.text_input("輸入代號 (如: MRVL, AVGO):", "").upper().strip()
    
    # 選單提供持倉作為快捷選擇
    quick_select = st.selectbox("或快速選擇持倉：", [""] + holdings)
    target = manual_sym if manual_sym else quick_select

    if target:
        with st.spinner(f'分析 {target} 中...'):
            data = get_valuation_row(target)
            if data:
                # 核心 5 指標
                st.write(f"#### {target} 核心數據")
                st.table(pd.DataFrame([data]).set_index("Symbol"))
                
                # 額外細節
                tick = yf.Ticker(target)
                info = tick.info
                c1, c2 = st.columns(2)
                c1.metric("營收成長 (YoY)", f"{info.get('revenueGrowth', 0)*100:.2f}%")
                c2.metric("淨利率", f"{info.get('profitMargins', 0)*100:.2f}%")
                
                with st.expander("更多細節"):
                    st.write(f"**市值:** {info.get('marketCap', 0):,}")
                    st.write(f"**PEG Ratio:** {info.get('pegRatio', 'N/A')}")
                    st.info("註：Forward 數據取自分析師預估(Normalized)。")
            else:
                st.error("找不到標的，請確認代號是否正確。")
