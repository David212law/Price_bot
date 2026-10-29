import requests
import time

def probe_endpoint(name, url):
    print(f"Testing {name} ({url})...")
    try:
        start_time = time.time()
        r = requests.get(url, timeout=10)
        latency = (time.time() - start_time) * 1000
        print(f"  [Status: {r.status_code}] Latency: {latency:.0f}ms")
        if r.status_code == 200:
            print(f"  Response (truncated): {r.text[:80]}...")
        else:
            print(f"  Blocked/Error Response: {r.text[:100]}")
    except requests.exceptions.ConnectionError as ce:
        if "NameResolutionError" in str(ce) or "Failed to resolve" in str(ce):
            print(f"  [DNS Error] Failed to resolve hostname.")
        else:
            print(f"  [Connection Error] {str(ce)[:100]}")
    except Exception as e:
        print(f"  [Failed] Exception: {str(e)[:100]}")
    print("-" * 50)

def main():
    print("=== Broad DEX Connectivity Probe ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 50)
    
    endpoints = [
        # شاهد (برای اطمینان از صحت شبکه)
        ("Hyperliquid (Control)", "https://api.hyperliquid.xyz/info"),
        
        # کاندیداهای جدید
        ("Paradex API", "https://api.prod.paradex.trade/v1/markets"),
        ("dYdX Indexer API", "https://indexer.dydx.trade/v4/markets"),
        ("Aevo API", "https://api.aevo.xyz/markets"),
        ("Drift Data API", "https://data.api.drift.trade/stats/markets")
    ]
    
    for name, url in endpoints:
        probe_endpoint(name, url)

if __name__ == "__main__":
    main()
