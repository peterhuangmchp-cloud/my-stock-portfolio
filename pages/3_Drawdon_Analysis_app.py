import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import time

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Historical Drawdown Analysis", layout="wide")

# --- 2. 核心抓取函數 ---
def get_live_quote(ticker):
    try:
        t_up = ticker.upper()
        market = ":TPE" if ".TW" in t_up else ":TWO" if ".TWO" in t_up else ":NASDAQ"
        clean_ticker = t_up.replace(".TW", "").replace(".TWO", "")
        url = f"https://www.google.com/finance/quote/{clean_ticker}{market}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.content, 'lxml')
        price = soup.select_one('div[class*="YMl6u"] span, .fxKbKc').get_text()
        change = soup.select_one('div[class*="jw7m8"], .En4P9').get_text()
        return {"price": price, "change": change}
    except:
        return None

# --- 3. 介面與參數 ---
st.title("📉 Drawdown Analysis & Market Events")
st.markdown("分析基準：**前 52 週最高點**。陰影區域標註歷史重大政經事件。")

with st.sidebar:
    st.header("Settings")
    ticker = st.text_input("Ticker (e.g., AVGO, 2330.TW)", value="AVGO").upper()
    start_dt = st.date_input("Start Date", value=datetime(2005, 1, 1))

if ticker:
    with st.spinner(f'Fetching data for {ticker}...'):
        try:
            # 抓取歷史數據
            df = yf.download(ticker, start=start_dt, progress=False)
            if df.empty:
                st.error("No data found. Please check the ticker symbol.")
            else:
                # 數據清理與計算
                if isinstance(df.columns, pd.MultiIndex):
                    close = df['Close'].iloc[:, 0]
                else:
                    close = df['Close']
                
                # 計算回撤 (Drawdown)
                peak = close.rolling(window=252, min_periods=1).max()
                dd = (close - peak) / peak * 100
                
                # 顯示即時指標卡
                live = get_live_quote(ticker)
                c1, c2, c3 = st.columns(3)
                with c1:
                    if live:
                        st.metric("Live Price", live['price'], live['change'])
                    else:
                        st.metric("Live Price", "N/A")
                with c2:
                    st.metric("Current Drawdown", f"{dd.iloc[-1]:.2f}%")
                with c3:
                    st.metric("Max Historical DD", f"{dd.min():.2f}%")

                # --- 4. 繪圖邏輯 ---
                plt.style.use('seaborn-v0_8-muted')
                fig, ax = plt.subplots(figsize=(15, 8), facecolor='white')
                
                # 繪製回撤線
                ax.plot(dd.index, dd, color='#d62728', lw=1.2, alpha=0.9, label='Drawdown %')
                ax.fill_between(dd.index, 0, dd, color='#d62728', alpha=0.08)

                # 定義重大事件 (包含 2025 川普關稅)
                crash_events = [
                    {"name": "2008 Financial Crisis", "start": "2008-01-01", "end": "2009-06-30", "color": "gray"},
                    {"name": "2018 Trade War", "start": "2018-06-01", "end": "2018-12-31", "color": "orange"},
                    {"name": "2020 COVID-19", "start": "2020-02-01", "end": "2020-04-30", "color": "green"},
                    {"name": "2022 Rate Hikes", "start": "2022-01-01", "end": "2022-12-31", "color": "purple"},
                    {"name": "2025 Trump Tariff", "start": "2025-01-20", "end": "2025-05-30", "color": "brown"}
                ]

                # 標註事件區間
                for event in crash_events:
                    ev_s = pd.to_datetime(event["start"])
                    ev_e = pd.to_datetime(event["end"])
                    # 只在圖表範圍內的事件才標註
                    if ev_s > dd.index[0]:
                        ax.axvspan(ev_s, ev_e, color=event["color"], alpha=0.12, label=event["name"])
                        # 在區間上方垂直標註名稱
                        ax.text(ev_s + (ev_e - ev_s)/2, 5, event["name"], 
                                rotation=90, ha='center', va='bottom', fontsize=8, color='#666666')

                # 標註年度最低點
                yearly_mins = dd.groupby(dd.index.year).idxmin()
                for d in yearly_mins:
                    val = dd.loc[d]
                    if val < -10:
                        ax.scatter(d, val, color='red', s=20, zorder=5)
                        ax.text(d, val-3, f"{val:.1f}%", fontsize=9, ha='center', fontweight='bold')

                # 圖表格式美化
                ax.set_title(f"{ticker} Historical Drawdown & Crisis Events", fontsize=16, pad=30)
                ax.set_ylabel("Drawdown (%)")
                ax.axhline(0, color='black', lw=1)
                ax.axhline(-20, color='black', ls='--', alpha=0.5) # 技術面熊市線
                ax.set_ylim(dd.min() - 15, 20) # 預留空間給文字標籤
                ax.xaxis.set_major_locator(mdates.YearLocator(2))
                ax.grid(True, linestyle=':', alpha=0.3)
                
                # 圖例處理 (避免重複標籤)
                handles, labels = ax.get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc='lower left', fontsize=8, ncol=3)

                st.pyplot(fig)

                # 5. 數據預覽
                with st.expander("View Raw Data (Recent 60 Days)"):
                    st.table(dd.tail(60).sort_index(ascending=False))

        except Exception as e:
            st.error(f"Error during analysis: {e}")
