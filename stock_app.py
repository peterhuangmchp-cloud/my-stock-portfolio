import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="全球資產損益與配息分析", layout="wide")

# --- 2. 🔐 安全密碼與數據讀取 ---
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

gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID")

@st.cache_data(ttl=600)
def load_data():
    url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/export?format=csv&gid={main_gid}"
    data = pd.read_csv(io.StringIO(requests.get(url).text))
    data.columns = data.columns.str.strip().str.lower()
    return data

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return yf.Ticker("TWD=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 32.5

def color_roi(val):
    if isinstance(val, (int, float)):
        return 'color: #0088ff' if val > 0 else 'color: #ff4b4b'
    return ''

# --- 3. 核心運算 ---
try:
    df = load_data()
    usd_to_twd = get_exchange_rate()
    
    with st.spinner('同步數據中...'):
        price_map, div_map, h52_map, history_list = {}, {}, {}, []
        
        for index, row in df.iterrows():
            sym = str(row['symbol']).strip()
            tk = yf.Ticker(sym)
            hist = tk.history(period="1y")
            
            if not hist.empty:
                curr_p = hist['Close'].iloc[-1]
                h52 = hist['High'].max()
                price_map[index] = curr_p
                h52_map[index] = h52
                
                h_12m = hist['Close'].copy()
                h_12m.index = pd.to_datetime(h_12m.index).tz_localize(None).normalize()
                rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
            
            try:
                divs = tk.dividends
                div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0
            except:
                div_map[sym] = 0
            time.sleep(0.02)

    # 指標運算
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def calculate_metrics(row):
        cp = price_map.get(row.name, 0)
        h52 = h52_map.get(row.name, 0)
        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
        mv = cp * row['shares'] * rate
        profit = mv - (row['cost'] * row['shares'] * rate)
        roi = (profit / (row['cost'] * row['shares'] * rate) * 100) if row['cost'] > 0 else 0
        drawdown_52h = ((cp - h52) / h52 * 100) if h52 > 0 else 0
        
        div_ps = div_map.get(str(row['symbol']).strip(), 0)
        tax = 0.7 if row['currency'].upper() == "USD" and str(row['symbol']).strip() not in bond_list else 1.0
        net_div = div_ps * row['shares'] * tax * rate
        return pd.Series([cp, mv, profit, roi, net_div, drawdown_52h])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'drawdown_52h']] = df.apply(calculate_metrics, axis=1)

    # --- 4. 顯示：重新排列後的獨立表格區 ---

    # A. 財務摘要
    st.subheader("💰 總體財務摘要")
    m1, m2, m3, m4 = st.columns(4)
    total_mv = df['mv_twd'].sum()
    m1.metric("總市值 (TWD)", f"${total_mv:,.0f}")
    m2.metric("總損益", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/total_mv*100):.2f}%")
    m3.metric("年度預估稅後配息", f"${df['net_div_twd'].sum():,.0f}")
    m4.metric("美元匯率", f"{usd_to_twd:.2f}")

    # B. 【原表格三 改到 表格一】：資產變動紀錄
    if history_list:
        st.markdown("---")
        st.subheader("📈 表格一：過去 12 個月資產變動紀錄")
        history_combined = pd.concat(history_list, axis=1).interpolate().ffill().bfill()
        trend_series = history_combined.sum(axis=1)
        
        monthly_df = trend_series.resample('ME').last().sort_index(ascending=False).to_frame(name='月終市值')
        monthly_df['月變動額'] = monthly_df['月終市值'].diff(periods=-1)
        monthly_df['月成長率'] = (monthly_df['月變動額'] / monthly_df['月終市值'].shift(-1)) * 100
        
        st.dataframe(monthly_df.style.format({
            '月終市值': '{:,.0f}', '月變動額': '{:,.0f}', '月成長率': '{:.2f}%'
        }).map(color_roi, subset=['月變動額', '月成長率']), use_container_width=True)
        
        st.plotly_chart(px.area(trend_series, title="總資產趨勢圖", template="plotly_white"), use_container_width=True)

    # C. 【原表格一 改到 表格二】：資產市值與損益
    st.markdown("---")
    st.subheader("📑 表格二：資產市值與風險監控")
    st.dataframe(df[['name', 'symbol', 'current_price', 'mv_twd', 'profit_twd', 'roi', 'drawdown_52h']].style.format({
        'current_price': '{:.2f}', 'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%', 'drawdown_52h': '{:.2f}%'
    }).map(color_roi, subset=['roi']), use_container_width=True)

    # D. 【原表格二 改到 表格三】：獨立配息明細表
    st.subheader("💵 表格三：年度預估配息明細 (稅後 TWD)")
    st.dataframe(df[['name', 'symbol', 'shares', 'net_div_twd']].style.format({
        'shares': '{:,.0f}', 'net_div_twd': '{:,.0f}'
    }), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
