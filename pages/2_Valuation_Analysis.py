import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. 驗證檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📈 個股獲利與估值深度分析")

gsheet_id = st.secrets.get("GSHEET_ID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=1797698775"
    return pd.read_csv(url)['symbol'].unique()

try:
    symbols = load_symbols()
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    stock_options = [s for s in symbols if s not in bond_list]
    sel_stock = st.selectbox("選擇分析標的：", stock_options)
    
    with st.spinner('提取財務數據中...'):
        tk = yf.Ticker(sel_stock)
        info = tk.info
        
        # --- A. 估值對照面板 (P/E Ratio) ---
        st.markdown(f"### 🔍 {sel_stock} 估值倍數對照")
        c1, c2, c3 = st.columns(3)
        
        pe_trailing = info.get('trailingPE')
        pe_forward = info.get('forwardPE')
        
        c1.metric("12M Trailing P/E (目前)", f"{pe_trailing:.2f}" if pe_trailing else "N/A")
        c2.metric("Forward P/E (遠期)", f"{pe_forward:.2f}" if pe_forward else "N/A")
        
        if pe_trailing and pe_forward:
            diff = ((pe_forward - pe_trailing) / pe_trailing * 100)
            c3.metric("估值預期變化", f"{diff:.1f}%", help="負值代表獲利增長超過股價漲幅，基期變低")

        st.markdown("---")
        
        # --- B. EPS 獲利能力對照 (GAAP vs Non-GAAP) ---
        st.markdown("### 💰 EPS 每股盈餘分析")
        
        # 準備 EPS 數據
        # yfinance 的 trailingEps 通常是 GAAP
        # forwardEps 是分析師預估，通常基於 Non-GAAP (Adjusted)
        # 另外提取分析師預期的 Adjusted EPS (如果有的話)
        
        eps_data = {
            "指標": [
                "GAAP EPS (Trailing)", 
                "Non-GAAP EPS (Adjusted/Est.)", 
                "Forward EPS (明年預估)"
            ],
            "數值": [
                f"${info.get('trailingEps', 0):.2f}",
                f"${info.get('epsActual', info.get('trailingEps', 0)):.2f}", # 嘗試抓取實際調整後 EPS
                f"${info.get('forwardEps', 0):.2f}"
            ],
            "意義說明": [
                "法定會計獲利 (含所有開支)",
                "營運核心獲利 (排除一次性支出)",
                "市場對未來 12 個月的獲利展望"
            ]
        }
        
        df_eps = pd.DataFrame(eps_data)
        st.table(df_eps)

        # --- C. 數據深度解讀 ---
        with st.expander("💡 如何判讀這些數據？", expanded=True):
            st.write(f"""
            1. **GAAP vs Non-GAAP**: 如果 {sel_stock} 的 Non-GAAP 高出 GAAP 很多，代表公司有較多非現金支出(如股權獎勵)。
            2. **P/E 對比**: 
               - 若 **Forward P/E < Trailing P/E**，代表市場預期獲利會成長。
               - 若差距極大，需注意分析師是否過度樂觀。
            3. **PEG Ratio**: 該標的目前的 PEG 為 **{info.get('pegRatio', 'N/A')}** (通常 < 1 代表股價相對成長潛力被低估)。
            """)

        # --- D. 盈餘歷史圖表 ---
        st.markdown("### 📊 盈餘發布紀錄 (Surprise History)")
        earnings_hist = tk.get_earnings_dates(limit=8)
        if earnings_hist is not None and not earnings_hist.empty:
            st.dataframe(earnings_hist[['Reported EPS', 'EPS Estimate', 'Surprise(%)']], use_container_width=True)
        else:
            st.info("暫無盈餘歷史數據。")

except Exception as e:
    st.error(f"數據加載失敗: {e}")
