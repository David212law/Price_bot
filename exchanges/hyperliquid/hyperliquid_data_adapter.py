import os
import json
import requests
import time
from datetime import datetime, timezone

# لیست کامل ارزها (شامل ۳ ارز جدید)
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "DOGE", "ADA", "LINK"]
DATA_DIR = "data/hyperliquid"
DAYS = 730

def fetch_ohlcv(symbol, interval, days=DAYS):
    print(f"[{symbol}] Fetching {interval} OHLCV...")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    all_candles = []
    current_end = end_ms
    chunk_seconds = 30 * 24 * 3600 * 1000
    
    while current_end > start_ms:
        current_start = max(start_ms, current_end - chunk_seconds)
        payload = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": interval, "startTime": current_start, "endTime": current_end}}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for c in data:
                    all_candles.append({"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"]), "v": float(c["v"])})
                earliest = min(int(c["t"]) for c in data)
                current_end = earliest - 1
            elif r.status_code == 429:
                time.sleep(5)
                continue
        except Exception as e:
            print(f"  Exception: {e}")
            break
        time.sleep(0.5)
        
    unique = {c["t"]: c for c in all_candles}
    sorted_candles = sorted(unique.values(), key=lambda x: x["t"])
    print(f"  → {len(sorted_candles)} candles")
    return sorted_candles

def fetch_funding(symbol, days=DAYS):
    print(f"[{symbol}] Fetching funding history...")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    all_records = []
    current_end = end_ms
    chunk_seconds = 30 * 24 * 3600 * 1000
    
    while current_end > start_ms:
        current_start = max(start_ms, current_end - chunk_seconds)
        payload = {"type": "fundingHistory", "coin": symbol, "startTime": current_start, "endTime": current_end}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for rec in data:
                    all_records.append({"t": int(rec["time"]), "rate": float(rec["fundingRate"])})
                earliest = min(int(rec["time"]) for rec in data)
                current_end = earliest - 1
            elif r.status_code == 429:
                time.sleep(5)
                continue
        except Exception as e:
            print(f"  Exception: {e}")
            break
        time.sleep(1.5)
        
    unique = {r["t"]: r for r in all_records}
    sorted_records = sorted(unique.values(), key=lambda x: x["t"])
    print(f"  → {len(sorted_records)} funding records")
    return sorted_records

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"=== Hyperliquid Data Adapter (All Assets) ===")
    print(f"Target: {len(SYMBOLS)} symbols × (4H + 1D + Funding)\n")
    
    for sym in SYMBOLS:
        # 4H OHLCV
        candles_4h = fetch_ohlcv(sym, "4h")
        with open(f"{DATA_DIR}/{sym}_4h.json", "w") as f: json.dump(candles_4h, f)
        
        # 1D OHLCV
        candles_1d = fetch_ohlcv(sym, "1d")
        with open(f"{DATA_DIR}/{sym}_1d.json", "w") as f: json.dump(candles_1d, f)
        
        # Funding
        funding = fetch_funding(sym)
        with open(f"{DATA_DIR}/{sym}_funding.json", "w") as f: json.dump(funding, f)
        
        print(f"[{sym}] ✅ Complete\n")
    
    print("=== Done ===")

if __name__ == "__main__":
    main()
