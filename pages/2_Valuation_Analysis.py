import streamlit as st
import yfinance as yf
import pandas as pd

# --- 1. 驗證檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📈 個股估值與獲利分析")

gsheet_id = st.secrets.get("GSHEET_ID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=1797698775"
    return pd.read_csv(url)['symbol'].unique()

try:
    symbols = load_symbols()
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    stock_options = [s for s in symbols if s not in bond_list]
    sel_stock = st.selectbox("選擇分析標的：", stock_options)
    
    with st.spinner('提取數據中...'):
        tk = yf.Ticker(sel_stock)
        info = tk.info
        
        # A. 估值概覽 (修正讀取邏輯)
        st.markdown(f"### 🔍 {sel_stock} 估值指標")
        c1, c2, c3 = st.columns(3)
        
        pe_t = info.get('trailingPE')
        pe_f = info.get('forwardPE')
        
        c1.metric("本益比 (Trailing P/E)", f"{pe_t:.2f}" if pe_t else "N/A")
        c2.metric("遠期本益比 (Forward P/E)", f"{pe_f:.2f}" if pe_f else "N/A")
        
        if pe_t and pe_f:
            pe_diff = ((pe_f - pe_t) / pe_t * 100)
            c3.metric("P/E 預期變化", f"{pe_diff:.1f}%")
        else:
            c3.metric("P/E 預期變化", "N/A")

        st.markdown("---")
        
        # B. EPS 分析 (GAAP vs Non-GAAP)
        st.markdown("### 💰 獲利能力分析 (EPS)")
        eps_data = {
            "指標": ["每股盈餘 (EPS Trailing)", "預估每股盈餘 (Forward EPS)"],
            "數值": [
                f"${info.get('trailingEps', 0):.2f}",
                f"${info.get('forwardEps', 0):.2f}"
            ],
            "說明": ["GAAP (標準會計)", "Non-GAAP (分析師調整後)"]
        }
        st.table(pd.DataFrame(eps_data))

        # C. 獲利趨勢 (修復 Net Income 錯誤)
        st.markdown("### 📊 近年獲利趨勢")
        try:
            # 優先嘗試抓取年度利潤，若失敗則顯示提示
            hist_earnings = tk.earnings_dates
            if hist_earnings is not None and not hist_earnings.empty:
                st.write("近期盈餘發布紀錄 (EPS Actual vs Estimate):")
                st.dataframe(hist_earnings.head(8))
            else:
                # 備案：顯示年度總收入趨勢
                financials = tk.financials
                if not financials.empty and 'Net Income' in financials.index:
                    net_inc = financials.loc['Net Income'].head(4)
                    st.bar_chart(net_inc)
                else:
                    st.info("該標的暫無詳細歷史獲利圖表數據。")
        except:
            st.info("無法獲取歷史趨勢圖，請參考上方 EPS 數據。")

except Exception as e:
    st.error(f"數據加載失敗: {e}")
