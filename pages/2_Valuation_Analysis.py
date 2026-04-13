import streamlit as st
import pandas as pd
import requests
import io

# --- 1. 驗證 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先解鎖。")
    st.stop()

st.title("📊 全標的獲利與估值分析")

# --- 2. 數據讀取 (優化為直接讀取你設定好的 Portfolio 分頁) ---
gsheet_id = st.secrets.get("GSHEET_ID")
# 確保這個 GID 是你 "Portfolio" 分頁的 GID (在網址列 gid= 後面的數字)
portfolio_gid = "你的Portfolio分頁GID" 

@st.cache_data(ttl=86400) # 👈 設定為 86400 秒 (即 24 小時更新一次)
def load_valuation_from_sheet():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # 確保欄位名稱正確 (根據你的截圖)
            df.columns = [
                'Name', 'Symbol', 'Price', 'Trailing_EPS', 
                'Trailing_PE', 'Forward_EPS', 'Forward_PE'
            ]
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"讀取失敗: {e}")
        return pd.DataFrame()

# --- 3. 顯示邏輯 ---
df = load_valuation_from_sheet()

if not df.empty:
    # 移除標題列
    df = df.dropna(subset=['Symbol'])
    
    # 過濾掉債券類 (根據你的清單)
    exclude = ['TLT', 'SHV', 'SGOV', 'LQD']
    df_display = df[~df['Symbol'].isin(exclude)].copy()

    st.markdown(f"### 📋 核心持倉估值表 (最後同步時間: {pd.Timestamp.now().strftime('%Y-%m-%d')})")
    
    # 格式化並顯示
    st.dataframe(
        df_display.style.format({
            "Price": "{:.2f}", 
            "Trailing_EPS": "{:.2f}",
            "Trailing_PE": "{:.2f}", 
            "Forward_EPS": "{:.2f}", 
            "Forward_PE": "{:.2f}"
        }).background_gradient(subset=['Forward_PE'], cmap='RdYlGn_r'),
        use_container_width=True
    )
    
    # 強制重新整理按鈕
    if st.button("🚀 強制從 Google Sheet 重新抓取"):
        st.cache_data.clear()
        st.rerun()
else:
    st.info("尚未讀取到數據，請確認 Google Sheet 分頁設定。")
