import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Historical Drawdown Analysis", layout="wide", page_icon="📉")

# --- 2. 核心抓取函數 (改用更穩定的 fast_info) ---
def get_live_metrics(ticker_str):
    try:
        tk = yf.Ticker(ticker_str)
        # fast_info 是 yfinance 較快且穩定的即時數據接口
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
    st.caption("2026/04/15 系統維護完成")

if ticker_input:
    with st.spinner(f'Fetching data for {ticker_input}...'):
        try:
            # 抓取歷史數據
            df = yf.download(ticker_input, start=start_dt, progress=False)
            
            if df.empty:
                st.error("找不到該標的數據，請確認代號是否正確。")
            else:
                # --- 數據清理 ---
                # 處理 yfinance 可能回傳的 MultiIndex 結構
                if isinstance(df.columns, pd.MultiIndex):
                    close = df['Close'].iloc[:, 0]
                else:
                    close = df['Close']
                
                # 計算回撤 (Drawdown)
                # 使用 rolling(252) 代表 52 週高點
                peak = close.rolling(window=252, min_periods=1).max()
                dd = (close - peak) / peak * 100
                
                # --- 即時指標卡 ---
                live = get_live_metrics(ticker_input)
                c1, c2, c3 = st.columns(3)
                with c1:
                    if live:
                        st.metric("Live Price", live['price'], live['change'])
                    else:
                        # 備援：若 fast_info 失敗，顯示最後一筆收盤價
                        st.metric("Live Price (Last Close)", f"{close.iloc[-1]:.2f}")
                with c2:
                    current_dd = dd.iloc[-1]
                    st.metric("Current Drawdown", f"{current_dd:.2f}%", 
                              delta_color="inverse" if current_dd < -5 else "normal")
                with c3:
                    st.metric("Max Historical DD", f"{dd.min():.2f}%")

                # --- 4. 繪圖邏輯 ---
                # 使用較新的樣式
                plt.style.use('ggplot') 
                fig, ax = plt.subplots(figsize=(15, 7), facecolor='white')
                
                # 繪製回撤線
                ax.plot(dd.index, dd, color='#d62728', lw=1.5, alpha=0.9, label='Drawdown %')
                ax.fill_between(dd.index, 0, dd, color='#d62728', alpha=0.15)

                # 重大歷史事件
                crash_events = [
                    {"name": "2008 Financial Crisis", "start": "2008-01-01", "end": "2009-06-30", "color": "#7f8c8d"},
                    {"name": "2018 Trade War", "start": "2018-06-01", "end": "2018-12-31", "color": "#f39c12"},
                    {"name": "2020 COVID-19", "start": "2020-02-01", "end": "2020-04-30", "color": "#27ae60"},
                    {"name": "2022 Rate Hikes", "start": "2022-01-01", "end": "2022-12-31", "color": "#8e44ad"},
                    {"name": "2025 Trump Tariff", "start": "2025-01-20", "end": "2025-05-30", "color": "#c0392b"},
                    {"name": "2026 US-Iran Conflict", "start": "2026-01-15", "end": "2026-04-03", "color": "#2c3e50"}
                ]

                # 標註事件區間 (修正時區比對)
                chart_start = dd.index[0]
                for event in crash_events:
                    ev_s = pd.to_datetime(event["start"]).tz_localize(dd.index.tz)
                    ev_e = pd.to_datetime(event["end"]).tz_localize(dd.index.tz)
                    
                    if ev_s > chart_start:
                        ax.axvspan(ev_s, ev_e, color=event["color"], alpha=0.1, label=event["name"])
                        # 名稱標註放在頂部
                        ax.text(ev_s + (ev_e - ev_s)/2, 15, event["name"], 
                                rotation=90, ha='center', va='top', fontsize=8, color='#555555', fontweight='bold')

                # 標註年度最低點 (每隔兩年標註一次，避免過度擁擠)
                yearly_mins = dd.resample('YE').idxmin()
                for d in yearly_mins:
                    if d in dd.index:
                        val = dd.loc[d]
                        if val < -15: # 只有回撤大於 15% 標註，過濾噪音
                            ax.scatter(d, val, color='#c0392b', s=30, zorder=5, edgecolors='white')
                            ax.text(d, val-2, f"{val:.0f}%", fontsize=8, ha='center', color='#c0392b')

                # 圖表細節美化
                ax.set_title(f"{ticker_input} Drawdown Deep Analysis (vs 52W High)", fontsize=18, fontweight='bold', pad=20)
                ax.set_ylabel("Drawdown Percentage (%)", fontsize=12)
                ax.axhline(0, color='black', lw=1.5)
                ax.axhline(-20, color='#e67e22', ls='--', alpha=0.6, label='Bear Market (-20%)')
                
                # 設定 Y 軸範圍
                ax.set_ylim(min(dd.min() - 10, -30), 20) 
                
                # 座標軸優化
                ax.xaxis.set_major_locator(mdates.YearLocator(2))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                plt.xticks(rotation=45)
                
                # 圖例去重
                handles, labels = ax.get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc='lower left', fontsize=9, ncol=2, frameon=True)

                st.pyplot(fig)

                # --- 5. 統計區塊 ---
                st.divider()
                with st.expander("📊 回撤統計明細"):
                    col_stat1, col_stat2 = st.columns(2)
                    with col_stat1:
                        st.write("**回撤區間統計**")
                        bins = [0, -5, -10, -20, -30, -50, -100]
                        labels = ["0 to -5%", "-5% to -10%", "-10% to -20%", "-20% to -30%", "-30% to -50%", "> -50%"]
                        dist = pd.cut(dd, bins=bins, labels=labels).value_counts().sort_index()
                        st.bar_chart(dist)
                    
                    with col_stat2:
                        st.write("**近期數據預覽**")
                        recent_df = dd.tail(10).sort_index(ascending=False).to_frame(name="Drawdown %")
                        st.table(recent_df.style.format("{:.2f}%"))

        except Exception as e:
            st.error(f"分析過程中發生錯誤: {e}")
            st.info("建議嘗試重新整理或檢查網路連線。")
