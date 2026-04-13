import streamlit as st
import pandas as pd
import requests
import io

# --- 1. 從 Secrets 取得設定 ---
# 確保你的 secrets.toml 裡有 GSHEET_ID 和 PORTFOLIO_GID
gsheet_id = st.secrets["GSHEET_ID"]
portfolio_gid = st.secrets["PORTFOLIO_GID"]  # 這是 Portfolio 分頁的 GID

st.title("📊 全標的獲利與估值分析")

# --- 2. 核心邏輯：從 Google Sheet 讀取已存好的數據 ---
@st.cache_data(ttl=86400)  # 👈 重要：設定 TTL 為 86400 秒 (24小時)，達成一天只抓一次
def load_data_from_gsheet():
    # 這是 Google Sheet 匯出為 CSV 的固定格式
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    
    try:
        # 使用 headers 模擬瀏覽器，避免被 Google 阻擋
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # 清理欄位多餘空白
            df.columns = df.columns.str.strip()
            return df
        else:
            st.error(f"無法讀取試算表，狀態碼：{response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"讀取過程發生錯誤: {e}")
        return pd.DataFrame()

# --- 3. 執行與顯示 ---
df = load_data_from_gsheet()

if not df.empty:
    # 排除不需要分析的標的（債券、現金等）
    exclude_list = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
    # 假設你的代號欄位標題是 "Symbol"
    df_analysis = df[~df['Symbol'].isin(exclude_list)].copy()

    st.markdown(f"### 📋 持倉標的快照 (數據源：Google Sheet)")
    
    # 定義要顯示的欄位 (請對應你截圖中的標題)
    display_cols = ['Symbol', 'Price', 'Trailing EPS', 'Trailing PE', 'Forward EPS', 'Forward PE']
    
    # 確保只選擇存在的欄位
    available_cols = [c for c in display_cols if c in df_analysis.columns]
    
    # 顯示表格並美化
    st.dataframe(
        df_analysis[available_cols].style.format({
            "Price": "{:.2f}", 
            "Trailing EPS": "{:.2f}", 
            "Trailing PE": "{:.2f}",
            "Forward EPS": "{:.2f}", 
            "Forward PE": "{:.2f}"
        }).background_gradient(subset=['Forward PE'], cmap='RdYlGn_r'),
        use_container_width=True
    )

    # 提供一個強制刷新的按鈕（以防萬一你在 Google Sheet 改了資料想立刻看到）
    if st.button("🔄 立即從試算表同步新數據"):
        st.cache_data.clear()
        st.rerun()

else:
    st.info("目前無可用數據，請檢查 Google Sheet 權限設定。")
