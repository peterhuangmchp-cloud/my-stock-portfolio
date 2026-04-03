import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time
from datetime import datetime

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="全球資產損益與配息分析", layout="wide", page_icon="💰")

# --- 2. 🔐 密碼保護功能 ---
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

# --- 3. 核心數據讀取 ---
st.title("📊 全球資產損益與配息看板")
gsheet_id = st.secrets.get("GSHEET_ID")

@st.cache_data(ttl=600) # 縮短快取時間，方便即時更新
def load_data(sheet_id):
    # 修正 gid 連結與空格問題
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
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
        return 32.5

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

# 顏色定義函數 (用於 map)
def color_roi_custom(val):
    if isinstance(val, (int, float)):
        return 'color: blue' if val > 0 else 'color: red'
    return ''

try:
    df = load_data(gsheet_id)
    
    # --- 4. 數據同步 (抗封鎖 + 強制對齊正規交易價) ---
    with st.spinner('正在同步全球行情數據 (已校準 AVGO 價格)...'):
        price_map, prev_close_map, div_map, h52_map, l52_map = {}, {}, {}, {}, {}
        history_list = []
        
        for index, row in df.iterrows():
            sym = row['symbol']
            tk = yf.Ticker(sym)
            
            # 使用 history 確保抓到正規收盤價 (解決 4.08% 誤差問題)
            h_data_short = tk.history(period="5d", auto_adjust=False, prepost=False)
            
            if len(h_data_short) >= 2:
                curr_p = h_data_short['Close'].iloc[-1]
                p_close = h_data_short['Close'].iloc[-2]
            else:
                curr_p = tk.fast_info['last_price']
                p_close = tk.fast_info['previous_close']

            price_map[index] = curr_p
            prev_close_map[index] = p_close
            h52_map[index] = tk.fast_info['year_high']
            l52_map[index] = tk.fast_info['year_low']
            
            # 歷史趨勢數據
            h_12m = tk.history(period="12mo", auto_adjust=False)['Close']
            h_12m.index = h_12m.index.tz_localize(None).normalize()
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
            
            # 股息數據
            try:
                divs = tk.dividends
                div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0.0
            except:
                div_map[sym] = 0.0
            
            time.sleep(0.05) # 抗封鎖微延遲

    # --- 5. 數據運算 ---
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        idx = row.name
        cp, pp = price_map.get(idx, 0), prev_close_map.get(idx, 0)
        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
        
        mv_twd = cp * row['shares'] * rate
        cost_twd = row['cost'] * row['shares'] * rate
        daily_chg = (cp - pp) * row['shares'] * rate
        daily_pct = ((cp - pp) / pp * 100) if pp > 0 else 0
        profit = mv_twd - cost_twd
        roi = (profit / cost_twd * 100) if cost_twd > 0 else 0
        
        div_ps = div_map.get(row['symbol'], 0)
        tax = 0.7 if row['currency'].upper() == "USD" and row['symbol'] not in bond_list else 1.0
        net_div = div_ps * row['shares'] * tax * rate
        
        return pd.Series([cp, pp, mv_twd, profit, roi, net_div, daily_chg, daily_pct, h52_map.get(idx, 0), l52_map.get(idx, 0)])

    df[['current_price', 'prev_close', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'daily_chg_twd', 'daily_pct', 'h52', 'l52']] = df.apply(process_row, axis=1)
    total_mv = df['mv_twd'].sum()

    # --- 6. 趨勢圖與月表 (修正 ME 與 map 報錯) ---
    history_combined = pd.concat(history_list, axis=1).interpolate().ffill().bfill()
    trend_data = history_combined.sum(axis=1).to_frame(name='Total_MV')
    trend_data.iloc[-1] = total_mv 
    
    # 【關鍵修正 1】'M' 改為 'ME'
    monthly_data = trend_data.resample('ME').last().sort_index(ascending=False)
    monthly_data['月變動 (TWD)'] = monthly_data['Total_MV'].diff(periods=-1)
    monthly_data['月變動 %'] = (monthly_data['月變動 (TWD)'] / monthly_data['Total_MV'].shift(-1) * 100)

    # --- A. 摘要指標 ---
    total_chg = df['daily_chg_twd'].sum()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("總資產市值 (TWD)", f"${total_mv:,.0f}")
    m2.metric("今日資產變動", f"${total_chg:,.0f}", f"{(total_chg/(total_mv-total_chg)*100):.2f}%")
    m3.metric("總累計損益", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/total_mv*100):.2f}%")
    m4.metric("預估年度稅後配息", f"${df['net_div_twd'].sum():,.0f}")
    m5.metric("美金匯率", f"{usd_to_twd:.2f}")

    # --- B. 12 個月趨勢圖 ---
    st.markdown("---")
    y_min, y_max = trend_data['Total_MV'].min() * 0.97, trend_data['Total_MV'].max() * 1.03
    fig_trend = px.area(trend_data, y='Total_MV', title="📈 總資產市值趨勢 (TWD)")
    fig_trend.update_layout(yaxis=dict(range=[y_min, y_max], tickformat=",.0f"))
    st.plotly_chart(fig_trend, use_container_width=True)

    # --- C. 總資產變化表 (關鍵修正 2：使用 .map) ---
    st.subheader("🗓️ 過去 12 個月總資產變化表")
    st.dataframe(monthly_data.style.format({
        'Total_MV': '{:,.0f}', '月變動 (TWD)': '{:,.0f}', '月變動 %': '{:.2f}%'
    }).map(color_roi_custom, subset=['月變動 (TWD)', '月變動 %']), use_container_width=True)

    # --- D. 詳細持倉清單 ---
    st.markdown("---")
    st.subheader("📝 完整持倉清單")
    st.dataframe(df[['name', 'symbol', 'current_price', 'prev_close', 'daily_pct', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}', 'prev_close': '{:.2f}', 'daily_pct': '{:.2f}%', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }).map(color_roi_custom, subset=['daily_pct', 'roi']), use_container_width=True)

    # --- E. 風險監控 ---
    st.markdown("---")
    st.subheader("📉 52 週高低點風險監控")
    risk_df = df[['name', 'symbol', 'current_price', 'h52']].copy()
    risk_df['較高點跌幅 %'] = ((risk_df['current_price'] - risk_df['h52']) / risk_df['h52'] * 100)
    st.dataframe(risk_df.style.format({'current_price': '{:.2f}', 'h52': '{:.2f}', '較高點跌幅 %': '{:.2f}%'})
                 .map(lambda x: 'color: red', subset=['較高點跌幅 %']), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
