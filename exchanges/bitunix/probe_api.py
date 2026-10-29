import requests
import time
import json

def probe_endpoint(name, url):
    print(f"Testing {name} ({url})...")
    try:
        start_time = time.time()
        r = requests.get(url, timeout=10)
        latency = (time.time() - start_time) * 1000
        print(f"  [Status: {r.status_code}] Latency: {latency:.0f}ms")
        if r.status_code == 200:
            # بررسی ساختار پاسخ برای اطمینان از صحت داده
            data = r.json()
            print(f"  ✅ SUCCESS! Response code: {data.get('code', 'N/A')}")
            if 'data' in data and len(data['data']) > 0:
                print(f"  Sample data (truncated): {str(data['data'][0])[:100]}...")
        else:
            print(f"  ❌ Blocked/Error Response: {r.text[:150]}")
    except requests.exceptions.ConnectionError as ce:
        print(f"  [Connection Error] {str(ce)[:100]}")
    except Exception as e:
        print(f"  [Failed] Exception: {str(e)[:100]}")
    print("-" * 50)

def main():
    print("=== Bitunix Public API Probe ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 50)
    
    endpoints = [
        # شاهد
        ("Hyperliquid (Control)", "https://api.hyperliquid.xyz/info"),
        
        # Bitunix Endpoints
        ("Bitunix Tickers", "https://api.bitunix.com/api/v1/futures/market/tickers"),
        ("Bitunix Klines", "https://api.bitunix.com/api/v1/futures/market/kline?symbol=BTCUSDT&interval=4h&limit=5"),
        ("Bitunix Funding", "https://api.bitunix.com/api/v1/futures/market/funding_rate?symbol=BTCUSDT")
    ]
    
    for name, url in endpoints:
        probe_endpoint(name, url)

if __name__ == "__main__":
    main()
