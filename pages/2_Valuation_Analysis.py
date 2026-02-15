import streamlit as st
import yfinance as yf
import pandas as pd

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先解鎖。")
    st.stop()

st.title("📈 個股獲利能力分析")

try:
    gsheet_id = st.secrets.get("GSHEET_ID")
    symbols = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid=1797698775")['symbol'].unique()
    sel_stock = st.selectbox("選擇分析標的：", [s for s in symbols if s not in ['TLT', 'SHV', 'SGOV', 'LQD']])
    
    tk = yf.Ticker(sel_stock)
    info = tk.info
    
    # 指標顯示 (GAAP vs Non-GAAP)
    st.markdown(f"### 🔍 {sel_stock} 關鍵指標")
    c1, c2, c3 = st.columns(3)
    c1.metric("P/E (Trailing)", f"{info.get('trailingPE', 0):.2f}")
    c2.metric("Forward P/E", f"{info.get('forwardPE', 0):.2f}")
    c3.metric("EPS (Trailing)", f"${info.get('trailingEps', 0):.2f}")

    st.markdown("---")
    st.subheader("💰 盈餘預估表")
    eps_table = pd.DataFrame({
        "指標": ["GAAP EPS (實績)", "Non-GAAP EPS (預估)"],
        "數值": [f"${info.get('trailingEps', 0):.2f}", f"${info.get('forwardEps', 0):.2f}"]
    })
    st.table(eps_table)

except Exception as e:
    st.error(f"數據讀取異常: {e}")
