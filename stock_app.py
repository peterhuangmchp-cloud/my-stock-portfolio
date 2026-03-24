import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests

# --- 1. 網頁基本設定 (原始版) ---
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
        return 32.5

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

def color_roi_custom(val):
    if isinstance(val, (int, float)):
        return 'color: blue' if val > 0 else 'color: red'
    return ''

try:
    df = load_data(gsheet_id)
    
    # --- 4. 數據同步 (12 個月歷史 & 精確校正今日報價) ---
    with st.spinner('正在同步精確行情與 12 個月歷史數據...'):
        price_map, prev_close_map, div_map, h52_map, l52_map = {}, {}, {}, {}, {}
        history_list = []
        
        for index, row in df.iterrows():
            sym = row['symbol']
            tk = yf.Ticker(sym)
            
            # 使用 auto_adjust=False 確保收盤價與市場報價一致
            h_data_full = tk.history(period="12mo", auto_adjust=False)
            h_data = h_data_full['Close']
            
            # 【關鍵校正】: 取得最後兩天的數據來計算漲跌
            if len(h_data_full) >= 2:
                # 確保取到的是最新收盤與前一交易日收盤
                current_p = h_data_full['Close'].iloc[-1]
                prev_p = h_data_full['Close'].iloc[-2]
            else:
                current_p = tk.fast_info['last_price']
                prev_p = tk.fast_info['previous_close']

            price_map[index] = current_p
            prev_close_map[index] = prev_p
            h52_map[index] = tk.fast_info['year_high']
            l52_map[index] = tk.fast_info['year_low']
            
            h_data.index = h_data.index.tz_localize(None).normalize()
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            sym_history = (h_data * row['shares'] * rate).to_frame(name=sym)
            history_list.append(sym_history)
            
            divs = tk.dividends
            div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0.0

    # --- 5. 數據運算 ---
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
        # 計算出您截圖中的 4.08%
        daily_pct = (curr_price - prev_price) / prev_price * 100 if prev_price > 0 else 0
        
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        
        div_per_share = div_map.get(row['symbol'], 0)
        tax_rate = 0.7 if row['currency'].upper() == "USD" and row['symbol'] not in bond_list else 1.0
        net_div_twd = div_per_share * row['shares'] * tax_rate * rate
        yield_rate = (div_per_share / curr_price * 100) if curr_price > 0 else 0
        
        return pd.Series([curr_price, mv_twd, profit_twd, roi, net_div_twd, yield_rate, daily_change, daily_pct, h52_map.get(idx, 0), l52_map.get(idx, 0)])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'yield_rate', 'daily_change_twd', 'daily_pct', 'h52', 'l52']] = df.apply(process_row, axis=1)
    total_mv = df['mv_twd'].sum()

    # --- 6. 趨勢圖與月表 ---
    history_combined = pd.concat(history_list, axis=1).interpolate(method='linear').ffill().bfill()
    trend_data = history_combined.sum(axis=1).to_frame(name='Total_MV')
    trend_data.iloc[-1] = total_mv 
    monthly_data = trend_data.resample('M').last().sort_index(ascending=False)
    monthly_data['月變動 (TWD)'] = monthly_data['Total_MV'].diff(periods=-1)
    monthly_data['月變動 %'] = (monthly_data['月變動 (TWD)'] / monthly_data['Total_MV'].shift(-1) * 100)

    # --- A. 摘要指標 ---
    total_daily_change = df['daily_change_twd'].sum()
    total_daily_pct = (total_daily_change / (total_mv - total_daily_change) * 100) if (total_mv - total_daily_change) != 0 else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("總資產市值 (TWD)", f"${total_mv:,.0f}")
    m2.metric("今日資產變動", f"${total_daily_change:,.0f}", f"{total_daily_pct:.2f}%")
    m3.metric("總累計損益 (TWD)", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/total_mv*100):.2f}%")
    m4.metric("年度預估稅後配息", f"${df['net_div_twd'].sum():,.0f}")
    m5.metric("當前匯率", f"{usd_to_twd:.2f}")

    # --- B. 12 個月趨勢圖 ---
    st.markdown("---")
    st.subheader("📈 過去 12 個月總資產趨勢 (動態 Y 軸)")
    y_min, y_max = trend_data['Total_MV'].min() * 0.97, trend_data['Total_MV'].max() * 1.03
    fig_trend = px.area(trend_data, x=trend_data.index, y='Total_MV')
    fig_trend.update_layout(hovermode="x unified", template="plotly_white", height=400, yaxis=dict(tickformat=",.0f", range=[y_min, y_max]))
    st.plotly_chart(fig_trend, use_container_width=True)

    st.subheader("🗓️ 過去 12 個月總資產變化表")
    st.dataframe(monthly_data.style.format({
        'Total_MV': '{:,.0f}', '月變動 (TWD)': '{:,.0f}', '月變動 %': '{:.2f}%'
    }).applymap(color_roi_custom, subset=['月變動 (TWD)', '月變動 %']), use_container_width=True)

    # --- C. 圖表區 ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    # --- D. 完整持倉清單 ---
    st.markdown("---")
    st.subheader("📝 完整持倉清單")
    st.dataframe(df[['name', 'symbol', 'shares', 'current_price', 'daily_change_twd', 'daily_pct', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}', 'daily_change_twd': '{:,.0f}', 'daily_pct': '{:.2f}%', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }).applymap(color_roi_custom, subset=['roi', 'daily_change_twd', 'daily_pct']), use_container_width=True)

    # --- E. 底部統計區 (垂直一上一下) ---
    st.markdown("---")
    st.subheader("💰 年度個股配息統計 (NTD)")
    st.dataframe(df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'yield_rate', 'net_div_twd']].sort_values('net_div_twd', ascending=False).style.format({'yield_rate': '{:.2f}%', 'net_div_twd': '{:,.0f}'}), use_container_width=True)
    
    st.markdown("---")
    st.subheader("📉 52 週高低點風險監控")
    risk_df = df[['name', 'symbol', 'current_price', 'h52', 'l52']].copy()
    risk_df['較高點跌幅 %'] = ((risk_df['current_price'] - risk_df['h52']) / risk_df['h52'] * 100)
    st.dataframe(risk_df.style.format({
        'current_price': '{:.2f}', 'h52': '{:.2f}', 'l52': '{:.2f}', '較高點跌幅 %': '{:.2f}%'
    }).applymap(lambda x: 'color: red', subset=['較高點跌幅 %']), use_container_width=True)

except Exception as e:
    st.error(f"系統錯誤: {e}")
