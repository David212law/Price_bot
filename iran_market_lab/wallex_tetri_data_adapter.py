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
RESOLUTION = "240" # 4 hours
DAYS = 730 # 2 years

def fetch_wallex_tetri(symbol, days=DAYS):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = f"{DATA_DIR}/{symbol}_4h.json"
    
    if os.path.exists(filepath):
        print(f"[{symbol}] Data already exists. Skipping.")
        return

    now = int(time.time())
    start = now - (days * 24 * 3600)
    chunk = 14 * 24 * 3600 # 14 days per request
    candles = []
    current = start
    
    print(f"[{symbol}] Fetching data from Wallex Tetri market...")
    
    while current < now:
        to_ts = min(current + chunk, now)
        url = f"https://api.wallex.ir/v1/udf/history?symbol={symbol}&resolution={RESOLUTION}&from={current}&to={to_ts}"
        
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get('s') == 'ok':
                    for i in range(len(data['t'])):
                        candles.append({
                            "t": int(data['t'][i]) * 1000, # Convert to ms
                            "o": float(data['o'][i]),
                            "h": float(data['h'][i]),
                            "l": float(data['l'][i]),
                            "c": float(data['c'][i]),
                            "v": float(data['v'][i])
                        })
        except Exception as e:
            print(f"  Error at chunk {current}: {e}")
            
        current = to_ts
        time.sleep(0.3) # Rate limit prevention
        
    # Deduplicate and sort
    unique = {c['t']: c for c in candles}
    sorted_candles = sorted(list(unique.values()), key=lambda x: x['t'])
    
    with open(filepath, 'w') as f:
        json.dump(sorted_candles, f, indent=2)
        
    print(f"[{symbol}] Saved {len(sorted_candles)} candles to {filepath}")

def main():
    print("=== Wallex Tetri (USDT) Data Adapter ===")
    for sym in SYMBOLS:
        fetch_wallex_tetri(sym)
    print("=== Done ===")

if __name__ == "__main__":
    main()
