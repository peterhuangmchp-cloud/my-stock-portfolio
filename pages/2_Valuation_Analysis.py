@st.cache_data(ttl=86400)
def load_data_from_gsheet():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={portfolio_gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            
            # --- 核心修正：強制清洗欄位名稱 ---
            # 去掉前後空白、全部轉小寫
            df.columns = df.columns.str.strip().str.lower()
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# --- 執行與顯示 ---
df = load_data_from_gsheet()

if not df.empty:
    # 這裡的 'symbol' 也要改成小寫
    exclude_list = ['tlt', 'shv', 'sgov', 'lqd', 'cash', 'usdt']
    
    # 使用標準化後的小寫 'symbol'
    # 這裡增加一個檢查，避免程式崩潰
    if 'symbol' in df.columns:
        # 強制將資料內容也轉小寫來比較，最保險
        df_analysis = df[~df['symbol'].str.strip().str.lower().isin(exclude_list)].copy()

        st.markdown(f"### 📋 持倉標的快照")
        
        # 顯示時可以再把標題改漂亮
        display_map = {
            'symbol': 'Symbol',
            'price': 'Price',
            'trailing eps': 'Trailing EPS',
            'trailing pe': 'Trailing PE',
            'forward eps': 'Forward EPS',
            'forward pe': 'Forward PE'
        }
        
        # 過濾出我們想看的欄位（對應你 Google Sheet 的標題，但需全小寫）
        target_cols = [c for c in display_map.keys() if c in df_analysis.columns]
        
        st.dataframe(
            df_analysis[target_cols].rename(columns=display_map).style.format({
                "Price": "{:.2f}", 
                "Trailing EPS": "{:.2f}", 
                "Trailing PE": "{:.2f}",
                "Forward EPS": "{:.2f}", 
                "Forward PE": "{:.2f}"
            }).background_gradient(subset=['Forward PE'], cmap='RdYlGn_r'),
            use_container_width=True
        )
    else:
        st.error(f"找不到 'symbol' 欄位。目前的欄位有：{list(df.columns)}")
