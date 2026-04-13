import streamlit as st
import pandas as pd
import requests
import io

# --- 1. 從 Secrets 讀取設定 ---
gsheet_id = st.secrets.get("GSHEET_ID")
portfolio_gid = st.secrets.get("PORTFOLIO_GID", "0") 

st.title("📊 全標的獲利與估值分析")

# --- 2. 數據讀取邏輯 ---
@st.cache_data(ttl=86400)
def load_data_from_gsheet():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # 重要：將欄位名稱標準化（去空白、轉小寫）
            df.columns = df.columns.str.strip().str.lower()
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# --- 3. 顯示與過濾 ---
df = load_data_from_gsheet()

if not df.empty:
    # 定義排除清單 (統一小寫)
    exclude_list = ['tlt', 'shv', 'sgov', 'lqd', 'cash', 'usdt']
    
    # 檢查是否讀取到 symbol 欄位
    if 'symbol' in df.columns:
        # 過濾標的
        df_analysis = df[~df['symbol'].str.strip().str.lower().isin(exclude_list)].copy()

        st.markdown(f"### 📋 持倉標的快照 (數據源：Google Sheet)")
        
        # 定義顯示映射 (左邊是 Google Sheet 小寫標題, 右邊是網頁顯示名稱)
        display_map = {
            'symbol': 'Symbol',
            'price': 'Price',
            'trailing eps': 'Trailing EPS',
            'trailing pe': 'Trailing PE',
            'forward eps': 'Forward EPS',
            'forward pe': 'Forward PE'
        }
        
        # 只選取存在的欄位
        target_cols = [c for c in display_map.keys() if c in df_analysis.columns]
        
        # 美化顯示
        st.dataframe(
            df_analysis[target_cols].rename(columns=display_map).style.format({
                "Price": "{:.2f}", 
                "Trailing EPS": "{:.2f}", 
                "Trailing PE": "{:.2f}",
                "Forward EPS": "{:.2f}", 
                "Forward PE": "{:.2f}"
            }, na_rep="-").background_gradient(subset=['Forward PE'], cmap='RdYlGn_r'),
            use_container_width=True
        )
    else:
        st.error(f"找不到 'symbol' 欄位。目前抓到的標題為：{list(df.columns)}")
        st.info("請檢查 Google Sheet 的 Portfolio 分頁第一列是否包含 'Symbol'。")

    if st.button("🔄 立即同步 Google Sheet 新數據"):
        st.cache_data.clear()
        st.rerun()
else:
    st.warning("無法取得資料，請檢查 Secrets 中的 GSHEET_ID 與 PORTFOLIO_GID 設定。")
