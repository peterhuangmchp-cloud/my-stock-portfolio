import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="私人投資儀表板", layout="wide", page_icon="💰", initial_sidebar_state="collapsed")

st.markdown("""<style>.main { padding-top: 1rem; } .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }</style>""", unsafe_allow_html=True)

# --- 2. 🔐 密碼保護與數據讀取 ---
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
            else:
                st.error("❌ 密碼錯誤")
        st.stop()

check_password()

@st.cache_data(ttl=600)
def load_data(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            data = pd.read_csv(io.StringIO(response.text))
            data.columns = data.columns.str.strip().str.lower()
            return data.dropna(subset=['symbol'])
    except:
        return None

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        ticker = yf.Ticker("TWD=X")
        val = ticker.history(period="1d")['Close'].iloc[-1]
        return float(val)
    except:
        return 32.5

# --- 3. 核心運算邏輯 ---
try:
    df = load_data(st.secrets.get("GSHEET_ID"), st.secrets.get("MAIN_GID"))
    if df is not None:
        usd_to_twd = get_exchange_rate()
        
        with st.spinner('📱 正在同步全球行情與配息數據...'):
            price_map, div_amt_map, div_yield_map, history_list = {}, {}, {}, []
            
            for index, row in df.iterrows():
                sym = str(row['symbol']).strip()
                tk = yf.Ticker(sym)
                hist = tk.history(period="1y")
                
                if not hist.empty:
                    # [修復] 強制去時區化，防止與 Timestamp 比較出錯
                    hist.index = hist.index.tz_localize(None)
                    
                    cp = float(hist['Close'].iloc[-1])
                    price_map[index] = cp
                    
                    # 處理資產趨勢數據
                    rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                    h_series = (hist['Close'] * row['shares'] * rate).to_frame(name=sym)
                    h_series.index = h_series.index.normalize()
                    history_list.append(h_series)
                
                    # --- 配息數據抓取 ---
                    try:
                        info = tk.info
                        d_amt = info.get('dividendRate', 0) or 0
                        d_yield = info.get('dividendYield', 0) or 0
                        
                        # [修復] 歷史配息日期比對
                        if d_amt == 0:
                            divs = tk.dividends
                            if not divs.empty:
                                divs.index = divs.index.tz_localize(None)
                                one_year_ago = pd.Timestamp.now().normalize() - pd.Timedelta(days=365)
                                d_amt = float(divs[divs.index > one_year_ago].sum())
                                d_yield = d_amt / cp if cp > 0 else 0
                        
                        div_amt_map[sym] = d_amt
                        div_yield_map[sym] = d_yield * 100
                    except:
                        div_amt_map[sym], div_yield_map[sym] = 0, 0
                
                time.sleep(0.05)

        # 指標計算
        bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
        def calculate_metrics(row):
            sym = str(row['symbol']).strip()
            cp = price_map.get(row.name, 0)
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            mv = float(cp * row['shares'] * rate)
            profit = float(mv - (row['cost'] * row['shares'] * rate))
            
            # 稅後計算 (美股扣 30%, 債券/台股免)
            tax = 0.7 if row['currency'].upper() == "USD" and sym not in bond_list else 1.0
            net_div = float(div_amt_map.get(sym, 0) * row['shares'] * tax * rate)
            
            return pd.Series([cp, mv, profit, net_div, div_yield_map.get(sym, 0), div_amt_map.get(sym, 0)])

        df[['current_price', 'mv_twd', 'profit_twd', 'net_div_twd', 'yield_pct', 'div_amt']] = df.apply(calculate_metrics, axis=1)

        # --- 4. 介面呈現 ---
        total_mv = df['mv_twd'].sum()
        total_net_div = df['net_div_twd'].sum()
        
        st.subheader("💰 財務快照")
        c1, c2, c3 = st.columns(3)
        c1.metric("總市值 (TWD)", f"${total_mv:,.0f}")
        c2.metric("預估年收息 (稅後)", f"${total_net_div:,.0f}")
        c3.metric("平均組合殖利率", f"{(total_net_div/total_mv*100):.2f}%")

        # --- 資產成長曲線 ---
        if history_list:
            st.markdown("---")
            full_history = pd.concat(history_list, axis=1).ffill().fillna(0).sum(axis=1)
            fig = px.area(full_history, title="總資產趨勢成長曲線 (TWD)", 
                         template="plotly_white", color_discrete_sequence=['#0088ff'])
            st.plotly_chart(fig, use_container_width=True)

        tab1, tab2, tab3 = st.tabs(["📑 市值損益", "📈 月變動紀錄", "💵 配息詳細清單"])
        
        with tab1:
            st.dataframe(df[['name', 'symbol', 'mv_twd', 'profit_twd']].style.format({
                'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}'
            }), use_container_width=True)
            
        with tab2:
            if history_list:
                monthly_df = full_history.resample('ME').last().sort_index(ascending=False).to_frame(name='月終市值')
                monthly_df['月變動額'] = monthly_df['月終市值'].diff(periods=-1)
                st.dataframe(monthly_df.style.format('{:,.0f}'), use_container_width=True)
            
        with tab3:
            # 同時顯示金額與利率
            st.dataframe(df[['name', 'symbol', 'div_amt', 'yield_pct', 'net_div_twd']].rename(columns={
                'div_amt': '每股年配息', 'yield_pct': '殖利率', 'net_div_twd': '預估實拿(TWD)'
            }).style.format({
                '每股年配息': '${:.2f}', '殖利率': '{:.2f}%', '預估實拿(TWD)': '{:,.0f}'
            }), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
