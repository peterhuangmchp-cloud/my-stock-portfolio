import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io

# --- 1. 驗證與設定 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.title("📊 個股獲利與估值深度分析")

# --- 2. 數據讀取 (同步主分頁) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

def load_symbols():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            df.columns = df.columns.str.strip().str.lower()
            return [str(s).strip() for s in df['symbol'].dropna().unique()]
        return []
    except:
        return []

# --- 3. 執行分析 ---
symbols = load_symbols()
if symbols:
    sel_stock = st.selectbox("選擇要分析的標的：", symbols)
    
    if sel_stock:
        with st.spinner(f'正在分析 {sel_stock} ...'):
            tick = yf.Ticker(sel_stock)
            info = tick.info
            
            # --- A. 您要求的核心估值數據 (Current Price, EPS, P/E, Forward EPS, Forward P/E) ---
            st.markdown("### 💎 核心獲利與估值指標")
            
            # 數值準備
            curr_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            t_eps = info.get('trailingEps', 0)
            t_pe = info.get('trailingPE', 0)
            f_eps = info.get('forwardEps', 0)
            f_pe = info.get('forwardPE', 0)
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Current Price", f"{curr_price:.2f}")
            m2.metric("EPS (Trailing)", f"{t_eps:.2f}")
            m3.metric("Current P/E", f"{t_pe:.2f}" if t_pe else "N/A")
            m4.metric("Forward EPS", f"{f_eps:.2f}")
            m5.metric("Forward P/E", f"{f_pe:.2f}" if f_pe else "N/A")
            
            st.markdown("---")
            
            # --- B. 原本的深度分析內容 ---
            st.markdown("### 📈 營收與獲利能力")
            d1, d2, d3 = st.columns(3)
            
            # 營收成長、利潤率、PEG
            rev_growth = info.get('revenueGrowth', 0) * 100
            profit_margin = info.get('profitMargins', 0) * 100
            peg_ratio = info.get('pegRatio', 'N/A')
            
            d1.metric("營收成長 (YoY)", f"{rev_growth:.2f}%")
            d2.metric("淨利率 (Margin)", f"{profit_margin:.2f}%")
            d3.metric("PEG Ratio", f"{peg_ratio}")
            
            # 更多細節與說明
            with st.expander("🔍 查看更多財務細節"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**市值 (Market Cap):** {info.get('marketCap', 0):,}")
                    st.write(f"**52週最高:** {info.get('fiftyTwoWeekHigh')}")
                    st.write(f"**52週最低:** {info.get('fiftyTwoWeekLow')}")
                with c2:
                    st.write(f"**股息收益率:** {info.get('dividendYield', 0)*100:.2f}%")
                    st.write(f"**持股比例 (法人):** {info.get('heldPercentInstitutions', 0)*100:.2f}%")
                    st.write(f"**分析師建議:** {info.get('recommendationKey', 'N/A').upper()}")
            
            # 數據邏輯說明
            st.info("💡 **Forward EPS 說明**：此數值為 Yahoo Finance 彙整之分析師預估平均值，反映市場對未來 12 個月的獲利期待。")
else:
    st.error("無法載入持倉代號，請確認試算表連接正常。")
