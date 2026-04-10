import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import io
import requests
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="全球資產損益與配息分析", layout="wide", page_icon="💰")

# --- 2. 🔐 密碼保護功能 ---
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

@st.cache_data(ttl=600)
def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=601349851"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    data = pd.read_csv(io.StringIO(response.text))
    data.columns = data.columns.str.strip().str.lower()
    return data

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate_ticker = yf.Ticker("TWD=X")
        rate_df = rate_ticker.history(period="1d")
        return rate_df['Close'].iloc[-1] if not rate_df.empty else 32.5
    except:
        return 32.5

usd_to_twd = get_exchange_rate()
st.sidebar.metric("當前匯率 (USD/TWD)", f"{usd_to_twd:.2f}")

def color_roi_custom(val):
    if isinstance(val, (int, float)):
        return 'color: #0088ff' if val > 0 else 'color: #ff4b4b'
    return ''

try:
    df = load_data(gsheet_id)
    
    # --- 4. 數據同步 (包含配息資料補回) ---
    with st.spinner('正在同步全球行情與配息數據...'):
        price_map, prev_close_map, div_map, h52_map, l52_map = {}, {}, {}, {}, {}
        history_list = []
        
        for index, row in df.iterrows():
            sym = str(row['symbol']).strip()
            tk = yf.Ticker(sym)
            
            # 市價與高低點
            h_data = tk.history(period="5d")
            if not h_data.empty:
                curr_p = h_data['Close'].iloc[-1]
                p_close = h_data['Close'].iloc[-2] if len(h_data) >= 2 else curr_p
                h_1y = tk.history(period="1y")
                h52 = h_1y['High'].max() if not h_1y.empty else curr_p
                l52 = h_1y['Low'].min() if not h_1y.empty else curr_p
            else:
                curr_p = p_close = h52 = l52 = 0
            
            price_map[index] = curr_p
            prev_close_map[index] = p_close
            h52_map[index] = h52
            l52_map[index] = l52
            
            # 趨勢數據
            h_12m_df = tk.history(period="1y")
            if not h_12m_df.empty:
                h_12m = h_12m_df['Close'].tz_localize(None).normalize()
                rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
            
            # 【補回配息邏輯】抓取過去 365 天的配息總額
            try:
                div_series = tk.dividends
                if not div_series.empty:
                    # 篩選過去一年的配息
                    last_year_divs = div_series[div_series.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))]
                    div_map[sym] = last_year_divs.sum()
                else:
                    div_map[sym] = 0.0
            except:
                div_map[sym] = 0.0
            
            time.sleep(0.05) 

    # --- 5. 數據運算 (包含稅務邏輯) ---
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        idx = row.name
        cp = price_map.get(idx, 0)
        pp = prev_close_map.get(idx, 0)
        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
        
        mv_twd = cp * row['shares'] * rate
        cost_twd = row['cost'] * row['shares'] * rate
        daily_chg = (cp - pp) * row['shares'] * rate
        daily_pct = ((cp - pp) / pp * 100) if pp > 0 else 0
        profit = mv_twd - cost_twd
        roi = (profit / cost_twd * 100) if cost_twd > 0 else 0
        
        # 配息運算
        div_per_share = div_map.get(row['symbol'], 0)
        # 美股非債券類扣 30% 稅
        tax_rate = 0.7 if row['currency'].upper() == "USD" and row['symbol'] not in bond_list else 1.0
        net_div_twd = div_per_share * row['shares'] * tax_rate * rate
        
        return pd.Series([cp, pp, mv_twd, profit, roi, net_div_twd, daily_chg, daily_pct, h52_map.get(idx, 0), l52_map.get(idx, 0)])

    df[['current_price', 'prev_close', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'daily_chg_twd', 'daily_pct', 'h52', 'l52']] = df.apply(process_row, axis=1)
    total_mv = df['mv_twd'].sum()

    # --- 6. 趨勢與摘要 ---
    if history_list:
        history_combined = pd.concat(history_list, axis=1).interpolate().ffill().bfill()
        trend_data = history_combined.sum(axis=1).to_frame(name='Total_MV')
        trend_data.iloc[-1] = total_mv 
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("總資產市值 (TWD)", f"${total_mv:,.0f}")
        total_chg = df['daily_chg_twd'].sum()
        m2.metric("今日資產變動", f"${total_chg:,.0f}", f"{(total_chg/(total_mv-total_chg)*100 if total_mv != total_chg else 0):.2f}%")
        m3.metric("總累計損益", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/total_mv*100 if total_mv != 0 else 0):.2f}%")
        # 這裡會重新顯示您的預估配息
        m4.metric("年度預估稅後配息", f"${df['net_div_twd'].sum():,.0f}")
        m5.metric("美金匯率", f"{usd_to_twd:.2f}")

        st.markdown("---")
        st.plotly_chart(px.area(trend_data, y='Total_MV', title="📈 總資產市值趨勢 (TWD)", template="plotly_white"), use_container_width=True)

    # 詳細表格
    st.subheader("📝 完整持倉與配息預估")
    st.dataframe(df[['name', 'symbol', 'current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd']].style.format({
        'current_price': '{:.2f}', 'mv_twd': '{:,.0f}', 'profit_twd': '{:,.0f}', 'roi': '{:.2f}%', 'net_div_twd': '{:,.0f}'
    }).map(color_roi_custom, subset=['roi']), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
