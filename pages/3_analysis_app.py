import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- 1. 即時數據抓取 ---
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
st.set_page_config(page_title="歷年回撤分析", layout="wide")
st.title("📉 歷年回撤深度分析 (基準：52週高點)")

# 使用側邊欄輸入參數
with st.sidebar:
    st.header("分析設定")
    ticker = st.text_input("輸入股票代號", value="AVGO").upper()
    start_dt = st.date_input("分析起點", value=datetime(2005, 1, 1))

if ticker:
    with st.spinner(f'正在分析 {ticker}...'):
        try:
            # 抓取數據
            df = yf.download(ticker, start=start_dt, progress=False)
            if df.empty:
                st.error("查無資料，請檢查代號是否正確。")
            else:
                # 處理資料
                close = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
                peak = close.rolling(window=252, min_periods=1).max()
                dd = (close - peak) / peak * 100
                
                # 顯示指標卡
                live = get_live_quote(ticker)
                c1, c2, c3 = st.columns(3)
                
                if live:
                    c1.metric("即時價格", live['price'], live['change'])
                else:
                    c1.metric("即時價格", "讀取中...")

                # 修正：確保這裡有冒號
                with c2:
                    st.metric("目前回撤深度", f"{dd.iloc[-1]:.2f}%")
                
                with c3:
                    st.metric("歷史最大回撤", f"{dd.min():.2f}%")

                # 繪製圖表
                plt.style.use('seaborn-v0_8-muted')
                plt.rcParams['axes.unicode_minus'] = False
                fig, ax = plt.subplots(figsize=(15, 7), facecolor='white')
                
                ax.plot(dd.index, dd, color='#d62728', lw=1, alpha=0.8)
                ax.fill_between(dd.index, 0, dd, color='#d62728', alpha=0.1)
                
                # 標註年度最低點
                yearly_mins = dd.groupby(dd.index.year).idxmin()
                for d in yearly_mins:
                    val = dd.loc[d]
                    if val < -10:
                        ax.scatter(d, val, color='red', s=15)
                        ax.text(d, val-2, f"{val:.0f}%", fontsize=8, ha='center')

                ax.set_title(f"{ticker} 歷年回撤趨勢 (自 {start_dt.year} 起)", fontsize=14)
                ax.xaxis.set_major_locator(mdates.YearLocator(2))
                ax.grid(True, alpha=0.2)
                
                st.pyplot(fig)

        except Exception as e:
            st.error(f"分析發生錯誤: {e}")
