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
            # فقط چند کاراکتر اول پاسخ را چاپ می‌کنیم تا از حجم لاگ جلوگیری شود
            print(f"  Response: {r.text[:150]}...")
        else:
            print(f"  Blocked/Error Response: {r.text[:150]}")
    except Exception as e:
        print(f"  [Failed] Exception: {e}")
    print("-" * 50)

def main():
    print("=== Lighter API Connectivity Probe (GitHub Actions) ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 50)
    
    # لیست اندپوینت‌های عمومی برای تست (بر اساس مستندات عمومی DEXها)
    endpoints = [
        ("Base Info", "https://api.lighter.xyz/api/v1/info"),
        ("Markets", "https://api.lighter.xyz/api/v1/markets"),
        ("Klines (BTC)", "https://api.lighter.xyz/api/v1/klines?symbol=BTC-USD&interval=4h&limit=5"),
        ("Funding Rates", "https://api.lighter.xyz/api/v1/funding-rates?symbol=BTC-USD")
    ]
    
    for name, url in endpoints:
        probe_endpoint(name, url)

if __name__ == "__main__":
    main()
