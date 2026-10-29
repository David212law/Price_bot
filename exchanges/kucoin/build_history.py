import requests
import json
import time
import os
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# نمادهای فیوچرز KuCoin (نکته: بیت‌کوین در KuCoin با XBT نمایش داده می‌شود)
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
DAYS_BACK = 365
CHUNK_MS = 10 * 24 * 60 * 60 * 1000 # دریافت ۱۰ روز در هر درخواست (برای جلوگیری از Rate Limit)

def fetch_historical_klines(symbol):
    print(f"Fetching history for {symbol} ({DAYS_BACK} days)...")
    end_ms = int(time.time() * 1000)
    start_target_ms = end_ms - (DAYS_BACK * 24 * 60 * 60 * 1000)
    
    all_candles = []
    current_end = end_ms
    
    while current_end > start_target_ms:
        current_start = max(current_end - CHUNK_MS, start_target_ms)
        
        url = f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=240&from={current_start}&to={current_end}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    # KuCoin returns newest first, we need to reverse and prepend
                    all_candles = data + all_candles
                current_end = current_start - 1 # یک میلی‌ثانیه عقب برای جلوگیری از تکرار
            else:
                print(f"  Error fetching chunk: {r.status_code}")
                time.sleep(2)
                continue
        except Exception as e:
            print(f"  Exception: {e}")
            time.sleep(2)
            continue
            
        time.sleep(0.3) # جلوگیری از مسدود شدن
        
    # حذف تکراری‌ها (بر اساس timestamp)
    unique_candles = {}
    for c in all_candles:
        unique_candles[c[0]] = c
    
    sorted_candles = [unique_candles[k] for k in sorted(unique_candles.keys())]
    
    # تبدیل به فرمت استاندارد ما
    formatted_candles = []
    for c in sorted_candles:
        formatted_candles.append({
            "t": int(c[0]), 
            "o": float(c[1]), 
            "h": float(c[2]), 
            "l": float(c[3]), 
            "c": float(c[4]), 
            "v": float(c[5])
        })
        
    output = {
        "metadata": {
            "source": "KuCoin Futures API",
            "symbol": symbol,
            "resolution": "4h",
            "fetched_at": datetime.now(timezone.utc).isoformat()
        },
        "candles": formatted_candles
    }
    
    filename = f"{DATA_DIR}/{symbol}_4h.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved {len(formatted_candles)} candles to {filename}")

def fetch_funding_history(symbol):
    print(f"Fetching funding history for {symbol}...")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (DAYS_BACK * 24 * 60 * 60 * 1000)
    
    url = f"https://api-futures.kucoin.com/api/v1/contract/funding-rates?symbol={symbol}&from={start_ms}&to={end_ms}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            filename = f"{DATA_DIR}/{symbol}_funding.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  Saved {len(data)} funding records to {filename}")
        else:
            print(f"  Failed to fetch funding: {r.status_code}")
    except Exception as e:
        print(f"  Funding exception: {e}")

def main():
    print(f"=== KuCoin Deep History Builder ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    for sym in SYMBOLS:
        fetch_historical_klines(sym)
        fetch_funding_history(sym)
        print("-" * 40)

if __name__ == "__main__":
    main()
