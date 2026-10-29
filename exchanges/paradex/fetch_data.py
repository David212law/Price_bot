import requests
import json
import time
from datetime import datetime, timezone

def fetch_klines_4h(symbol="BTC-USD-PERP", limit=100):
    """دریافت کندل‌های ۱ ساعته و تجمیع به ۴ ساعته"""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (limit * 4 * 60 * 60 * 1000)  # limit * 4 ساعت
    
    url = f"https://api.prod.paradex.trade/v1/markets/klines?symbol={symbol}&resolution=60&start_at={start_ms}&end_at={end_ms}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            raw = r.json().get("results", [])
            if not raw:
                print(f"  [{symbol}] No klines returned.")
                return []
            
            # تجمیع ۴ کندل ۱ ساعته به یک کندل ۴ ساعته
            candles_4h = []
            for i in range(0, len(raw) - 3, 4):
                chunk = raw[i:i+4]
                if len(chunk) < 4: break
                t = chunk[0][0]
                o = float(chunk[0][1])
                h = max(float(c[2]) for c in chunk)
                l = min(float(c[3]) for c in chunk)
                c = float(chunk[-1][4])
                v = sum(float(x[5]) for x in chunk)
                candles_4h.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
            
            print(f"  [{symbol}] Aggregated {len(candles_4h)} candles (4H).")
            if candles_4h:
                print(f"    Latest: {datetime.fromtimestamp(candles_4h[-1]['t']/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')} | Close: {candles_4h[-1]['c']}")
            return candles_4h
        else:
            print(f"  [{symbol}] Klines failed: {r.status_code}")
    except Exception as e:
        print(f"  [{symbol}] Klines exception: {e}")
    return []

def fetch_funding(symbol="BTC-USD-PERP", limit=10):
    url = f"https://api.prod.paradex.trade/v1/funding/data?market={symbol}&page_size={limit}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json().get("results", [])
            print(f"  [{symbol}] Received {len(data)} funding records.")
            if data:
                latest = data[-1]
                print(f"    Latest: {latest['created_at']} | Rate: {latest['funding_rate']} | Period: {latest['funding_period_hours']}h")
            return data
    except Exception as e:
        print(f"  [{symbol}] Funding exception: {e}")
    return []

def main():
    print("=== Paradex Data Collector (4H Klines + Funding) ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    
    for sym in ["BTC-USD-PERP", "ETH-USD-PERP", "SOL-USD-PERP"]:
        print(f"--- {sym} ---")
        fetch_klines_4h(sym, limit=30)
        fetch_funding(sym, limit=5)
        print()

if __name__ == "__main__":
    main()
