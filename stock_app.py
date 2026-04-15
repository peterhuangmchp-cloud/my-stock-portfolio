import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(
    page_title="私人投資儀表板", 
    layout="wide", 
    page_icon="💰",
    initial_sidebar_state="collapsed"
)

st.markdown("""<style>.stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }</style>""", unsafe_allow_html=True)

# --- 2. 🔐 密碼與數據讀取 ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if not st.session_state["authenticated"]:
        st.title("🔐 私人投資實驗室")
        pwd_input = st.text_input("請輸入解鎖密碼", type="password")
        if st.button("確認解鎖", use_container_width=True):
            if pwd_input == st.secrets.get("APP_PASSWORD"):
                st.session_state["authenticated"] = True
                st.rerun()
            else: st.error("❌ 密碼錯誤")
        st.stop()

check_password()
gsheet_id, main_gid = st.secrets.get("GSHEET_ID"), st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_data(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = pd.read_csv(io.StringIO(response.text))
            data.columns = data.columns.str.strip().str.lower()
            return data.dropna(subset=['symbol'])
        return None
    except: return None

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        ticker = yf.Ticker("TWD=X")
        return float(ticker.history(period="1d")['Close'].iloc[-1])
    except: return 32.5 

def color_roi(val):
    if isinstance(val, (int, float)):
        return 'color: #0088ff' if val > 0 else 'color: #ff4b4b'
    return ''

# --- 3. 核心運算邏輯 ---
try:
    df = load_data(gsheet_id, main_gid)
    if df is not None:
        usd_to_twd = get_exchange_rate()
        with st.spinner('📱 正在同步全球行情與配息...'):
            price_map, prev_map, div_map, h52_map, history_list = {}, {}, {}, {}, []
            for index, row in df.iterrows():
                sym = str(row['symbol']).strip()
                tk = yf.Ticker(sym)
                hist = tk.history(period="1y")
                
                if not hist.empty:
                    cp = float(hist['Close'].iloc[-1])
                    pp = float(hist['Close'].iloc[-2]) if len(hist) > 1 else cp
                    h52 = float(hist['High'].max())
                    price_map[index], prev_map[index], h52_map[index] = cp, pp, h52
                    
                    h_12m = hist['Close'].copy()
                    h_12m.index = pd.to_datetime(h_12m.index).tz_localize(None).normalize()
                    rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                    history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
                
                # --- [配息抓取邏輯強化版] ---
                try:
                    # 1. 嘗試從 info 抓取
                    info = tk.info
                    d_val = info.get('trailingAnnualDividendRate', 0) or info.get('dividendRate', 0) or 0
                    
                    # 2. 如果 info 是 0，或標的是 SHV/SGOV，改用歷史紀錄加總
                    if d_val == 0 or sym.upper() in ['SHV', 'SGOV']:
                        divs = tk.dividends
                        if not divs.empty:
                            # 抓取最近 12 筆配息紀錄直接加總，避開日期過濾的錯誤
                            d_val = float(divs.tail(12).sum())
                    
                    div_map[sym] = d_val
                except:
                    div_map[sym] = 0
                
                time.sleep(0.05)

        bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
        def calculate_metrics(row):
            sym = str(row['symbol']).strip()
            cp = price_map.get(row.name, 0)
            pp = prev_map.get(row.name, 0)
            h52 = h52_map.get(row.name, 0)
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            
            mv = float(cp * row['shares'] * rate)
            profit = float(mv - (row['cost'] * row['shares'] * rate))
            roi = float((profit / (row['cost'] * row['shares'] * rate) * 100) if row['cost'] > 0 else 0)
            drawdown_52h = float(((cp - h52) / h52 * 100) if h52 > 0 else 0)
            daily_chg = float((cp - pp) * row['shares'] * rate)
            
            # 配息計算
            div_ps = div_map.get(sym, 0)
            tax = 0.7 if row['currency'].upper() == "USD" and sym not in bond_list else 1.0
            net_div = float(div_ps * row['shares'] * tax * rate)
            
            return pd.Series([cp, mv, profit, roi, net_div, drawdown_52h, daily_chg])

        cols = ['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'drawdown_52h', 'daily_chg_twd']
        df[cols] = df.apply(calculate_metrics, axis=1)

        # --- 4. 數據統計 ---
        total_mv = df['mv_twd'].sum()
        total_daily_chg = df['daily_chg_twd'].sum()
        total_profit = df['profit_twd'].sum()
        total_net_div = df['net_div_twd'].sum()
        
        # --- 5. 介面呈現 ---
        st.subheader("💰 財務快照")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總市值 (TWD)", f"${total_mv:,.0f}", f"${total_daily_chg:,.0f}")
        c2.metric("累計損益 (TWD)", f"${total_profit:,.0f}")
        c3.metric("年度預估配息 (稅後)", f"${total_net_div:,.0f}")
        c4.metric("平均月收息 (TWD)", f"${total_net_div/12:,.0f}")

        if history_list:
            trend = pd.concat(history_list, axis=1).ffill().fillna(0).sum(axis=1)
            st.plotly_chart(px.area(trend, title="資產成長曲線 (TWD)", template="plotly_white"), use_container_width=True)

        tab1, tab2, tab3 = st.tabs(["📑 市值損益", "📈 月變動紀錄", "💵 詳細配息清單"])
        with tab1:
            st.dataframe(df[['name', 'roi', 'mv_twd', 'profit_twd', 'drawdown_52h']].style.format({
                'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%', 'drawdown_52h': '{:.2f}%'
            }).map(color_roi, subset=['roi']), use_container_width=True)
        with tab2:
            m_df = trend.resample('ME').last().sort_index(ascending=False).to_frame(name='月終市值')
            m_df['月變動額'] = m_df['月終市值'].diff(periods=-1)
            st.dataframe(m_df.style.format('{:,.0f}').map(color_roi, subset=['月變動額']), use_container_width=True)
        with tab3:
            st.dataframe(df[['name', 'symbol', 'shares', 'net_div_twd']].style.format({
                'shares': '{:,.0f}', 'net_div_twd': '{:,.0f}'
            }), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
