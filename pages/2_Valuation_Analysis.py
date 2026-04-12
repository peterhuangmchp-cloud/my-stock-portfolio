import streamlit as st
import pandas as pd
import requests
import io
import yfinance as yf

# --- 1. 驗證檢查 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📊 個股獲利與估值深度分析")

# --- 2. 數據讀取 (同步主程式 GID) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

def load_symbols_from_main():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            # 取得代號清單
            symbols = df['symbol'].dropna().unique()
            return [str(s).strip() for s in symbols]
        else:
            st.error(f"數據讀取失敗，狀態碼: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"連線錯誤: {e}")
        return []

# --- 3. 執行分析 ---
try:
    available_symbols = load_symbols_from_main()
    
    if available_symbols:
        sel_stock = st.selectbox("選擇要分析的標的：", available_symbols)
        
        with st.spinner(f'正在獲取 {sel_stock} 財務數據...'):
            stock = yf.Ticker(sel_stock)
            info = stock.info
            
            # --- 顯示估值指標 ---
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            
            # 獲利指標
            pe_ratio = info.get('trailingPE', 'N/A')
            forward_pe = info.get('forwardPE', 'N/A')
            peg_ratio = info.get('pegRatio', 'N/A')
            
            c1.metric("本益比 (Trailing PE)", f"{pe_ratio}")
            c2.metric("預估本益比 (Forward PE)", f"{forward_pe}")
            c3.metric("PEG 比例", f"{peg_ratio}")
            
            # 營收指標
            st.markdown("### 📈 營收與獲利成長")
            d1, d2 = st.columns(2)
            rev_growth = info.get('revenueGrowth', 0) * 100
            profit_margin = info.get('profitMargins', 0) * 100
            
            d1.metric("營收成長率 (YoY)", f"{rev_growth:.2f}%")
            d2.metric("利潤率 (Profit Margin)", f"{profit_margin:.2f}%")
            
            # 更多詳情
            with st.expander("🔍 更多財務細節"):
                st.write(f"**市值:** {info.get('marketCap', 'N/A'):,}")
                st.write(f"**52週最高/最低:** {info.get('fiftyTwoWeekHigh')} / {info.get('fiftyTwoWeekLow')}")
                st.write(f"**股息收益率:** {info.get('dividendYield', 0)*100:.2f}%")
    else:
        st.info("💡 請確認持倉分頁中已有標的代號。")

except Exception as e:
    st.error(f"估值分析失敗: {e}")
