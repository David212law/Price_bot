import requests
import time
from datetime import datetime, timezone

# ─── Configuration ───
# Hyperliquid uses coin base names (BTC, ETH, SOL)
SYMBOLS = ["BTC", "ETH", "SOL"]
INTERVAL = "4h"
DAYS = 30 # Just 30 days for connection test

def fetch_hyperliquid_data(symbol):
    print(f"[{symbol}] Fetching {INTERVAL} data from Hyperliquid...")
    
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (DAYS * 24 * 3600 * 1000)
    
    url = "https://api.hyperliquid.xyz/info"
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": symbol,
            "interval": INTERVAL,
            "startTime": start_ms,
            "endTime": now_ms
        }
    }
    
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"✅ [{symbol}] Successfully received {len(data)} candles.")
                # Print first and last candle to verify
                first = data[0]
                last = data[-1]
                print(f"   First candle time: {datetime.fromtimestamp(first['t']/1000, timezone.utc).strftime('%Y-%m-%d %H:%M')} | Close: {first['c']}")
                print(f"   Last candle time:  {datetime.fromtimestamp(last['t']/1000, timezone.utc).strftime('%Y-%m-%d %H:%M')} | Close: {last['c']}")
                return True
            else:
                print(f"⚠️ [{symbol}] Empty data or invalid format. Response: {r.text[:200]}")
        else:
            print(f"❌ [{symbol}] Failed. Status: {r.status_code} | Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ [{symbol}] Exception: {e}")
        
    return False

def main():
    print("=== Hyperliquid API Connection Test ===\n")
    success_count = 0
    for sym in SYMBOLS:
        if fetch_hyperliquid_data(sym):
            success_count += 1
        print() # empty line
        
    if success_count == len(SYMBOLS):
        print("✅ All tests passed! Hyperliquid API is accessible.")
    else:
        print("❌ Some tests failed. Check the logs above.")

if __name__ == "__main__":
    main()
