import streamlit as st
import pandas as pd
import requests
import io

# --- 1. 從 Secrets 讀取 ---
gsheet_id = st.secrets.get("GSHEET_ID")
portfolio_gid = st.secrets.get("PORTFOLIO_GID", "0") 

st.title("📊 全標的獲利與估值分析")

@st.cache_data(ttl=86400)
def load_data_from_gsheet():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # 只做基本的去空白處理
            df.columns = df.columns.str.strip()
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 2. 顯示邏輯 ---
df = load_data_from_gsheet()

if not df.empty:
    # 統一用大小寫一致的 'Symbol' (因為你 Google Sheet 改成 Symbol 了)
    exclude_list = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
    
    if 'Symbol' in df.columns:
        # 過濾債券
        df_display = df[~df['Symbol'].isin(exclude_list)].copy()

        # 顯示你想要的欄位
        target_cols = ['Symbol', 'Price', 'Trailing EPS', 'Trailing PE', 'Forward EPS', 'Forward PE']
        # 確保只顯示存在的欄位
        available_cols = [c for c in target_cols if c in df_display.columns]

        st.dataframe(
            df_display[available_cols].style.format({
                "Price": "{:.2f}", 
                "Trailing EPS": "{:.2f}", 
                "Trailing PE": "{:.2f}",
                "Forward EPS": "{:.2f}", 
                "Forward PE": "{:.2f}"
            }, na_rep="-").background_gradient(subset=['Forward PE'], cmap='RdYlGn_r'),
            use_container_width=True
        )
    else:
        st.error(f"找不到 'Symbol' 欄位。目前標題：{list(df.columns)}")

    if st.button("🔄 同步 Google Sheet 數據"):
        st.cache_data.clear()
        st.rerun()
