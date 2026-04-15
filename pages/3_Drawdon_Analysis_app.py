import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Historical Drawdown Analysis", layout="wide", page_icon="📉")

# --- 2. 核心抓取函數 (穩定版) ---
def get_live_metrics(ticker_str):
    try:
        tk = yf.Ticker(ticker_str)
        info = tk.fast_info
        
        price = info.get('lastPrice')
        prev_close = info.get('previousClose')
        
        if price and prev_close:
            change_val = price - prev_close
            change_pct = (change_val / prev_close) * 100
            return {
                "price": f"{price:.2f}",
                "change": f"{change_val:+.2f} ({change_pct:+.2f}%)"
            }
        return None
    except:
        return None

# --- 3. 介面與參數 ---
st.title("📉 Drawdown Analysis & Geopolitical Events")
st.markdown("分析基準：**前 252 日 (約 52 週) 最高點**。標註歷史重大政經與地緣政治事件。")

with st.sidebar:
    st.header("Settings")
    ticker_input = st.text_input("Ticker (e.g., AVGO, 2330.TW)", value="AVGO").upper()
    start_dt = st.date_input("Start Date", value=datetime(2010, 1, 1))
    st.divider()
    st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if ticker_input:
    with st.spinner(f'Fetching data for {ticker_input}...'):
        try:
            # 抓取歷史數據
            df = yf.download(ticker_input, start=start_dt, progress=False)
            
            if df.empty:
                st.error("找不到該標的數據，請確認代號是否正確。")
            else:
                # --- 數據清理 ---
                if isinstance(df.columns, pd.MultiIndex):
                    close = df['Close'].iloc[:, 0]
                else:
                    close = df['Close']
                
                # 確保索引為 DatetimeIndex
                close.index = pd.to_datetime(close.index)
                
                # 計算回撤 (Drawdown)
                peak = close.rolling(window=252, min_periods=1).max()
                dd = (close - peak) / peak * 100
                
                # --- 即時指標卡 ---
                live = get_live_metrics(ticker_input)
                c1, c2, c3 = st.columns(3)
                with c1:
                    if live:
                        st.metric("Live Price", live['price'], live['change'])
                    else:
                        st.metric("Live Price (Last Close)", f"{close.iloc[-1]:.2f}")
                with c2:
                    current_dd = dd.iloc[-1]
                    st.metric("Current Drawdown", f"{current_dd:.2f}%")
                with c3:
                    st.metric("Max Historical DD", f"{dd.min():.2f}%")

                # --- 4. 繪圖邏輯 ---
                plt.style.use('ggplot') 
                fig, ax = plt.subplots(figsize=(15, 7.5), facecolor='white')
                
                # 繪製回撤線
                ax.plot(dd.index, dd, color='#d62728', lw=1.5, alpha=0.9, label='Drawdown %')
                ax.fill_between(dd.index, 0, dd, color='#d62728', alpha=0.15)

                # 重大歷史事件 (包含 2026 美伊衝突)
                crash_events = [
                    {"name": "2008 Financial Crisis", "start": "2008-01-01", "end": "2009-06-30", "color": "#7f8c8d"},
                    {"name": "2018 Trade War", "start": "2018-06-01", "end": "2018-12-31", "color": "#f39c12"},
                    {"name": "2020 COVID-19", "start": "2020-02-01", "end": "2020-04-30", "color": "#27ae60"},
                    {"name": "2022 Rate Hikes", "start": "2022-01-01", "end": "2022-12-31", "color": "#8e44ad"},
                    {"name": "2025 Trump Tariff", "start": "2025-01-20", "end": "2025-05-30", "color": "#c0392b"},
                    {"name": "2026 US-Iran Conflict", "start": "2026-01-15", "end": "2026-04-03", "color": "#2c3e50"}
                ]

                # 標註事件區間 (修正時區與比對)
                chart_start = dd.index[0]
                for event in crash_events:
                    ev_s = pd.to_datetime(event["start"])
                    ev_e = pd.to_datetime(event["end"])
                    
                    # 若數據有時區資訊，則同步時區
                    if dd.index.tz is not None:
                        ev_s = ev_s.tz_localize(dd.index.tz)
                        ev_e = ev_e.tz_localize(dd.index.tz)
                    
                    if ev_s > chart_start:
                        ax.axvspan(ev_s, ev_e, color=event["color"], alpha=0.1)
                        # 名稱標註
                        ax.text(ev_s + (ev_e - ev_s)/2, 5, event["name"], 
                                rotation=90, ha='center', va='bottom', fontsize=9, color='#555555')

                # --- 修正後的標註年度最低點邏輯 ---
                # 使用 apply 確保在所有 Pandas 版本中都能運作
                yearly_mins = dd.resample('YE').apply(lambda x: x.idxmin() if not x.empty else None).dropna()
                
                for d in yearly_mins:
                    if d in dd.index:
                        val = dd.loc[d]
                        if val < -15: # 過濾輕微波動，只標註回撤大於 15% 的重要低點
                            ax.scatter(d, val, color='#c0392b', s=35, zorder=5, edgecolors='white')
                            ax.text(d, val-2, f"{val:.0f}%", fontsize=9, ha='center', color='#c0392b', fontweight='bold')

                # 圖表細節美化
                ax.set_title(f"{ticker_input} Drawdown Deep Analysis", fontsize=18, fontweight='bold', pad=20)
                ax.set_ylabel("Drawdown Percentage (%)", fontsize=12)
                ax.axhline(0, color='black', lw=1.5)
                ax.axhline(-20, color='#e67e22', ls='--', alpha=0.6) # 熊市線標示
                
                # 動態調整 Y 軸範圍，確保 Max DD 能被看見
                min_y = min(dd.min() - 15, -40)
                ax.set_ylim(min_y, 25) 
                
                # 座標軸優化
                ax.xaxis.set_major_locator(mdates.YearLocator(2))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                plt.xticks(rotation=45)
                
                st.pyplot(fig)

                # --- 5. 數據預覽 ---
                with st.expander("📊 近期回撤數據細節"):
                    st.dataframe(dd.tail(100).sort_index(ascending=False).to_frame(name="Drawdown %").style.format("{:.2f}%"))

        except Exception as e:
            st.error(f"分析過程中發生錯誤: {e}")
            st.info("這可能是由於數據格式不相容或 Pandas 版本更新導致，請嘗試重新整理。")
