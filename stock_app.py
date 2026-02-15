import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# 1. 基本設定
st.set_page_config(page_title="資產管理主頁", layout="wide", page_icon="💰")
st.title("📊 全球資產損益與現金流儀表板")

# 2. 安全讀取 Secrets (圖 3 設定值)
if "GSHEET_ID" in st.secrets:
    gsheet_id = st.secrets["GSHEET_ID"]
else:
    gsheet_id = st.sidebar.text_input("請輸入 Google Sheet ID")

if not gsheet_id:
    st.info("👈 請於側邊欄設定 ID 或於 Secrets 中填寫。")
    st.stop()

st.session_state['gsheet_id'] = gsheet_id # 傳遞給分頁

# 3. 核心函數與匯率
def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    data = pd.read_csv(url)
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

try:
    df = load_data(gsheet_id)
    with st.spinner('同步即時行情中...'):
        price_map, div_map = {}, {}
        for sym in df['symbol'].unique():
            tk = yf.Ticker(sym)
            price_map[sym] = tk.fast_info['last_price']
            divs = tk.dividends
            div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0

    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        curr_p = price_map.get(row['symbol'], 0)
        curr_conv = (usd_to_twd if row['currency'] == "USD" else 1)
        mv_twd = curr_p * row['shares'] * curr_conv
        cost_twd = row['cost'] * row['shares'] * curr_conv
        profit_twd = mv_twd - cost_twd
        roi = (profit_twd / cost_twd * 100) if cost_twd > 0 else 0
        div_raw = div_map.get(row['symbol'], 0) * row['shares']
        tax = 0.7 if (row['currency'] == "USD" and row['symbol'] not in bond_list) else 1.0
        net_div = div_raw * tax * curr_conv
        y_rate = (div_map.get(row['symbol'], 0) / curr_p * 100) if curr_p > 0 else 0
        return pd.Series([curr_p, mv_twd, profit_twd, roi, net_div, y_rate])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'yield_rate']] = df.apply(process_row, axis=1)

    # --- 顯示原本所有資訊 ---
    m1, m2, m3 = st.columns(3)
    m1.metric("總資產市值 (TWD)", f"${df['mv_twd'].sum():,.0f}")
    m2.metric("總累計損益 (TWD)", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/df['mv_twd'].sum()*100):.2f}%")
    m3.metric("年度預估稅後配息 (TWD)", f"${df['net_div_twd'].sum():,.0f}")

    st.markdown("---")
    st.subheader("💰 年度個股配息統計")
    div_df = df[df['net_div_twd'] > 0][['name', 'symbol', 'shares', 'yield_rate', 'net_div_twd']].copy()
    st.dataframe(div_df.sort_values('net_div_twd', ascending=False).style.format({'yield_rate': '{:.2f}%', 'net_div_twd': '{:,.0f}'}), use_container_width=True)
    st.download_button("📥 匯出配息統計", div_df.to_csv(index=False).encode('utf-8-sig'), "dividend.csv", "text/csv")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📌 資產配置比例")
        st.plotly_chart(px.pie(df, values='mv_twd', names='name', hole=0.3), use_container_width=True)
    with c2:
        st.subheader("📈 個股損益排行")
        st.plotly_chart(px.bar(df.sort_values('profit_twd'), x='profit_twd', y='name', orientation='h', color='profit_twd', color_continuous_scale='RdYlGn'), use_container_width=True)

    st.subheader("📝 完整持倉清單")
    detail_df = df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd', 'roi']]
    st.dataframe(detail_df.style.format({'current_price': '{:.2f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%'}), use_container_width=True)
    st.download_button("📥 匯出持倉明細", detail_df.to_csv(index=False).encode('utf-8-sig'), "portfolio.csv", "text/csv")

except Exception as e:
    st.error(f"錯誤: {e}")
