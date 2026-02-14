import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# 設定網頁標題
st.set_page_config(page_title="我的個人投資組合", layout="wide")
st.title("📈 全球資產損益管理儀表板")

# 1. 獲取即時匯率 (美金對台幣)
@st.cache_data(ttl=3600)
def get_exchange_rate():
    ticker = yf.Ticker("TWD=X") # 或是 "USDTWD=X"
    data = ticker.history(period="1d")
    return data['Close'].iloc[-1]

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"${usd_to_twd:.2f}")

# 2. 模擬你的投資組合 (你可以之後改成讀取 Excel 或資料庫)
# 注意：台股代號請加上 .TW (例如 2330.TW)
my_stocks = [
    {"name": "台積電", "symbol": "2330.TW", "shares": 500, "cost": 600, "currency": "TWD"},
    {"name": "Apple", "symbol": "AAPL", "shares": 10, "cost": 150, "currency": "USD"},
    {"name": "Nvidia", "symbol": "NVDA", "shares": 5, "cost": 400, "currency": "USD"},
    {"name": "鴻海", "symbol": "2317.TW", "shares": 1000, "cost": 105, "currency": "TWD"},
]

# 3. 抓取數據並計算
df = pd.DataFrame(my_stocks)

def get_current_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # 抓取最新一筆收盤價
        return ticker.fast_info['last_price']
    except:
        return 0

with st.spinner('正在更新全球即時股價...'):
    df['current_price'] = df['symbol'].apply(get_current_price)

# 計算損益
def calculate_metrics(row):
    # 原始幣別市值
    market_value_orig = row['current_price'] * row['shares']
    # 換算為台幣市值
    if row['currency'] == "USD":
        market_value_twd = market_value_orig * usd_to_twd
        cost_twd = row['cost'] * row['shares'] * usd_to_twd # 簡化計算，未計入買入時匯率
    else:
        market_value_twd = market_value_orig
        cost_twd = row['cost'] * row['shares']
    
    profit_twd = market_value_twd - cost_twd
    return pd.Series([market_value_twd, profit_twd])

df[['market_value_twd', 'profit_twd']] = df.apply(calculate_metrics, axis=1)

# --- 網頁顯示部分 ---

# 上方總覽卡片
total_value = df['market_value_twd'].sum()
total_profit = df['profit_twd'].sum()
profit_rate = (total_profit / (total_value - total_profit)) * 100

col1, col2, col3 = st.columns(3)
col1.metric("總資產 (TWD)", f"${total_value:,.0f}")
col2.metric("總損益 (TWD)", f"${total_profit:,.0f}", f"{profit_rate:.2f}%")
col3.metric("美金匯率", f"{usd_to_twd:.2f}")

# 圖表展示
st.markdown("---")
c1, c2 = st.columns(2)

with c1:
    st.subheader("資產分佈 (TWD)")
    fig_pie = px.pie(df, values='market_value_twd', names='name', hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("個股損益比較")
    fig_bar = px.bar(df, x='name', y='profit_twd', color='profit_twd', 
                     color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar, use_container_width=True)

# 詳細數據表格
st.subheader("詳細持倉清單")
st.dataframe(df[['name', 'symbol', 'shares', 'cost', 'current_price', 'profit_twd']].style.format({
    'current_price': '{:.2f}',
    'profit_twd': '{:,.0f}'
}), use_container_width=True)