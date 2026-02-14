import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 設定網頁標題
st.set_page_config(page_title="股票投資組合與 200MA 分析", layout="wide", page_icon="📈")
st.title("🚀 股票資產長期趨勢追蹤 (200MA)")

# --- 1. 讀取 Google Sheets ---
def load_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    return data

# --- 2. 側邊欄設定 ---
st.sidebar.header("⚙️ 系統設定")
gsheet_id = st.sidebar.text_input("Google Sheet ID", "15NuQ4YTC08NsC1cVtpJbLCgUHI2WrhGwyFpXFzcHOR4")

if not gsheet_id:
    st.info("請在側邊欄輸入您的 Google Sheet ID。")
    st.stop()

# --- 3. 數據處理 ---
try:
    df = load_data(gsheet_id)
    
    # 定義要排除的債券關鍵字或標號 (依據您的清單)
    bond_symbols = ['TLT', 'SHV', 'SGOV', 'LQD']
    # 過濾出純股票清單
    stock_df = df[~df['symbol'].isin(bond_symbols)].copy()
    stock_symbols = stock_df['symbol'].unique()

    st.subheader("📈 股票個股與 200MA 走勢圖")
    
    # 讓用戶選擇要查看的股票
    selected_stock = st.selectbox("請選擇要分析的股票：", stock_symbols)

    if selected_stock:
        with st.spinner(f'正在抓取 {selected_stock} 的歷史數據...'):
            ticker = yf.Ticker(selected_stock)
            # 抓取兩年的歷史數據以確保 200MA 計算精準
            hist = ticker.history(period="2y")
            hist['200MA'] = hist['Close'].rolling(window=200).mean()
            
            # 繪製 Plotly 線圖
            fig = go.Figure()
            
            # 收盤價
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='收盤價', line=dict(color='royalblue', width=2)))
            # 200MA
            fig.add_trace(go.Scatter(x=hist.index, y=hist['200MA'], mode='lines', name='200MA', line=dict(color='orange', width=2, dash='dash')))
            
            # 設定佈局
            fig.update_layout(
                title=f"{selected_stock} 股價與 200MA 對照圖",
                xaxis_title="日期",
                yaxis_title="價格",
                hovermode="x unified",
                template="plotly_white",
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            
            # 加上現價與 200MA 的狀態標籤
            current_price = hist['Close'].iloc[-1]
            current_ma = hist['200MA'].iloc[-1]
            diff = ((current_price - current_ma) / current_ma) * 100 if current_ma else 0
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 趨勢提示卡片
            status_col1, status_col2 = st.columns(2)
            status_col1.metric("目前股價", f"{current_price:.2f}")
            status_col2.metric("200MA 乖離率", f"{diff:.2f}%", delta=f"{'多頭趨勢' if diff > 0 else '空頭趨勢'}")

    # --- 原有的損益摘要表格 ---
    st.markdown("---")
    st.subheader("📝 股票持倉即時數據")
    # (此處可保留您原有的計算總資產與表格的邏輯...)

except Exception as e:
    st.error(f"發生錯誤：{e}")
