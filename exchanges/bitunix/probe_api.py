import requests
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def probe_endpoint(name, url, is_post=False, payload=None):
    print(f"Testing {name} ({url})...")
    try:
        start_time = time.time()
        if is_post:
            r = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        else:
            r = requests.get(url, headers=HEADERS, timeout=10)
            
        latency = (time.time() - start_time) * 1000
        print(f"  [Status: {r.status_code}] Latency: {latency:.0f}ms")
        
        if r.status_code == 200:
            print(f"  ✅ SUCCESS! Response (truncated): {r.text[:80]}...")
        else:
            print(f"  ❌ Blocked/Error: {r.text[:100].replace(chr(10), ' ')}")
            
    except Exception as e:
        print(f"  [Failed] Exception: {str(e)[:100]}")
    print("-" * 50)

def main():
    print("=== Bitunix (with UA) & Toobit Probe ===")
    print("=" * 50)
    
    # 1. Hyperliquid (Control - POST method)
    probe_endpoint("Hyperliquid Control", "https://api.hyperliquid.xyz/info", is_post=True, payload={"type": "meta"})
    
    # 2. Bitunix (with User-Agent)
    probe_endpoint("Bitunix Tickers (with UA)", "https://api.bitunix.com/api/v1/futures/market/tickers")
    
    # 3. Toobit API (Spot & Futures)
    probe_endpoint("Toobit Spot Tickers", "https://api.toobit.com/api/v1/public/tickers")
    probe_endpoint("Toobit Futures Klines", "https://api.toobit.com/api/v1/futures/market/kline?symbol=BTCUSDT&interval=4h&limit=5")

if __name__ == "__main__":
    main()
