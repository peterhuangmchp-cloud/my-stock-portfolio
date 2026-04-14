import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="私人投資儀表板", layout="wide", page_icon="💰", initial_sidebar_state="collapsed")

# --- 2. 🔐 密碼保護 ---
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

# --- 3. 數據同步 ---
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
    except:
        return None

# --- 4. 核心邏輯：真正去 Yahoo 抓取 ---
try:
    df = load_data(st.secrets["GSHEET_ID"], st.secrets["MAIN_GID"])
    if df is not None:
        usd_to_twd = 32.5 # 簡化，可改為 API 抓取
        
        with st.spinner('📱 正在從 Yahoo 提取即時行情與配息率...'):
            price_map, div_ps_map, history_list = {}, {}, []
            st.sidebar.subheader("🔍 Yahoo 抓取狀態")
            
            for index, row in df.iterrows():
                sym = str(row['symbol']).strip()
                tk = yf.Ticker(sym)
                
                # 抓取價格
                hist = tk.history(period="1y")
                if not hist.empty:
                    cp = float(hist['Close'].iloc[-1])
                    price_map[index] = cp
                    
                    # 處理趨勢圖資料
                    h_12m = hist['Close'].copy()
                    h_12m.index = pd.to_datetime(h_12m.index).tz_localize(None).normalize()
                    rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                    history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
                
                # --- [重點] 去 Yahoo 抓配息率 ---
                try:
                    # 1. 優先使用 Sheet 的手動數據
                    if 'dividend_yield' in df.columns and not pd.isna(row['dividend_yield']):
                        div_ps_map[sym] = cp * (float(row['dividend_yield']) / 100)
                        st.sidebar.info(f"✅ {sym}: 使用 Sheet 數據")
                    else:
                        # 2. 自動去 Yahoo Info 抓取
                        info = tk.info
                        # Yahoo Info 有兩種配息率，我們取預估值 (forwardYield)
                        y_yield = info.get('dividendYield', info.get('trailingAnnualDividendYield', 0))
                        if y_yield:
                            div_ps_map[sym] = cp * float(y_yield)
                            st.sidebar.success(f"✅ {sym}: Yahoo 抓取成功 ({y_yield*100:.2f}%)")
                        else:
                            div_ps_map[sym] = 0
                            st.sidebar.warning(f"⚠️ {sym}: Yahoo 無資料")
                except:
                    div_ps_map[sym] = 0
                    st.sidebar.error(f"❌ {sym}: 連線被 Yahoo 封鎖")
                
                time.sleep(0.2) # 減少被封鎖機率

        # --- 計算資產 ---
        bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
        def calculate_metrics(row):
            cp = price_map.get(row.name, 0)
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            mv = float(cp * row['shares'] * rate)
            profit = float(mv - (row['cost'] * row['shares'] * rate))
            
            # 配息與稅務
            div_ps = div_ps_map.get(str(row['symbol']).strip(), 0)
            tax = 0.7 if row['currency'].upper() == "USD" and str(row['symbol']).strip() not in bond_list else 1.0
            net_div = float(div_ps * row['shares'] * tax * rate)
            
            return pd.Series([cp, mv, profit, net_div])

        df[['current_price', 'mv_twd', 'profit_twd', 'net_div_twd']] = df.apply(calculate_metrics, axis=1)

        # --- 介面呈現 ---
        total_mv = df['mv_twd'].sum()
        total_net_div = df['net_div_twd'].sum()
        
        st.subheader("💰 財務快照")
        c1, c2, c3 = st.columns(3)
        c1.metric("總市值 (TWD)", f"${total_mv:,.0f}")
        c2.metric("預估年收息 (稅後)", f"${total_net_div:,.0f}")
        c3.metric("平均月收息", f"${(total_net_div/12):,.0f}")

        tab1, tab2 = st.tabs(["📑 資產損益", "💵 配息預估紀錄"])
        with tab1:
            st.dataframe(df[['name', 'symbol', 'shares', 'mv_twd', 'profit_twd']].style.format({'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}'}), use_container_width=True)
        with tab2:
            st.dataframe(df[['name', 'symbol', 'net_div_twd']].style.format({'net_div_twd': '{:,.0f}'}), use_container_width=True)

except Exception as e:
    st.error(f"系統錯誤: {e}")
