import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# --- 1. 抓取函數 (省略內容以節省空間，請保留您原本的 get_live_quote) ---
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

# --- 2. 頁面內容 ---
st.set_page_config(page_title="歷年回撤與股災分析", layout="wide")
st.title("📉 歷年回撤與重大股災事件分析")

with st.sidebar:
    ticker = st.text_input("輸入股票代號", value="AVGO").upper()
    start_dt = st.date_input("分析起點", value=datetime(2005, 1, 1))

if ticker:
    try:
        df = yf.download(ticker, start=start_dt, progress=False)
        if df.empty:
            st.error("查無資料")
        else:
            # A. 數據處理
            close = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
            peak = close.rolling(window=252, min_periods=1).max()
            drawdown = (close - peak) / peak * 100
            
            # B. 指標卡
            live = get_live_quote(ticker)
            c1, c2, c3 = st.columns(3)
            with c1:
                if live: st.metric("即時價格", live['price'], live['change'])
            with c2:
                st.metric("目前回撤深度", f"{drawdown.iloc[-1]:.2f}%")
            with c3:
                st.metric("歷史最大回撤", f"{drawdown.min():.2f}%")

            # C. 繪圖區 (請檢查此處縮排)
            plt.style.use('seaborn-v0_8-muted')
            fig, ax = plt.subplots(figsize=(15, 8), facecolor='white')
            
            ax.plot(drawdown.index, drawdown, color='#d62728', lw=1.2, alpha=0.9)
            ax.fill_between(drawdown.index, 0, drawdown, color='#d62728', alpha=0.08)

            # 歷史股災事件定義
            crash_events = [
                {"name": "2008 Financial Crisis", "start": "2008-01-01", "end": "2009-06-30", "color": "gray"},
                {"name": "2018 Trade War", "start": "2018-06-01", "end": "2018-12-31", "color": "orange"},
                {"name": "2020 COVID-19", "start": "2020-02-01", "end": "2020-04-30", "color": "green"},
                {"name": "2022 Inflation/Rate Hike", "start": "2022-01-01", "end": "2022-12-31", "color": "purple"}
            ]

            # 標註股災區間
            for event in crash_events:
                ev_s = pd.to_datetime(event["start"])
                ev_e = pd.to_datetime(event["end"])
                if ev_s > drawdown.index[0]:
                    ax.axvspan(ev_s, ev_e, color=event["color"], alpha=0.12)
                    ax.text(ev_s + (ev_e - ev_s)/2, 5, event["name"], 
                            rotation=45, ha='center', fontsize=8, color='#666666')

            # 標註年度低點
            yearly_mins = drawdown.groupby(drawdown.index.year).idxmin()
            for d in yearly_mins:
                val = drawdown.loc[d]
                if val < -10:
                    ax.scatter(d, val, color='red', s=20, zorder=5)
                    ax.text(d, val-3, f"{val:.1f}%", fontsize=9, ha='center', fontweight='bold')

            ax.set_title(f"{ticker} Drawdown & Historical Events", fontsize=16)
            ax.set_ylim(drawdown.min() - 15, 15)
            ax.grid(True, alpha=0.2)
            st.pyplot(fig)

    except Exception as e:
        st.error(f"分析錯誤: {e}")
