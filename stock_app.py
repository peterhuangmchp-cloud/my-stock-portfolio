import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests

# --- 1. 網頁基本設定 (不變) ---
st.set_page_config(page_title="全球資產損益與配息分析", layout="wide", page_icon="💰")

# --- 2. 🔐 密碼保護功能 (不變) ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if not st.session_state["authenticated"]:
        st.title("🔐 私人投資實驗室")
        pwd_input = st.text_input("請輸入密碼", type="password")
        if st.button("確認解鎖"):
            if pwd_input == st.secrets.get("APP_PASSWORD"):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤")
        st.stop()

check_password()

# --- 3. 核心數據讀取 (不變) ---
st.title("📊 全球資產損益與配息看板")
gsheet_id = st.secrets.get("GSHEET_ID")

def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=601349851"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    data = pd.read_csv(io.StringIO(response.text))
    data.columns = data.columns.str.strip().str.lower()
    return data

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return yf.Ticker("TWD=X").fast_info['last_price']
    except:
        return 31.91

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    # --- 4. 同步即時行情與近 5 日歷史 ---
    with st.spinner('正在診斷近 5 個交易日數據...'):
        price_map, prev_close_map, div_map, h52_map, l52_map = {}, {}, {}, {}, {}
        history_list = []
        
        for index, row in df.iterrows():
            sym = row['symbol']
            tk = yf.Ticker(sym)
            fast = tk.fast_info
            
            # 即時資料存入 map (依 index 存取避免重複 symbol 覆蓋)
            price_map[index] = fast['last_price']
            prev_close_map[index] = fast['previous_close']
            h52_map[index] = fast['year_high']
            l52_map[index] = fast['year_low']
            
            # 抓取近 5 日歷史
            h_data = tk.history(period="5d", auto_adjust=False)['Close']
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            
            # 建立唯一名稱：名稱 + 代號 + 序號，防止 Styler 報錯
            unique_name = f"{row['name']} ({sym}) #{index}"
            sym_history = (h_data * row['shares'] * rate).to_frame(name=unique_name)
            history_list.append(sym_history)
            
            divs = tk.dividends
            div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0.0

    # --- 5. 當前數據處理 ---
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        idx = row.name
        curr_price = price_map.get(idx, 0)
        prev_price = prev_close_map.get(idx, 0)
        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
        mv_twd = curr_price * row['shares'] * rate
        prev_mv_twd = prev_price * row['shares'] * rate
        cost_twd = row['cost'] * row['shares'] * rate
        daily_change = mv_twd - prev_mv_twd
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        div_per_share = div_map.get(row['symbol'], 0)
        tax_rate = 0.7 if row['currency'].upper() == "USD" and row['symbol'] not in bond_list else 1.0
        net_div_twd = div_per_share * row['shares'] * tax_rate * rate
        return pd.Series([curr_price, mv_twd, profit_twd, roi, net_div_twd, daily_change])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'daily_change_twd']] = df.apply(process_row, axis=1)
    total_mv = df['mv_twd'].sum()

    # --- 6. 近 5 日資產明細表邏輯 (修正 Index 衝突) ---
    five_day_df = pd.concat(history_list, axis=1).T
    five_day_df.columns = [d.strftime('%m/%d') for d in five_day_df.columns]
    
    # 計算總計列
    summary_row = five_day_df.sum().to_frame(name='Σ 總資產市值 (TWD)').T
    five_day_df = pd.concat([five_day_df, summary_row])

    # --- A. 摘要儀表板 (維持原格式) ---
    total_daily_change = df['daily_change_twd'].sum()
    daily_pct = (total_daily_change / (total_mv - total_daily_change) * 100) if (total_mv - total_daily_change) != 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總資產市值 (TWD)", f"${total_mv:,.0f}")
    m2.metric("今日資產變動", f"${total_daily_change:,.0f}", f"{daily_pct:.2f}%")
    m3.metric("總累計損益 (TWD)", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/total_mv*100):.2f}%")
    m4.metric("年度預估稅後配息", f"${df['net_div_twd'].sum():,.0f}")

    # --- B. 近 5 個交易日明細表 ---
    st.markdown("---")
    st.subheader("🗓️ 近 5 個交易日：單一資產市值變化 (TWD)")
    st.info("請檢查下方表格。若 Σ 總資產在某天突然少了 700 萬，請查看該欄位中哪檔股票變成了 0 或異常小。")
    
    # 這裡移除 style.map 以避免 index 衝突，先確保資料能顯示
    st.dataframe(five_day_df.style.format("{:,.0f}"), use_container_width=True)

    # --- C, D, E 維持原樣 (配置、清單、監控) ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    st.markdown("---")
    st.subheader("📝 完整持倉清單")
    # 清單部分的顏色邏輯維持
    st.dataframe(df[['name', 'symbol', 'shares', 'current_price', 'daily_change_twd', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}', 'daily_change_twd': '{:,.0f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }), use_container_width=True)

    st.markdown("---")
    k1, k2 = st.columns([1, 1.2])
    with k1:
        st.subheader("💰 年度個股配息統計 (NTD)")
        st.dataframe(df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'net_div_twd']].sort_values('net_div_twd', ascending=False).style.format({'net_div_twd': '{:,.0f}'}), use_container_width=True)
    with k2:
        st.subheader("📈 52 週高低點風險監控")
        risk_df = df[['name', 'symbol', 'current_price', 'h52', 'l52']].copy()
        risk_df['較高點跌幅 %'] = ((risk_df['current_price'] - risk_df['h52']) / risk_df['h52'] * 100)
        st.dataframe(risk_df.style.format({
            'current_price': '{:.2f}', 'h52': '{:.2f}', 'l52': '{:.2f}', '較高點跌幅 %': '{:.2f}%'
        }), use_container_width=True)

except Exception as e:
    st.error(f"系統錯誤: {e}")
