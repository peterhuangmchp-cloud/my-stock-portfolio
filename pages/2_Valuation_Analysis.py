import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. 驗證檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📈 個股估值與獲利分析 (Fundamental Analysis)")

gsheet_id = st.secrets.get("GSHEET_ID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=1797698775"
    return pd.read_csv(url)['symbol'].unique()

try:
    symbols = load_symbols()
    # 過濾掉債券標的
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    stock_options = [s for s in symbols if s not in bond_list]
    
    sel_stock = st.selectbox("選擇分析標的：", stock_options)
    
    with st.spinner('從 yfinance 提取財務指標中...'):
        tk = yf.Ticker(sel_stock)
        info = tk.info
        
        # 提取核心指標
        pe_trailing = info.get('trailingPE', 0)
        pe_forward = info.get('forwardPE', 0)
        eps_trailing = info.get('trailingEps', 0)  # 通常為 GAAP
        
        # 獲取 GAAP vs Non-GAAP (從分析師預期或財務報表特徵中提取)
        # Note: yfinance 對 Non-GAAP 的標註較分散，通常用 "Earnings from continuing operations" 比較
        financials = tk.get_income_stmt()
        
        # --- A. 估值概覽面板 ---
        st.markdown(f"### 🔍 {sel_stock} 估值指標")
        c1, c2, c3 = st.columns(3)
        
        c1.metric("本益比 (Trailing P/E)", f"{pe_trailing:.2f}" if pe_trailing else "N/A")
        c2.metric("遠期本益比 (Forward P/E)", f"{pe_forward:.2f}" if pe_forward else "N/A")
        
        pe_diff = ((pe_forward - pe_trailing) / pe_trailing * 100) if pe_trailing and pe_forward else 0
        c3.metric("P/E 變化預期", f"{pe_diff:.1f}%", help="負值代表市場預期未來獲利增長，導致 Forward P/E 降低")

        st.markdown("---")
        
        # --- B. EPS 獲利分析 (GAAP vs Non-GAAP) ---
        st.markdown("### 💰 獲利能力分析 (EPS)")
        
        # 建立展示表格
        eps_data = {
            "指標": ["每股盈餘 (EPS Trailing)", "預估每股盈餘 (Forward EPS)"],
            "數值": [
                f"${info.get('trailingEps', 0):.2f}",
                f"${info.get('forwardEps', 0):.2f}"
            ],
            "類型說明": ["通常為 GAAP (標準會計準則)", "通常為 Non-GAAP / 分析師調整後預估"]
        }
        st.table(pd.DataFrame(eps_data))

        with st.expander("📝 專有名詞小科普"):
            st.write("""
            - **GAAP EPS**: 嚴格遵守會計準則的獲利，包含所有一次性支出或股票獎勵開支。
            - **Non-GAAP EPS**: 剔除一次性或非現金支出，更能反映公司『營運核心』的獲利能力。
            - **Trailing vs Forward**: Trailing 是看過去一年的成績單；Forward 是看分析師對未來一年的期望。
            """)

        # --- C. 歷史獲利趨勢 (圖表) ---
        st.markdown("### 📊 近年獲利趨勢")
        if not financials.empty:
            # 取得淨利數據 (Net Income)
            net_income = financials.loc['Net Income'].head(4) # 取近四年
            income_df = pd.DataFrame(net_income).reset_index()
            income_df.columns = ['年度', '淨利 (Net Income)']
            st.bar_chart(data=income_df, x='年度', y='淨利 (Net Income)')
        else:
            st.info("暫無歷史獲利趨勢數據。")

except Exception as e:
    st.error(f"數據讀取失敗: {e}")
