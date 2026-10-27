import json
import os
import time
import requests

# ─── Configuration ───
BASE_URL = "https://fapi.asterdex.com/fapi/v1"
DATA_DIR = "data/aster"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"]
INTERVAL = "4h"
DAYS = 730

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_klines(symbol, days=DAYS):
    print(f"[{symbol}] Fetching {INTERVAL} klines...")
    all_candles = []
    end_time = int(time.time() * 1000)
    start_time = end_time - (days * 24 * 3600 * 1000)
    current_end = end_time
    
    while current_end > start_time:
        url = f"{BASE_URL}/klines"
        params = {"symbol": symbol, "interval": INTERVAL, "limit": 1000, "endTime": current_end}
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for k in data:
                    all_candles.append({
                        "t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                        "l": float(k[3]), "c": float(k[4]), "v": float(k[5])
                    })
                current_end = data[0][0] - 1
            else:
                print(f"  Error: {r.status_code}")
                break
        except Exception as e:
            print(f"  Exception: {e}")
            break
        time.sleep(0.2)
    
    unique = {c["t"]: c for c in all_candles}
    sorted_c = sorted(unique.values(), key=lambda x: x["t"])
    print(f"  → {len(sorted_c)} candles")
    return sorted_c

def fetch_funding(symbol, days=DAYS):
    print(f"[{symbol}] Fetching funding history...")
    all_records = []
    end_time = int(time.time() * 1000)
    start_time = end_time - (days * 24 * 3600 * 1000)
    current_end = end_time
    
    while current_end > start_time:
        url = f"{BASE_URL}/fundingRate"
        params = {"symbol": symbol, "limit": 1000, "endTime": current_end}
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for rec in data:
                    all_records.append({
                        "t": int(rec["fundingTime"]),
                        "rate": float(rec["fundingRate"])
                    })
                current_end = data[0]["fundingTime"] - 1
            else:
                print(f"  Error: {r.status_code}")
                break
        except Exception as e:
            print(f"  Exception: {e}")
            break
        time.sleep(0.2)
    
    unique = {r["t"]: r for r in all_records}
    sorted_r = sorted(unique.values(), key=lambda x: x["t"])
    print(f"  → {len(sorted_r)} funding records")
    return sorted_r

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"=== Aster Data Adapter ===\n")
    
    for sym in SYMBOLS:
        # Skip if already exists (to save time in future runs)
        kline_path = f"{DATA_DIR}/{sym}_4h.json"
        fund_path = f"{DATA_DIR}/{sym}_funding.json"
        
        if os.path.exists(kline_path) and os.path.exists(fund_path):
            print(f"[{sym}] Data exists, skipping.\n")
            continue
        
        klines = fetch_klines(sym)
        with open(kline_path, "w") as f: json.dump(klines, f)
        
        funding = fetch_funding(sym)
        with open(fund_path, "w") as f: json.dump(funding, f)
        
        print(f"[{sym}] ✅ Complete\n")
        time.sleep(1)
    
    print("=== Done ===")

if __name__ == "__main__":
    main()
