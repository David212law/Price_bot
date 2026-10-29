import requests
import time
from datetime import datetime

def test_klines_format(symbol, resolution):
    # تست دو نوع اندپوینت رایج
    urls = [
        f"https://api.prod.paradex.trade/v1/markets/klines?symbol={symbol}&resolution={resolution}&limit=5",
        f"https://api.prod.paradex.trade/v1/klines?symbol={symbol}&resolution={resolution}&limit=5"
    ]
    
    for url in urls:
        print(f"Testing URL: {url}")
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    print(f"  ✅ SUCCESS! Found {len(data)} candles.")
                    # نمایش اولین کندل برای بررسی ساختار
                    print(f"  Sample: {data[0]}")
                    return True
                else:
                    print("  ❌ Empty response (200 OK but no data).")
            else:
                print(f"  ❌ Failed with status: {r.status_code}")
        except Exception as e:
            print(f"  ❌ Exception: {e}")
    return False

def main():
    print("=== Paradex Klines Format Diagnostic ===\n")
    symbol = "BTC-USD-PERP"
    
    # لیست فرمت‌های احتمالی برای ۴ ساعت
    resolutions = ["4h", "240", "4H", "1h", "60", "1d", "1D"]
    
    for res in resolutions:
        print(f"--- Testing resolution: '{res}' ---")
        if test_klines_format(symbol, res):
            print(f"\n🎉 Correct format found: {res}\n")
            break
        print("-" * 40)

if __name__ == "__main__":
    main()
