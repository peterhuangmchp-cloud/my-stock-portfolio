import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基本設定 (行動端優化) ---
st.set_page_config(
    page_title="私人投資儀表板", 
    layout="wide", 
    page_icon="💰",
    initial_sidebar_state="collapsed"
)

# 自定義 CSS 提升質感
st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 12px; border-radius: 12px; border: 1px solid #eee; }
    [data-testid="stMetricValue"] { font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

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

# --- 3. 數據讀取與快取邏輯 (修復 HTTP 400 問題) ---
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_data(sheet_id, gid):
    # 加入更完整的 URL 參數確保讀取成功
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = pd.read_csv(io.StringIO(response.text))
            data.columns = data.columns.str.strip().str.lower()
            return data.dropna(subset=['symbol'])
        else:
            st.error(f"數據加載失敗: 狀態碼 {response.status_code}")
            return None
    except Exception as e:
        st.error(f"連線 Google Sheet 錯誤: {e}")
        return None

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        # 改用更穩定的 TWD=X 抓取方式
        ticker = yf.Ticker("TWD=X")
        return ticker.fast_info['last_price'] if 'last_price' in ticker.fast_info else 32.5
    except:
        return 32.5

# --- 4. 核心運算邏輯 (修復 Rate Limit 問題) ---
try:
    df = load_data(gsheet_id, main_gid)
    if df is not None:
        usd_to_twd = get_exchange_rate()
        
        with st.spinner('📱 正在安全同步全球數據...'):
            price_map, prev_map, div_map, h52_map, history_list = {}, {}, {}, {}, []
            
            for index, row in df.iterrows():
                sym = str(row['symbol']).strip().upper()
                try:
                    tk = yf.Ticker(sym)
                    # 使用 fast_info 減少 API 請求負擔，預防 Rate Limit
                    cp = tk.fast_info['last_price']
                    pp = tk.fast_info['previous_close']
                    h52 = tk.fast_info['year_high']
                    
                    price_map[index], prev_map[index], h52_map[index] = cp, pp, h52
                    
                    # 歷史數據與配息 (適度間隔)
                    hist = tk.history(period="1y")
                    if not hist.empty:
                        h_12m = hist['Close'].copy()
                        h_12m.index = pd.to_datetime(h_12m.index).tz_localize(None).normalize()
                        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                        history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
                        
                        divs = tk.dividends
                        one_year_ago = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365)
                        div_map[sym] = divs[divs.index > one_year_ago].sum() if not divs.empty else 0
                    
                    # 關鍵：加入微小延遲避免被 Yahoo 封鎖
                    time.sleep(0.1) 
                except Exception:
                    continue

        # 計算損益數據
        bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
        def calculate_metrics(row):
            cp = price_map.get(row.name, 0)
            pp = prev_map.get(row.name, 0)
            h52 = h52_map.get(row.name, 0)
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            
            mv = cp * row['shares'] * rate
            profit = mv - (row['cost'] * row['shares'] * rate)
            roi = (profit / (row['cost'] * row['shares'] * rate) * 100) if row['cost'] > 0 else 0
            drawdown_52h = ((cp - h52) / h52 * 100) if h52 > 0 else 0
            daily_chg = (cp - pp) * row['shares'] * rate
            
            div_ps = div_map.get(str(row['symbol']).strip().upper(), 0)
            tax = 0.7 if row['currency'].upper() == "USD" and str(row['symbol']).strip() not in bond_list else 1.0
            net_div = div_ps * row['shares'] * tax * rate
            
            return pd.Series({
                'mv_twd': mv, 'profit_twd': profit, 'roi': roi, 
                'net_div_twd': net_div, 'drawdown_52h': drawdown_52h, 'daily_chg_twd': daily_chg
            })

        df[['mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'drawdown_52h', 'daily_chg_twd']] = df.apply(calculate_metrics, axis=1)

        # --- 5. iPhone 版介面呈現 ---
        total_mv = df['mv_twd'].sum()
        total_daily_chg = df['daily_chg_twd'].sum()
        total_net_div = df['net_div_twd'].sum()
        avg_monthly_div = total_net_div / 12

        st.subheader("💰 財務總覽")
        col1, col2 = st.columns(2)
        col1.metric("總市值", f"${total_mv:,.0f}")
        col2.metric("今日變動", f"${total_daily_chg:,.0f}", f"{(total_daily_chg/total_mv*100):.2f}%")
        
        col3, col4 = st.columns(2)
        col3.metric("預估年息 (稅後)", f"${total_net_div:,.0f}")
        col4.metric("平均月收息", f"${avg_monthly_div:,.0f}")

        # 功能分頁
        tab1, tab2, tab3 = st.tabs(["📊 持倉明細", "📉 成長曲線", "🗓️ 配息細節"])
        
        with tab1:
            st.dataframe(df[['name', 'roi', 'mv_twd', 'profit_twd', 'drawdown_52h']].style.format({
                'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%', 'drawdown_52h': '{:.2f}%'
            }), use_container_width=True)

        with tab2:
            if history_list:
                trend = pd.concat(history_list, axis=1).ffill().sum(axis=1)
                fig = px.area(trend, title="12個月資產走勢", template="plotly_white")
                fig.update_layout(height=350, margin=dict(l=0,r=0,b=0,t=40))
                st.plotly_chart(fig, use_container_width=True)

        with tab3:
            st.metric("平均每月被動收入", f"${avg_monthly_div:,.0f} TWD")
            st.dataframe(df[['name', 'symbol', 'shares', 'net_div_twd']].style.format({
                'shares': '{:,.0f}', 'net_div_twd': '{:,.0f}'
            }), use_container_width=True)

except Exception as e:
    st.error(f"系統檢修中，請稍後再試。錯誤代碼: {e}")
