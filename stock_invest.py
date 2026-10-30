from datetime import datetime
from pathlib import Path
import time
import matplotlib.pyplot as plt
import pandas as pd
import requests

DATA_PATH = Path(__file__).with_name("institutional.csv")
CACHE_COLUMNS = ["Date", "Foreign", "Investment_Trust", "Dealer", "Status"]

def load_cache():
    if not DATA_PATH.exists():
        return pd.DataFrame(columns=CACHE_COLUMNS)
    cache = pd.read_csv(DATA_PATH, parse_dates=["Date"])
    if "Status" not in cache.columns:
        cache["Status"] = "ok"
    return cache

def save_cache(cache):
    cache.sort_values("Date").to_csv(DATA_PATH, index=False)

def remember(cache, dt, status, foreign=None, trust=None, dealer=None):
    row = pd.DataFrame([{
        "Date": pd.Timestamp(dt).normalize(),
        "Foreign": foreign,
        "Investment_Trust": trust,
        "Dealer": dealer,
        "Status": status,
    }])
    cache = pd.concat([cache, row], ignore_index=True)
    cache = cache.drop_duplicates("Date", keep="last")
    save_cache(cache)
    return cache

def parse_institutional_row(data):
    # data["data"] 結構：
    # [ ["自營商(自行買賣)", "買進金額", "賣出金額", "買賣差額"], ... ]
    foreign = 0.0
    trust = 0.0
    dealer = 0.0
    for row in data["data"]:
        name = row[0].strip()
        # 買賣差額在第四欄，移除逗號後由元換算為億元
        diff_val = float(row[3].replace(",", "")) / 100000000
        if "外資" in name:
            foreign += diff_val
        elif "投信" in name:
            trust += diff_val
        elif "自營商" in name:
            dealer += diff_val
    return foreign, trust, dealer

# 1. 抓取證交所三大法人每日買賣超資料 (以 2026 年為例)
def fetch_institutional_investors(start_date):
    # 起始日至今日的工作日；已存日期略過，只補尚未下載的日子
    end_date = datetime.today()
    dates = pd.date_range(start=start_date, end=end_date)
    trading_days = [dt for dt in dates if dt.weekday() < 5]

    cache = load_cache()
    cached_dates = set(pd.to_datetime(cache["Date"]).dt.normalize()) if len(cache) else set()
    pending = [dt for dt in trading_days if pd.Timestamp(dt).normalize() not in cached_dates]
    saved_days = int((cache["Status"] == "ok").sum()) if len(cache) else 0
    print(f"已儲存 {saved_days} 個交易日於 {DATA_PATH.name}，尚需下載 {len(pending)} 個工作日。")

    # 證交所「三大法人買賣金額統計表」：dayDate 才會對應到指定交易日
    for index, dt in enumerate(pending, start=1):
        date_str = dt.strftime("%Y%m%d")
        url = (
            "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
            f"?response=json&dayDate={date_str}&weekDate={date_str}"
            f"&monthDate={date_str}&type=day"
        )
        progress = f"[{index}/{len(pending)}] {date_str}"
        print(f"{progress} 下載中...", flush=True)

        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("stat") == "OK" and "data" in data:
                    foreign, trust, dealer = parse_institutional_row(data)
                    cache = remember(cache, dt, "ok", foreign, trust, dealer)
                    saved_days = int((cache["Status"] == "ok").sum())
                    print(
                        f"{progress} 完成，外資: {foreign:.2f}億, 投信: {trust:.2f}億, "
                        f"自營商: {dealer:.2f}億（已儲存 {saved_days} 日）",
                        flush=True,
                    )
                elif dt.date() < datetime.today().date():
                    cache = remember(cache, dt, "closed")
                    print(f"{progress} 無交易資料，已記入快取", flush=True)
                else:
                    print(f"{progress} 今日尚無資料，下次再補", flush=True)
            else:
                print(f"{progress} 下載失敗，HTTP {res.status_code}，下次再補", flush=True)
            # 遵循爬蟲禮儀，每次請求延遲以防被證交所封鎖 IP
            time.sleep(1.5)
        except Exception as e:
            print(f"{progress} 下載失敗: {e}，下次再補", flush=True)

    if pending:
        print(f"下載結束，累計儲存 {int((cache['Status'] == 'ok').sum())} 個交易日。", flush=True)
    else:
        print("籌碼資料已是最新，略過下載。", flush=True)

    ok = cache[cache["Status"] == "ok"] if len(cache) else cache
    if len(ok):
        start_ts = pd.Timestamp(start_date).normalize()
        end_ts = pd.Timestamp(end_date).normalize()
        ok = ok[(ok["Date"] >= start_ts) & (ok["Date"] <= end_ts)]
    if ok.empty:
        print("未能取得 2026 年實際數據，使用模擬數據呈現圖表。")
        df = pd.DataFrame(index=dates)
        df["Foreign"] = 0
        df["Investment_Trust"] = 0
        df["Dealer"] = 0
        return df

    df = ok.set_index("Date").sort_index()
    return df[["Foreign", "Investment_Trust", "Dealer"]]

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
    start_date = datetime(2026, 10, 1)
    df_data = fetch_institutional_investors(start_date)
    plot_institutional_trend(df_data)
