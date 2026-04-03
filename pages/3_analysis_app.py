import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- 1. 網頁設定 ---
st.set_page_config(page_title="個股歷年回撤分析系統", layout="wide", page_icon="📉")

# --- 2. 核心功能函數 ---
def get_google_finance_live_data(ticker):
    """從 Google Finance 抓取即時數據"""
    try:
        t_up = ticker.upper()
        if '.TW' in t_up:
            google_ticker, currency = t_up.replace('.TW', ':TPE'), "TWD"
        elif '.TWO' in t_up:
            google_ticker, currency = t_up.replace('.TWO', ':TWO'), "TWD"
        else:
            # 預設嘗試 NASDAQ，若失敗可再擴充邏輯
            google_ticker, currency = f"{t_up}:NASDAQ", "USD"
            
        url = f"https://www.google.com/finance/quote/{google_ticker}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'lxml')
        
        # 抓取價格與漲跌幅
        price_el = soup.select_one('div[class*="YMl6u"] span, .fxKbKc')
        price = price_el.get_text() if price_el else "N/A"
        
        change_el = soup.select_one('div[class*="jw7m8"], .En4P9')
        change = change_el.get_text() if change_el else ""
        
        return {'price': f"{price} {currency}", 'change': change}
    except:
        return None

# --- 3. UI 介面 ---
st.title("📉 個股歷年回撤標註系統")
st.markdown("分析基準：**前 52 週最高點**。本工具用於觀察歷史波動深度與調整頻率。")

# 側邊欄輸入
with st.sidebar:
    st.header("參數設定")
    ticker = st.text_input("請輸入股票代號", value="AVGO").upper()
    start_date = st.date_input("分析起始日期", value=datetime(2005, 1, 1))
    st.info("支援美股 (如: NVDA) 及台股 (如: 2330.TW)")

if ticker:
    with st.spinner(f'正在分析 {ticker} 歷史數據...'):
        try:
            # 1. 抓取歷史資料
            df = yf.download(ticker, start=start_date, progress=False)
            
            if df.empty:
                st.error(f"找不到代號 '{ticker}'，請檢查輸入是否正確。")
            else:
                # 處理資料結構 (處理 yfinance 可能產生的 MultiIndex)
                if isinstance(df.columns, pd.MultiIndex):
                    close_prices = df['Close'].iloc[:, 0]
                else:
                    close_prices = df['Close']
                close_prices = close_prices.squeeze()

                # 2. 計算 Drawdown (前 52 週最高點回撤)
                peak_52w = close_prices.rolling(window=252, min_periods=1).max()
                drawdown = (close_prices - peak_52w) / peak_52w * 100

                # 3. 準備繪圖
                plt.style.use('seaborn-v0_8-muted')
                plt.rcParams['font.sans-serif'] = ['Arial'] # 雲端部署建議用 Arial 或 Ubuntu
                plt.rcParams['axes.unicode_minus'] = False
                
                fig, ax = plt.subplots(figsize=(15, 8), facecolor='white')

                # 繪製主線
                ax.plot(drawdown.index, drawdown, color='#d62728', linewidth=1, alpha=0.7, label='52週高點回撤 %')
                ax.fill_between(drawdown.index, 0, drawdown, color='#d62728', alpha=0.05)

                # 參考線
                ax.axhline(0, color='black', linewidth=1)
                ax.axhline(-10, color='purple', linestyle=':', alpha=0.5)
                ax.axhline(-20, color='black', linewidth=1.2, alpha=0.8, label='-20% 技術面熊市')

                # 4. 標註每年度最低回測值
                yearly_min_dates = drawdown.groupby(drawdown.index.year).idxmin()
                for date in yearly_min_dates:
                    val = float(drawdown.loc[date])
                    if val < -5: # 超過 -5% 才標註，避免圖表太擠
                        ax.scatter(date, val, color='#d62728', s=25, zorder=5)
                        ax.text(date, val - 1.5, f"{val:.1f}%", 
                                fontsize=9, ha='center', color='#8b0000', fontweight='bold',
                                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

                # 5. 標註「現在」數據
                last_date = drawdown.index[-1]
                last_dd = float(drawdown.iloc[-1])
                ax.annotate(f"現在 ({last_date.strftime('%Y/%m/%d')})\n{last_dd:.2f}%", 
                            xy=(last_date, last_dd), xytext=(25, -40),
                            textcoords='offset points',
                            bbox=dict(boxstyle='round,pad=0.5', fc='#d62728', ec='none', alpha=0.9),
                            color='white', fontweight='bold',
                            arrowprops=dict(arrowstyle="->", color='#d62728', connectionstyle="arc3,rad=.2"))

                # 6. 座標軸優化
                ax.set_xlim(pd.Timestamp(start_date), last_date + timedelta(days=90))
                ax.xaxis.set_major_locator(mdates.YearLocator(2)) 
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                
                ax.set_title(f"{ticker} 歷年最大回撤 (基準：前 52 週高點)", fontsize=16, pad=20)
                ax.set_ylabel("Drawdown (%)")
                ax.set_ylim(drawdown.min() - 15, 5)
                ax.grid(True, linestyle='--', alpha=0.3)
                ax.legend(loc='upper right')

                # 7. 顯示即時數據卡片
                live = get_google_finance_live_data(ticker)
                c1, c2, c3, c4 = st.columns(4)
                if live:
                    c1.metric("即時價格", live['price'])
                    c2.metric("今日漲跌", live['change'])
                c3.metric("當前回撤", f"{last_dd:.2f}%")
                c4.metric("歷史最大回撤", f"{drawdown.min():.2f}%")

                # 8. 輸出圖表
                st.pyplot(fig)
                
                # 9. 顯示原始數據表 (可選)
                with st.expander("查看原始數據"):
                    st.dataframe(drawdown.tail(100), use_container_width=True)

        except Exception as e:
            st.error(f"發生錯誤: {e}")
