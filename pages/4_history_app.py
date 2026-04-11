import streamlit as st
import pandas as pd
import plotly.express as px
import io
import requests

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="資產淨值歷史軌跡", layout="wide", page_icon="📈")

# --- 2. 核心數據讀取函數 (安全性優化) ---
gsheet_id = st.secrets.get("GSHEET_ID")
# 從 Secrets 讀取 History 分頁的 GID，不再硬編碼在程式裡
history_gid = st.secrets.get("HISTORY_GID") 

def load_history_data(sheet_id, gid):
    # 修正：將原本寫死的數字替換為變數 gid
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = pd.read_csv(io.StringIO(response.text))
            # 統一欄位名稱為小寫
            data.columns = data.columns.str.strip().str.lower()
            return data
        else:
            st.error(f"無法存取 Google Sheet, 狀態碼: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"連線錯誤: {e}")
        return None

# --- 3. 頁面內容 ---
st.title("📈 資產淨值成長歷史 (Net Worth)")
st.markdown(f"數據來源：Google Sheet - 歷史紀錄")

try:
    # 執行讀取
    history_df = load_history_data(gsheet_id, history_gid)
    
    if history_df is not None and not history_df.empty:
        # 轉換日期格式
        history_df['date'] = pd.to_datetime(history_df['date'])
        history_df = history_df.sort_values('date')

        # --- A. 關鍵指標卡 ---
        last_val = history_df['total_mv'].iloc[-1]
        
        # 只有一筆資料時，顯示目前的金額
        if len(history_df) > 1:
            prev_val = history_df['total_mv'].iloc[-2]
            delta = last_val - prev_val
        else:
            delta = 0
            
        c1, c2, c3 = st.columns(3)
        c1.metric("最新紀錄總額", f"${last_val:,.0f}", f"${delta:,.0f}")
        c2.metric("紀錄起始日", history_df['date'].iloc[0].strftime('%Y-%m-%d'))
        c3.metric("資料總筆數", f"{len(history_df)} 筆")

        # --- B. 淨值成長曲線圖 ---
        st.markdown("---")
        
        # 繪製 Plotly 線圖
        fig = px.line(history_df, x='date', y='total_mv', 
                      title="Net Worth Growth Curve",
                      markers=True)
        
        # 優化圖表外觀 (回歸專業 Plotly 風格)
        fig.update_traces(line_color='#1f77b4', line_width=3, marker=dict(size=8))
        fig.update_layout(
            hovermode="x unified",
            xaxis_title="日期",
            yaxis_title="總市值 (TWD)",
            yaxis=dict(tickformat=",.0f"),
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- C. 數據表格清單 ---
        with st.expander("查看所有歷史數據明細"):
            # 檢查是否有 daily_perf 欄位再進行格式化，避免報錯
            format_dict = {'total_mv': '{:,.0f}'}
            if 'daily_perf' in history_df.columns:
                format_dict['daily_perf'] = '{:,.0f}'
                
            st.dataframe(history_df.sort_values('date', ascending=False).style.format(format_dict), 
                         use_container_width=True)

    else:
        st.warning("目前 History 分頁中還沒有數據。請確認 Google Apps Script 是否已成功執行。")

except Exception as e:
    st.error(f"程式執行失敗：{e}")
    st.info("請確認：1. Secrets 中已設定 HISTORY_GID。 2. Sheet 標題包含 date, total_mv")
