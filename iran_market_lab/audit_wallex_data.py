import json
import os
from datetime import datetime, timezone

DATA_DIR = "data_tetri"
ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"]
FOUR_HOURS_MS = 4 * 3600 * 1000

def audit_file(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path):
        return f"[{symbol}] File not found."
        
    with open(path, 'r') as f:
        candles = json.load(f)
        
    if not candles:
        return f"[{symbol}] Empty data."
        
    n_total = len(candles)
    unique_ts = set(c["t"] for c in candles)
    n_unique = len(unique_ts)
    
    first_ts = candles[0]["t"]
    last_ts = candles[-1]["t"]
    
    first_date = datetime.fromtimestamp(first_ts/1000, timezone.utc).strftime('%Y-%m-%d')
    last_date = datetime.fromtimestamp(last_ts/1000, timezone.utc).strftime('%Y-%m-%d')
    
    # Check for gaps
    gaps = 0
    zero_vol = 0
    flat_candles = 0
    
    prev_t = first_ts
    for c in candles:
        if c["v"] == 0: zero_vol += 1
        if c["o"] == c["c"] == c["h"] == c["l"]: flat_candles += 1
        
        diff = c["t"] - prev_t
        if diff > FOUR_HOURS_MS:
            gaps += 1
        prev_t = c["t"]
        
    gap_pct = (gaps / n_total) * 100
    zero_pct = (zero_vol / n_total) * 100
    flat_pct = (flat_candles / n_total) * 100
    
    return (f"[{symbol}] Total: {n_total} | Unique: {n_unique} | "
            f"From {first_date} to {last_date} | Gaps: {gaps} ({gap_pct:.2f}%) | "
            f"ZeroVol: {zero_vol} ({zero_pct:.2f}%) | Flat: {flat_candles} ({flat_pct:.2f}%)")

def main():
    print("=== Data Audit Report (D-116) ===")
    for sym in ASSETS:
        print(audit_file(sym))
        
if __name__ == "__main__":
    main()
