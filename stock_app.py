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

# --- 3. 核心數據讀取 (GID 隱私化) ---
st.title("📊 全球資產損益與配息看板")
gsheet_id = st.secrets.get("GSHEET_ID")
main_gid = st.secrets.get("MAIN_GID") # 從 Secrets 讀取，不再洩漏

@st.cache_data(ttl=600)
def load_data(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
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
    df = load_data(gsheet_id, main_gid)
    
    # --- 4. 數據同步 (包含代號自動修正) ---
    with st.spinner('正在同步全球行情、配息與風險數據...'):
        price_map, prev_close_map, div_map, h52_map = {}, {}, {}, {}
        history_list = []
        
        for index, row in df.iterrows():
            # 【自動修正代號邏輯】
            raw_sym = str(row['symbol']).strip().upper()
            if raw_sym == "CREDO":
                sym = "CRDO"
            elif raw_sym.isdigit(): # 如果全是數字(如 2330), 自動補 .TW
                sym = raw_sym + ".TW"
            elif ":" in raw_sym: # 處理 TPE:2330 這種格式
                sym = raw_sym.split(":")[-1] + ".TW"
            else:
                sym = raw_sym
            
            tk = yf.Ticker(sym)
            
            # 獲取價格與歷史數據 (避開 fast_info)
            h_1y_data = tk.history(period="1y")
            if not h_1y_data.empty:
                curr_p = h_1y_data['Close'].iloc[-1]
                p_close = h_1y_data['Close'].iloc[-2] if len(h_1y_data) >= 2 else curr_p
                h52 = h_1y_data['High'].max()
                
                # 趨勢數據處理
                h_12m = h_1y_data['Close'].copy()
                h_12m.index = pd.to_datetime(h_12m.index).tz_localize(None).normalize()
                rate = usd_to_twd if row['currency'].upper() == "USD" else 1
                history_list.append((h_12m * row['shares'] * rate).to_frame(name=sym))
            else:
                curr_p = p_close = h52 = 0
            
            price_map[index] = curr_p
            prev_close_map[index] = p_close
            h52_map[index] = h52
            
            # 配息數據 (過去 365 天)
            try:
                divs = tk.dividends
                div_map[sym] = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))].sum() if not divs.empty else 0.0
            except:
                div_map[sym] = 0.0
            
            time.sleep(0.05) 

    # --- 5. 數據運算 ---
    bond_list = ['TLT', 'SHV', 'SGOV', 'LQD']
    def process_row(row):
        idx = row.name
        cp, pp = price_map.get(idx, 0), prev_close_map.get(idx, 0)
        h52 = h52_map.get(idx, 0)
        rate = usd_to_twd if row['currency'].upper() == "USD" else 1
        
        mv_twd = cp * row['shares'] * rate
        profit = mv_twd - (row['cost'] * row['shares'] * rate)
        roi = (profit / (row['cost'] * row['shares'] * rate) * 100) if row['cost'] > 0 else 0
        
        # 52週高點跌幅
        drawdown_52h = ((cp - h52) / h52 * 100) if h52 > 0 else 0
        
        # 配息計算 (美股 30% 稅率)
        # 先取得修正後的 sym 用來對應配息地圖
        raw_sym = str(row['symbol']).strip().upper()
        sym_key = "CRDO" if raw_sym == "CREDO" else (raw_sym.split(":")[-1] + ".TW" if ":" in raw_sym else (raw_sym + ".TW" if raw_sym.isdigit() else raw_sym))
        div_ps = div_map.get(sym_key, 0)
        
        tax = 0.7 if row['currency'].upper() == "USD" and sym_key not in bond_list else 1.0
        net_div = div_ps * row['shares'] * tax * rate
        
        daily_chg = (cp - pp) * row['shares'] * rate
        daily_pct = ((cp - pp) / pp * 100) if pp > 0 else 0
        
        return pd.Series([cp, mv_twd, profit, roi, net_div, drawdown_52h, daily_chg, daily_pct])

    df[['current_price', 'mv_twd', 'profit_twd', 'roi', 'net_div_twd', 'drawdown_52h', 'daily_chg_twd', 'daily_pct']] = df.apply(process_row, axis=1)
    total_mv = df['mv_twd'].sum()

    # --- 6. 介面呈現 ---
    total_chg = df['daily_chg_twd'].sum()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("總資產市值 (TWD)", f"${total_mv:,.0f}")
    m2.metric("今日資產變動", f"${total_chg:,.0f}", f"{(total_chg/(total_mv-total_chg)*100 if total_mv != total_chg else 0):.2f}%")
    m3.metric("總累計損益", f"${df['profit_twd'].sum():,.0f}", f"{(df['profit_twd'].sum()/total_mv*100 if total_mv != 0 else 0):.2f}%")
    m4.metric("年度預估稅後配息", f"${df['net_div_twd'].sum():,.0f}")
    m5.metric("美金匯率", f"{usd_to_twd:.2f}")

    if history_list:
        history_combined = pd.concat(history_list, axis=1).interpolate().ffill().bfill()
        st.plotly_chart(px.area(history_combined.sum(axis=1), title="📈 總資產市值趨勢 (TWD)", template="plotly_white"), use_container_width=True)

    st.subheader("📝 詳細持倉與風險監控")
    st.dataframe(df[['name', 'symbol', 'current_price', 'roi', 'net_div_twd', 'drawdown_52h', 'daily_pct']].style.format({
        'current_price': '{:.2f}', 'roi': '{:.2f}%', 'net_div_twd': '{:,.0f}', 'drawdown_52h': '{:.2f}%', 'daily_pct': '{:.2f}%'
    }).map(color_roi_custom, subset=['roi', 'daily_pct'])
      .map(lambda x: 'color: red' if x < -10 else '', subset=['drawdown_52h']), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
