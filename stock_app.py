import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests

# --- 1. 網頁基本設定 (維持不變) ---
st.set_page_config(page_title="全球資產損益與配息分析", layout="wide", page_icon="💰")

# --- 2. 🔐 密碼保護功能 (維持不變) ---
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
    data.columns = data.columns.str.strip()
    return data

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return yf.Ticker("TWD=X").fast_info['last_price']
    except:
        return 32.5

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

# --- 🎨 顏色邏輯修正：>0 藍色, <=0 紅色 ---
def color_roi_custom(val):
    if val > 0:
        return 'color: blue'
    else:
        return 'color: red'

try:
    df = load_data(gsheet_id)
    unique_symbols = df['symbol'].unique()
    
    with st.spinner('同步即時行情與 52 週數據中...'):
        price_map, div_map, h52_map, l52_map = {}, {}, {}, {}
        for sym in unique_symbols:
            tk = yf.Ticker(sym)
            info = tk.fast_info
            price_map[sym] = info['last_price']
            h52_map[sym] = info['year_high']
            l52_map[sym] = info['year_low']
            divs = tk.dividends
            div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0.0

    # 運算邏輯 (完全保留原本 Feature 與公式)
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        curr_price = price_map.get(row['symbol'], 0)
        h52 = h52_map.get(row['symbol'], 0)
        mv_twd = curr_price * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        cost_twd = row['cost'] * row['shares'] * (usd_to_twd if row['currency'] == "USD" else 1)
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        
        div_per_share = div_map.get(row['symbol'], 0)
        total_div_raw = div_per_share * row['shares']
        if row['currency'] == "USD":
            tax_rate = 0.7 if row['symbol'] not in bond_list else 1.0
            net_div_twd = total_div_raw * tax_rate * usd_to_twd
        else:
            net_div_twd = total_div_raw
        
        yield_rate = (div_per_share / curr_price * 100) if curr_price > 0 else 0
        drop_from_high = ((curr_price - h52) / h52 * 100) if h52 > 0 else 0
        
        return pd.Series([curr_price, mv_twd, profit_twd, roi, net_div_twd, yield_rate, h52, l52_map.get(row['symbol'], 0), drop_from_high])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'yield_rate', 'h52', 'l52', 'drop_from_high']] = df.apply(process_row, axis=1)

    # A. 摘要區
    m1, m2, m3 = st.columns(3)
    m1.metric("總資產市值 (TWD)", f"${df['mv_twd'].sum():,.0f}")
    m2.metric("總累計損益 (TWD)", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/df['mv_twd'].sum()*100):.2f}%")
    m3.metric("年度預估稅後配息 (TWD)", f"${df['net_div_twd'].sum():,.0f}")

    # B. 配息表
    st.markdown("---")
    st.subheader("💰 年度個股配息統計 (NTD)")
    st.dataframe(df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'yield_rate', 'net_div_twd']].sort_values('net_div_twd', ascending=False).style.format({'yield_rate': '{:.2f}%', 'net_div_twd': '{:,.0f}'}), use_container_width=True)

    # C. 持倉圖表
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行 (TWD)")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    # D. 原始持倉清單 (ROI >0 藍色, <=0 紅色)
    st.subheader("📝 完整持倉清單")
    st.dataframe(df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']].style.format({
        'current_price': '{:.2f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'
    }).applymap(color_roi_custom, subset=['roi']), use_container_width=True)

    # E. 52 週高低點監控表 (跌幅固定紅色)
    st.markdown("---")
    st.subheader("📉 52 週高低點風險監控 (USD/Local)")
    risk_df = df[['name', 'symbol', 'current_price', 'h52', 'l52', 'drop_from_high']].copy()
    risk_df.columns = ['名稱', '代號', '目前現價', '52週最高', '52週最低', '較高點跌幅 %']
    st.dataframe(risk_df.style.format({
        '目前現價': '{:.2f}', '52週最高': '{:.2f}', '52週最低': '{:.2f}', '較高點跌幅 %': '{:.2f}%'
    }).applymap(lambda x: 'color: red', subset=['較高點跌幅 %']), use_container_width=True)

except Exception as e:
    st.error(f"系統錯誤: {e}")

