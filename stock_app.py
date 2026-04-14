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

# 自定義 CSS
st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

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

gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_data(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = pd.read_csv(io.StringIO(response.text))
            data.columns = data.columns.str.strip().str.lower()
            return data.dropna(subset=['symbol'])
        return None
    except:
        return None

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        # 抓取美金對台幣匯率
        ticker = yf.Ticker("TWD=X")
        return ticker.history(period="1d")['Close'].iloc[-1]
    except:
        return 32.5 # 失敗時的保底匯率

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
                # 抓取一年資料用於趨勢圖與 52 週高點
                hist = tk.history(period="1y")
                
                if not hist.empty:
                    cp = hist['Close'].iloc[-1]
                    pp = hist['Close'].iloc[-2] if len(hist) > 1 else cp
                    h52 = hist['High'].max()
                    price_map[index], prev_map[index], h52_map[index] = cp, pp, h52
                    
                    # 處理資產趨勢數據
                    h_12m = hist['Close'].copy()
                    h_12m.index = pd.to_datetime(h_12m.index).tz_localize(None).normalize()
                    rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                    history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
                
                # 抓取配息 (過濾過去 365 天)
                try:
                    divs = tk.dividends
                    one_year_ago = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365)
                    div_map[sym] = divs[divs.index > one_year_ago].sum() if not divs.empty else 0
                except:
                    div_map[sym] = 0
                
                time.sleep(0.05) # 稍微緩衝避開 Rate Limit

        bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
        def calculate_metrics(row):
            cp, pp = price_map.get(row.name, 0), prev_map.get(row.name, 0)
            h52 = h52_map.get(row.name, 0)
            rate = usd_to_twd if row['currency'].upper() == "USD" else 1
            
            mv = cp * row['shares'] * rate
            profit = mv - (row['cost'] * row['shares'] * rate)
            roi = (profit / (row['cost'] * row['shares'] * rate) * 100) if row['cost'] > 0 else 0
            drawdown_52h = ((cp - h52) / h52 * 100) if h52 > 0 else 0
            
            # 今日價值變動 = (現價 - 昨收) * 股數 * 匯率
            daily_chg = (cp - pp) * row['shares'] * rate
            
            # 稅後配息計算 (美股扣 30%)
            div_ps = div_map.get(str(row['symbol']).strip(), 0)
            tax = 0.7 if row['currency'].upper() == "USD" and str(row['symbol']).strip() not in bond_list else 1.0
            net_div = div_ps * row['shares'] * tax * rate
            
            return pd.Series({
                'current_price': cp, 'mv_twd': mv, 'profit_twd': profit,
                'roi': roi, 'net_div_twd': net_div, 'drawdown_52h': drawdown_52h,
                'daily_chg_twd': daily_chg
            })

        cols = ['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'drawdown_52h', 'daily_chg_twd']
        df[cols] = df.apply(calculate_metrics, axis=1)

        # --- 4. 數據統計 ---
        total_mv = df['mv_twd'].sum()
        total_daily_chg = df['daily_chg_twd'].sum()
        total_net_div = df['net_div_twd'].sum()
        avg_monthly_div = total_net_div / 12
        
        # 昨日總市值與變動百分比
        yesterday_total_mv = total_mv - total_daily_chg
        daily_pct = (total_daily_chg / yesterday_total_mv * 100) if yesterday_total_mv != 0 else 0

        # --- 5. 介面呈現 ---
        st.subheader("💰 財務快照")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        # 第一格：顯示總市值，Delta 為今日金額跳動
        c1.metric(
            label="總市值 (TWD)", 
            value=f"${total_mv:,.0f}", 
            delta=f"${total_daily_chg:,.0f} (與昨收比)",
            delta_color="normal"
        )
        
        # 第二格：顯示總損益，Delta 為今日漲跌幅 %
        c2.metric(
            label="總累計損益 (TWD)", 
            value=f"${df['profit_twd'].sum():,.0f}", 
            delta=f"{daily_pct:+.2f}% (今日)",
            help="括號內為今日資產相對於昨日收盤的波動百分比"
        )
        
        c3.metric("年度預估配息 (稅後)", f"${total_net_div:,.0f}", help="過去 12 個月已發放股息之稅後總和")
        c4.metric("平均月收息 (TWD)", f"${avg_monthly_div:,.0f}")

        # 資產趨勢圖
        if history_list:
            st.markdown("---")
            history_combined = pd.concat(history_list, axis=1).interpolate().ffill().bfill()
            trend_series = history_combined.sum(axis=1)
            fig = px.area(trend_series, title="資產成長曲線 (TWD)", template="plotly_white")
            fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

        # 分頁顯示表格
        tab1, tab2, tab3 = st.tabs(["📑 市值損益", "📈 月變動紀錄", "💵 詳細配息清單"])

        with tab1:
            st.dataframe(df[['name', 'roi', 'mv_twd', 'profit_twd', 'drawdown_52h']].style.format({
                'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%', 'drawdown_52h': '{:.2f}%'
            }).map(color_roi, subset=['roi']), use_container_width=True)

        with tab2:
            monthly_df = trend_series.resample('ME').last().sort_index(ascending=False).to_frame(name='月終市值')
            monthly_df['月變動額'] = monthly_df['月終市值'].diff(periods=-1)
            monthly_df['月成長率'] = (monthly_df['月變動額'] / monthly_df['月終市值'].shift(-1)) * 100
            st.dataframe(monthly_df.style.format({
                '月終市值': '{:,.0f}', '月變動額': '{:,.0f}', '月成長率': '{:.2f}%'
            }).map(color_roi, subset=['月變動額', '月成長率']), use_container_width=True)

        with tab3:
            st.write(f"### 🗓️ 預估總年領：${total_net_div:,.0f}")
            st.dataframe(df[['name', 'symbol', 'shares', 'net_div_twd']].style.format({
                'shares': '{:,.0f}', 'net_div_twd': '{:,.0f}'
            }), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
