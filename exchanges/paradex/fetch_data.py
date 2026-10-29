import requests
import json
import time
from datetime import datetime

def fetch_klines(symbol="BTC-USD-PERP", interval="4h", limit=10):
    url = f"https://api.prod.paradex.trade/v1/markets/klines?symbol={symbol}&resolution={interval}&limit={limit}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"[{symbol}] Received {len(data)} candles.")
            if data:
                print(f"  Latest candle: {datetime.utcfromtimestamp(data[-1][0]/1000).strftime('%Y-%m-%d %H:%M')} | Close: {data[-1][4]}")
            return data
    except Exception as e:
        print(f"Error fetching klines: {e}")
    return []

def fetch_funding(symbol="BTC-USD-PERP", limit=10):
    url = f"https://api.prod.paradex.trade/v1/funding/data?market={symbol}&page_size={limit}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json().get("results", [])
            print(f"[{symbol}] Received {len(data)} funding records.")
            if data:
                print(f"  Latest funding: {data[-1]['created_at']} | Rate: {data[-1]['funding_rate']}")
            return data
    except Exception as e:
        print(f"Error fetching funding: {e}")
    return []

def main():
    print("=== Paradex Data Collector Test ===")
    print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    
    # تست برای ۳ ارز اصلی
    for sym in ["BTC-USD-PERP", "ETH-USD-PERP", "SOL-USD-PERP"]:
        fetch_klines(sym, "4h", 5)
        fetch_funding(sym, 5)
        print("-" * 40)

if __name__ == "__main__":
    main()
