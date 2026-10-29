import requests
import json
import time
import os
from datetime import datetime, timezone

DATA_DIR = "exchanges/paradex/data"
os.makedirs(DATA_DIR, exist_ok=True)

SYMBOLS = ["BTC-USD-PERP", "ETH-USD-PERP", "SOL-USD-PERP", "BNB-USD-PERP", "AVAX-USD-PERP", "XRP-USD-PERP"]
DAYS_BACK = 365 # دریافت ۱ سال داده
CHUNK_SIZE = 1000 # حداکثر کندل ۱ ساعته در هر درخواست

def fetch_historical_klines(symbol):
    print(f"Fetching history for {symbol} ({DAYS_BACK} days)...")
    end_ms = int(time.time() * 1000)
    start_target_ms = end_ms - (DAYS_BACK * 24 * 60 * 60 * 1000)
    
    all_raw_1h = []
    current_end = end_ms
    
    while current_end > start_target_ms:
        # محاسبه شروع برای این چانک
        current_start = max(current_end - (CHUNK_SIZE * 60 * 60 * 1000), start_target_ms)
        
        url = f"https://api.prod.paradex.trade/v1/markets/klines?symbol={symbol}&resolution=60&start_at={current_start}&end_at={current_end}"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                results = r.json().get("results", [])
                if not results:
                    break
                all_raw_1h = results + all_raw_1h
                # یک ساعت عقب برمی‌گردیم تا از دریافت تکراری جلوگیری شود
                current_end = int(results[0][0]) - (60 * 60 * 1000)
            else:
                print(f"  Error fetching chunk: {r.status_code}")
                break
        except Exception as e:
            print(f"  Exception: {e}")
            break
        
        time.sleep(0.5) # جلوگیری از Rate Limit
        
    # تجمیع به ۴ ساعته
    print(f"  Aggregating {len(all_raw_1h)} 1H candles into 4H...")
    candles_4h = []
    for i in range(0, len(all_raw_1h) - 3, 4):
        chunk = all_raw_1h[i:i+4]
        t = chunk[0][0]
        o = float(chunk[0][1])
        h = max(float(c[2]) for c in chunk)
        l = min(float(c[3]) for c in chunk)
        c = float(chunk[-1][4])
        v = sum(float(x[5]) for x in chunk)
        candles_4h.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
        
    # ذخیره با متادیتای D-50
    output = {
        "metadata": {
            "source": "Paradex API v1",
            "symbol": symbol,
            "resolution": "4h",
            "fetched_at": datetime.now(timezone.utc).isoformat()
        },
        "candles": candles_4h
    }
    filename = f"{DATA_DIR}/{symbol.replace('-', '_')}_4h.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved {len(candles_4h)} candles to {filename}")

def fetch_funding_history(symbol):
    url = f"https://api.prod.paradex.trade/v1/funding/data?market={symbol}&page_size=1000"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json().get("results", [])
            filename = f"{DATA_DIR}/{symbol.replace('-', '_')}_funding.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  Saved {len(data)} funding records to {filename}")
    except Exception as e:
        print(f"  Funding exception: {e}")

def main():
    print("=== Paradex Deep History Builder ===")
    for sym in SYMBOLS:
        fetch_historical_klines(sym)
        fetch_funding_history(sym)
        print("-" * 40)

if __name__ == "__main__":
    main()
