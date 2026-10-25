import os
import json
import time
import requests

# ─── Configuration ───
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", 
    "DOGEUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"
]

DATA_DIR = "data_tetri"
DAYS = 730 # 2 years

def fetch_wallex_tetri(symbol, days=DAYS):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = f"{DATA_DIR}/{symbol}_4h.json"
    
    now = int(time.time())
    start = now - (days * 24 * 3600)
    chunk = 14 * 24 * 3600 # 14 days per request
    raw_candles = []
    current = start
    
    print(f"[{symbol}] Fetching 1H data to resample to 4H...")
    
    while current < now:
        to_ts = min(current + chunk, now)
        url = f"https://api.wallex.ir/v1/udf/history?symbol={symbol}&resolution=60&from={current}&to={to_ts}"
        
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get('s') == 'ok':
                    for i in range(len(data['t'])):
                        raw_candles.append({
                            "t": int(data['t'][i]) * 1000,
                            "o": float(data['o'][i]),
                            "h": float(data['h'][i]),
                            "l": float(data['l'][i]),
                            "c": float(data['c'][i]),
                            "v": float(data['v'][i])
                        })
        except Exception as e:
            print(f"  Error at chunk {current}: {e}")
            
        current = to_ts
        time.sleep(0.3)
        
    unique = {c['t']: c for c in raw_candles}
    sorted_1h = sorted(list(unique.values()), key=lambda x: x['t'])
    
    # ─── Resample 1H to 4H ───
    resampled_4h = []
    for i in range(0, len(sorted_1h), 4):
        chunk_1h = sorted_1h[i:i+4]
        if not chunk_1h: continue
        
        c_4h = {
            "t": chunk_1h[0]["t"],
            "o": chunk_1h[0]["o"],
            "h": max(c["h"] for c in chunk_1h),
            "l": min(c["l"] for c in chunk_1h),
            "c": chunk_1h[-1]["c"],
            "v": sum(c["v"] for c in chunk_1h)
        }
        resampled_4h.append(c_4h)
        
    with open(filepath, 'w') as f:
        json.dump(resampled_4h, f, indent=2)
        
    print(f"[{symbol}] Saved {len(resampled_4h)} (4H) candles to {filepath}")

def main():
    print("=== Wallex Tetri (USDT) Data Adapter (Fixed to 4H) ===")
    for sym in SYMBOLS:
        fetch_wallex_tetri(sym)
    print("=== Done ===")

if __name__ == "__main__":
    main()
