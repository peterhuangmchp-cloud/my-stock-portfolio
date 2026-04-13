import streamlit as st
import pandas as pd
import requests
import io

# --- 1. 從 Secrets 讀取設定 ---
# 建議在 Streamlit Cloud Secrets 設定：
# GSHEET_ID = "你的試算表ID"
# PORTFOLIO_GID = "你的分頁ID"
gsheet_id = st.secrets.get("GSHEET_ID")
portfolio_gid = st.secrets.get("PORTFOLIO_GID", "0") 

# --- 2. 驗證與標題 ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("🔒 請先在主頁面輸入密碼解鎖。")
    st.stop()

st.set_page_config(page_title="估值分析", layout="wide")
st.title("📊 全標的獲利與估值分析")

# --- 3. 數據讀取邏輯 (帶快取機制) ---
@st.cache_data(ttl=3600)  # 快取 1 小時，兼顧效能與更新
def load_data_from_gsheet():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # 標準化標題列：去掉前後空格、轉為小寫，解決標題亂碼或括號問題
            df.columns = df.columns.str.strip().str.lower()
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"讀取 Google Sheet 失敗: {e}")
        return pd.DataFrame()

# --- 4. 執行與處理 ---
df_raw = load_data_from_gsheet()

if not df_raw.empty:
    # 檢查是否讀取到必要的 symbol 欄位 (模糊匹配，只要標題包含 symbol 即可)
    symbol_col = next((c for c in df_raw.columns if 'symbol' in c), None)
    
    if symbol_col:
        # 清理數據：移除 symbol 為空的列
        df = df_raw.dropna(subset=[symbol_col]).copy()
        
        # 定義排除名單 (統一轉大寫對比)
        exclude_list = ['TLT', 'SHV', 'SGOV', 'LQD', 'CASH', 'USDT']
        df[symbol_col] = df[symbol_col].astype(str).str.strip().str.upper()
        
        # 過濾標的
        df_display = df[~df[symbol_col].isin(exclude_list)].copy()

        st.markdown(f"#### 📋 目前監控中： {len(df_display)} 檔標的")

        # 定義顯示映射 (左邊是原始小寫標題關鍵字, 右邊是網頁美化名稱)
        # 這裡使用「包含」邏輯來對齊欄位
        display_map = {}
        target_keys = {
            'name': 'Name',
            'symbol': 'Symbol',
            'price': 'Price',
            'trailing eps': 'Trailing EPS',
            'trailing pe': 'Trailing PE',
            'forward eps': 'Forward EPS',
            'forward pe': 'Forward PE'
        }

        # 動態對齊 Google Sheet 的原始欄位
        for actual_col in df_display.columns:
            for key, pretty_name in target_keys.items():
                if key in actual_col:
                    display_map[actual_col] = pretty_name

        # 執行過濾與更名
        df_final = df_display[list(display_map.keys())].rename(columns=display_map)
        
        # --- 5. 樣式美化 ---
        # 找出哪些更名後的欄位需要格式化小數點
        format_cols = ["Price", "Trailing EPS", "Trailing PE", "Forward EPS", "Forward PE"]
        active_formats = {c: "{:.2f}" for c in format_cols if c in df_final.columns}
        
        styler = df_final.style.format(active_formats, na_rep="-")
        
        # 安全套用背景漸層 (綠色代表 PE 較低，估值較吸引人)
        if "Forward PE" in df_final.columns:
            styler = styler.background_gradient(subset=['Forward PE'], cmap='RdYlGn_r')
        
        # 輸出表格
        st.dataframe(styler, use_container_width=True)
        
    else:
        st.error(f"找不到 Symbol 欄位。目前抓到的標題為：{list(df_raw.columns)}")
        st.info("請檢查 Google Sheet 第一列是否包含 'Symbol' 字樣。")
else:
    st.info("尚未從 Google Sheet 取得數據，請確認試算表權限與 ID。")

# --- 6. 側邊欄：強制更新按鈕 ---
with st.sidebar:
    st.divider()
    if st.button("🚀 重新同步試算表數據"):
        st.cache_data.clear()
        st.rerun()
    st.caption("手動重新整理會清除快取，即時抓取 Google Sheet 最新變動。")
