from datetime import datetime, timedelta
import io
import time
import matplotlib.pyplot as plt
import pandas as pd
import requests

# 1. 抓取證交所三大法人每日買賣超資料 (以 2026 年為例)
def fetch_institutional_investors_2026():
    # 2026 年 6 月 1 日至今日的交易日範圍 (證交所僅工作日有資料，此處先建立完整日期範圍後過濾)
    start_date = datetime(2026, 6, 1)
    end_date = min(datetime.today(), datetime(2026, 12, 31))
    dates = pd.date_range(start=start_date, end=end_date)

    records = []
    # 證交所「三大法人買賣超日報」總表：https://www.twse.com.tw/rwd/zh/fund/BFI82U?date=YYYYMMDD&response=json
    trading_days = [dt for dt in dates if dt.weekday() < 5]
    total = len(trading_days)
    print(f"正在從證交所下載 2026 年度三大法人籌碼資料，共 {total} 個工作日...")

    for index, dt in enumerate(trading_days, start=1):
        date_str = dt.strftime("%Y%m%d")
        url = (
            "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
            f"?response=json&dayDate={date_str}&weekDate={date_str}"
            f"&monthDate={date_str}&type=day"
        )
        progress = f"[{index}/{total}] {date_str}"
        print(f"{progress} 下載中...", flush=True)

        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("stat") == "OK" and "data" in data:
                    # data["data"] 結構：
                    # [ ["自營商(自行買賣)", "買進金額", "賣出金額", "買賣差額"], ... ]
                    foreign = 0
                    trust = 0
                    dealer = 0

                    for row in data["data"]:
                        name = row[0].strip()
                        # 買賣差額在第四欄 (index 3)，移除逗號並轉為 float，單位元轉為億元
                        diff_val = float(row[3].replace(",", "")) / 100000000

                        if "外資" in name:
                            foreign += diff_val
                        elif "投信" in name:
                            trust += diff_val
                        elif "自營商" in name:
                            dealer += diff_val
                    records.append({
                        "Date": dt,
                        "Foreign": foreign,
                        "Investment_Trust": trust,
                        "Dealer": dealer
                    })
                    print(
                        f"{progress} 完成，外資: {foreign:.2f}億, 投信: {trust:.2f}億, "
                        f"自營商: {dealer:.2f}億（已取得 {len(records)} 日）",
                        flush=True,
                    )
                else:
                    print(f"{progress} 無交易資料", flush=True)
            else:
                print(f"{progress} 下載失敗，HTTP {res.status_code}", flush=True)
            # 遵循爬蟲禮儀，每次請求延遲 3 秒以防被證交所封鎖 IP
            time.sleep(1.5)
        except Exception as e:
            print(f"{progress} 下載失敗: {e}", flush=True)

    print(f"下載結束，成功取得 {len(records)}/{total} 日。", flush=True)
            
    if not records:
        print("未能取得 2026 年實際數據，使用模擬數據呈現圖表。")
        df = pd.DataFrame(index=dates)
        df["Foreign"] = 0
        df["Investment_Trust"] = 0
        df["Dealer"] = 0
        return df

    df = pd.DataFrame(records)
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)
    return df

# 2. 繪圖設定
def plot_institutional_trend(df):
    # 計算累積買賣超
    df["Foreign_Cum"] = df["Foreign"].cumsum()
    df["Trust_Cum"] = df["Investment_Trust"].cumsum()
    df["Dealer_Cum"] = df["Dealer"].cumsum()

    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "MingLiU", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.figure(figsize=(12, 6))

    plt.plot(
        df.index,
        df["Foreign_Cum"],
        label="外資及陸資 (累積)",
        color="dodgerblue",
        linewidth=1.5,
    )
    plt.plot(
        df.index,
        df["Trust_Cum"],
        label="投信 (累積)",
        color="crimson",
        linewidth=1.5,
    )
    plt.plot(
        df.index,
        df["Dealer_Cum"],
        label="自營商 (累積)",
        color="forestgreen",
        linewidth=1.5,
    )

    plt.title("2026 年台股三大法人累積買賣超趨勢圖", fontsize=16, fontweight="bold")
    plt.xlabel("日期", fontsize=12)
    plt.ylabel("金額 (新台幣億元)", fontsize=12)
    plt.axhline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.7)
    plt.legend(loc="upper left", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df_data = fetch_institutional_investors_2026()
    plot_institutional_trend(df_data)