import streamlit as st
import pandas as pd
import requests
import io

# --- 1. 從 Secrets 讀取設定 ---
gsheet_id = st.secrets.get("GSHEET_ID")
portfolio_gid = st.secrets.get("PORTFOLIO_GID", "0") 

st.title("📊 全標的獲利與估值分析")

# --- 2. 數據讀取邏輯 ---
# 注意：為了讓你增加股票能立刻顯示，我們將 ttl 縮短，或利用手動刷新按鈕
@st.cache_data(ttl=3600) # 設定為 1 小時快取，兼顧效能與更新頻率
def load_data_from_gsheet():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # 標準化標題列：去掉前後空格、轉為小寫
            df.columns = df.columns.str.strip().str.lower()
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# --- 3. 處理與過濾 ---
df_raw = load_data_from_gsheet()

if not df_raw.empty:
    # 1. 檢查必要的 'symbol' 欄位是否存在
    if 'symbol' in df_raw.columns:
        # 清理數據：移除 symbol 為空的列
        df = df_raw.dropna(subset=['symbol']).copy()
        
        # 2. 定義排除名單 (統一轉大寫對比)
        exclude_list = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
        df['symbol'] = df['symbol'].astype(str).str.strip().str.upper()
        
        # 3. 過濾掉不顯示的標的
        df_display = df[~df['symbol'].isin(exclude_list)].copy()

        st.markdown(f"### 📋 持倉標的快照 (目前共 {len(df_display)} 檔)")

        # 4. 定義顯示映射 (確保對齊你剛才在 Sheet 改好的標題)
        display_map = {
            'name': 'Name',
            'symbol': 'Symbol',
            'price': 'Price',
            'trailing eps': 'Trailing EPS',
            'trailing pe': 'Trailing PE',
            'forward eps': 'Forward EPS',
            'forward pe': 'Forward PE'
        }
        
        # 過濾出存在的欄位並重新命名
        available_cols = [c for c in display_map.keys() if c in df_display.columns]
        
        # 5. 渲染表格
        st.dataframe(
            df_display[available_cols].rename(columns=display_map).style.format({
                "Price": "{:.2f}", 
                "Trailing EPS": "{:.2f}", 
                "Trailing PE": "{:.2f}",
                "Forward EPS": "{:.2f}", 
                "Forward PE": "{:.2f}"
            }, na_rep="-").background_gradient(subset=['Forward PE'], cmap='RdYlGn_r'),
            use_container_width=True
        )
    else:
        st.error(f"找不到 'symbol' 欄位。目前抓到的標題為：{list(df_raw.columns)}")
else:
    st.info("等待 Google Sheet 數據載入中...")

# --- 4. 關鍵功能：手動強制更新按鈕 ---
# 當你在 Google Sheet 新增股票後，點擊這個按鈕會清除快取並重新抓取
if st.sidebar.button("🚀 重新從試算表同步股票"):
    st.cache_data.clear()
    st.rerun()
