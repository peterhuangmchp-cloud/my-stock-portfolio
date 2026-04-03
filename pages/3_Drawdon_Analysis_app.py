# --- 繪圖邏輯開始 ---
                plt.style.use('seaborn-v0_8-muted')
                plt.rcParams['axes.unicode_minus'] = False
                fig, ax = plt.subplots(figsize=(15, 8), facecolor='white')
                
                # 1. 繪製回撤主線
                ax.plot(drawdown.index, drawdown, color='#d62728', lw=1.2, alpha=0.9, label='Drawdown %')
                ax.fill_between(drawdown.index, 0, drawdown, color='#d62728', alpha=0.08)

                # 2. 定義歷史重大股災區間 (標註用)
                crash_events = [
                    {"name": "2008 Financial Crisis", "start": "2008-01-01", "end": "2009-06-30", "color": "gray"},
                    {"name": "2011 Euro Debt", "start": "2011-07-01", "end": "2011-12-31", "color": "blue"},
                    {"name": "2018 Trade War", "start": "2018-06-01", "end": "2018-12-31", "color": "orange"},
                    {"name": "2020 COVID-19", "start": "2020-02-01", "end": "2020-04-30", "color": "green"},
                    {"name": "2022 Inflation/Rate Hike", "start": "2022-01-01", "end": "2022-12-31", "color": "purple"}
                ]

                # 3. 畫出背景陰影與標籤
                for event in crash_events:
                    ev_start = pd.to_datetime(event["start"])
                    ev_end = pd.to_datetime(event["end"])
                    # 只在數據時間範圍內才畫
                    if ev_start > drawdown.index[0]:
                        ax.axvspan(ev_start, ev_end, color=event["color"], alpha=0.15, label=event["name"])
                        # 在區間上方標註名稱
                        ax.text(ev_start + (ev_end - ev_start)/2, 2, event["name"], 
                                rotation=45, ha='center', fontsize=8, color='#555555')

                # 4. 標註年度最低點 (原有的邏輯)
                yearly_mins = drawdown.groupby(drawdown.index.year).idxmin()
                for d in yearly_mins:
                    val = drawdown.loc[d]
                    if val < -10:
                        ax.scatter(d, val, color='red', s=20, zorder=5)
                        ax.text(d, val-3, f"{val:.1f}%", fontsize=9, ha='center', fontweight='bold')

                # 5. 設定格式
                ax.set_title(f"{ticker} Drawdown & Historical Market Events", fontsize=16, pad=25)
                ax.set_ylabel("Drawdown (%)")
                ax.axhline(0, color='black', lw=1)
                ax.axhline(-20, color='black', ls='--', alpha=0.5) # 熊市線
                ax.xaxis.set_major_locator(mdates.YearLocator(2))
                ax.grid(True, alpha=0.2)
                ax.set_ylim(drawdown.min() - 15, 10) # 預留上方空間給標籤
                
                # 顯示圖例 (避免重複)
                handles, labels = ax.get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc='lower left', fontsize=9, ncol=2)

                st.pyplot(fig)
                # --- 繪圖邏輯結束 ---
