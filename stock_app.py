import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="私人投資儀表板", layout="wide", page_icon="💰", initial_sidebar_state="collapsed")

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
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = pd.read_csv(io.StringIO(response.text))
            data.columns = data.columns.str.strip().str.lower()
            return data.dropna(subset=['symbol'])
    except:
        return None

# --- 3. 核心運算邏輯 ---
try:
    df = load_data(st.secrets.get("GSHEET_ID"), st.secrets.get("MAIN_GID"))
    if df is not None:
        usd_to_twd = 32.5 
        
        with st.spinner('📱 正在同步全球數據...'):
            price_map, div_amt_map, history_list = {}, {}, []

            for index, row in df.iterrows():
                sym = str(row['symbol']).strip()
                tk = yf.Ticker(sym)
                
                # --- 1. 抓取價格與趨勢 ---
                try:
                    hist = tk.history(period="1y")
                    if not hist.empty:
                        hist.index = hist.index.tz_localize(None)
                        cp = float(hist['Close'].iloc[-1])
                        price_map[index] = cp
                        
                        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                        h_series = (hist['Close'] * row['shares'] * rate).to_frame(name=sym)
                        h_series.index = h_series.index.normalize()
                        history_list.append(h_series)
                    else:
                        price_map[index] = 0
                except:
                    price_map[index] = 0

                # --- 2. [核心修正] 混合式配息抓取邏輯 ---
                try:
                    d_amt = 0
                    # A. 先嘗試抓 info (這對 NVDA, AVGO 等科技股最準)
                    info = tk.info
                    d_amt = info.get('trailingAnnualDividendRate', 0) or info.get('dividendRate', 0) or 0
                    
                    # B. 如果 info 為 0 (這對 SHV, SGOV 月配息標的最常發生)，則改用歷史加總
                    if d_amt == 0:
                        divs = tk.dividends
                        if not divs.empty:
                            divs.index = divs.index.tz_localize(None)
                            one_year_ago = pd.Timestamp.now().normalize() - pd.Timedelta(days=365)
                            d_amt = float(divs[divs.index > one_year_ago].sum())
                    
                    div_amt_map[sym] = d_amt
                except:
                    div_amt_map[sym] = 0
                
                time.sleep(0.15) # 稍微加長間隔，防止被封鎖

        # 債券清單：美股債券免 30% 稅
        bond_list = ['TLT', 'SHV', 'SGOV', 'LQD', '00937B.TW']
        
        def calculate_metrics(row):
            sym = str(row['symbol']).strip()
            cp = price_map.get(row.name, 0)
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            mv = float(cp * row['shares'] * rate)
            profit = float(mv - (row['cost'] * row['shares'] * rate))
            
            # 稅後計算
            d_amt = div_amt_map.get(sym, 0)
            tax = 0.7 if row['currency'].upper() == "USD" and sym not in bond_list else 1.0
            net_div = float(d_amt * row['shares'] * tax * rate)
            
            return pd.Series([cp, mv, profit, net_div, d_amt])

        df[['current_price', 'mv_twd', 'profit_twd', 'net_div_twd', 'div_amt']] = df.apply(calculate_metrics, axis=1)

        # --- 4. 介面呈現 ---
        total_mv = df['mv_twd'].sum()
        total_net_div = df['net_div_twd'].sum()
        
        st.subheader("💰 財務快照")
        c1, c2, c3 = st.columns(3)
        c1.metric("總市值 (TWD)", f"${total_mv:,.0f}")
        c2.metric("預估年收息 (稅後)", f"${total_net_div:,.0f}")
        c3.metric("組合平均殖利率", f"{(total_net_div/total_mv*100 if total_mv > 0 else 0):.2f}%")

        if history_list:
            st.markdown("---")
            full_history = pd.concat(history_list, axis=1).ffill().fillna(0).sum(axis=1)
            st.plotly_chart(px.area(full_history, title="總資產趨勢成長曲線 (TWD)", template="plotly_white"), use_container_width=True)

        tab1, tab2, tab3 = st.tabs(["📑 市值損益", "📈 月變動紀錄", "💵 配息詳細明細"])
        
        with tab1:
            st.dataframe(df[['name', 'symbol', 'mv_twd', 'profit_twd']].style.format({'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}'}), use_container_width=True)
            
        with tab3:
            st.dataframe(df[['name', 'symbol', 'div_amt', 'net_div_twd']].rename(columns={
                'div_amt': '每股年度總配息(原幣)', 'net_div_twd': '預估實拿年息(TWD)'
            }).style.format({
                '每股年度總配息(原幣)': '${:.2f}', '預估實拿年息(TWD)': '{:,.0f}'
            }), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
