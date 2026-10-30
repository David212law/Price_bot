import requests, time, json, os
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
os.makedirs(DATA_DIR, exist_ok=True)
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_full_funding(symbol):
    print(f"Fetching 1-year funding for {symbol}...")
    end_ms = int(time.time() * 1000)
    start_target_ms = end_ms - (365 * 24 * 60 * 60 * 1000)
    
    all_records = []
    current_end = end_ms
    
    while current_end > start_target_ms:
        current_start = max(current_end - (100 * 8 * 60 * 60 * 1000), start_target_ms)
        url = f"https://api-futures.kucoin.com/api/v1/contract/funding-rates?symbol={symbol}&from={current_start}&to={current_end}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    all_records = data + all_records
                current_end = current_start - 1
            else:
                break
        except Exception as e:
            print(f"Error: {e}")
            break
        time.sleep(0.3)
        
    # حذف تکراری‌ها
    unique = {r["timepoint"]: r for r in all_records}
    sorted_data = [unique[k] for k in sorted(unique.keys())]
    
    filename = f"{DATA_DIR}/{symbol}_funding_full.json"
    with open(filename, "w") as f:
        json.dump(sorted_data, f, indent=2)
    print(f"  ✅ Saved {len(sorted_data)} records to {filename}")

if __name__ == "__main__":
    for sym in SYMBOLS:
        fetch_full_funding(sym)
