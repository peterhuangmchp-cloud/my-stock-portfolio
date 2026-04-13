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

st.title("📊 全標的獲利與估值分析 (電腦優化版)")

# --- 2. 數據讀取邏輯 ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_holdings():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
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
        tick = yf.Ticker(sym)
        info = tick.info
        # 建立一個標準字典，確保所有 key 都存在
        row = {
            "Symbol": sym.upper(),
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', 0)),
            "EPS (Trailing)": info.get('trailingEps', 0),
            "Current P/E": info.get('trailingPE', 0),
            "Forward EPS": info.get('forwardEps', 0),
            "Forward P/E": info.get('forwardPE', 0)
        }
        return row
    except:
        return None

# --- 3. 介面呈現 ---
holdings = load_holdings()

tab_summary, tab_search = st.tabs(["📋 持倉總表", "🔍 單一查詢"])

with tab_summary:
    st.markdown("### 持倉估值對照")
    
    # 建立一個更新按鈕
    if st.button("🔄 刷新持倉數據 (電腦版需手動點擊)", use_container_width=True):
        all_data = []
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        for i, sym in enumerate(holdings):
            status_text.text(f"正在抓取 {sym} ({i+1}/{len(holdings)})...")
            row = get_valuation_row(sym)
            if row:
                all_data.append(row)
            time.sleep(0.15) # 稍微加速但保留緩衝
            progress_bar.progress((i + 1) / len(holdings))
        
        st.session_state["val_df"] = pd.DataFrame(all_data)
        status_text.empty()
        progress_bar.empty()

    # --- 修復 KeyError 的核心邏輯 ---
    if "val_df" in st.session_state and not st.session_state["val_df"].empty:
        df_display = st.session_state["val_df"].copy()
        
        # 強制補齊欄位，如果 API 沒抓到，就填入 0 或 None，避免表格格式化報錯
        target_cols = ["Current Price", "EPS (Trailing)", "Current P/E", "Forward EPS", "Forward P/E"]
        for col in target_cols:
            if col not in df_display.columns:
                df_display[col] = 0.0
        
        # 將數據轉換為數值型態，避免 String 導致計算錯誤
        for col in target_cols:
            df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0)

        # 格式化顯示
        styled_df = df_display.style.format({
            "Current Price": "{:.2f}",
            "EPS (Trailing)": "{:.2f}",
            "Current P/E": "{:.2f}",
            "Forward EPS": "{:.2f}",
            "Forward P/E": "{:.2f}"
        })
        
        # 漸層色邏輯：綠色表示 Forward P/E 較低 (便宜)
        styled_df = styled_df.background_gradient(subset=['Forward P/E'], cmap='RdYlGn_r')
        
        st.dataframe(styled_df, use_container_width=True, height=500)
    else:
        st.info("💡 數據尚未載入。請點擊上方按鈕抓取最新估值數據。")

with tab_search:
    st.markdown("### 深度查詢")
    col_input, col_quick = st.columns(2)
    with col_input:
        manual_sym = st.text_input("輸入代號 (如: MRVL):").upper().strip()
    with col_quick:
        quick_select = st.selectbox("或快速選擇持倉：", [""] + holdings)
    
    target = manual_sym if manual_sym else quick_select

    if target:
        with st.spinner(f'正在深度分析 {target}...'):
            data = get_valuation_row(target)
            if data:
                st.write(f"#### {target} 核心數據")
                # 橫向顯示核心 5 指標
                st.table(pd.DataFrame([data]).set_index("Symbol"))
                
                # 詳細財報指標
                tick = yf.Ticker(target)
                info = tick.info
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("營收成長 (YoY)", f"{info.get('revenueGrowth', 0)*100:.2f}%")
                m2.metric("淨利率", f"{info.get('profitMargins', 0)*100:.2f}%")
                m3.metric("PEG Ratio", f"{info.get('pegRatio', 'N/A')}")
                m4.metric("股息率", f"{info.get('dividendYield', 0)*100:.2f}%")
                
                st.info(f"💡 **估值分析**：{target} 的 Forward P/E 為 {data['Forward P/E']:.2f}。")
            else:
                st.error("無法取得該標的數據。")
