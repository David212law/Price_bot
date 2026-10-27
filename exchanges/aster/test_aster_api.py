import requests
import time
from datetime import datetime, timezone

def test_aster_klines():
    print("=== Testing Aster API (Klines) ===")
    # Aster Futures API (similar to Binance)
    url = "https://fapi.asterdex.com/fapi/v1/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 10}
    
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            print("✅ Aster Klines API is accessible!")
            print(f"Response (first 200 chars): {r.text[:200]}")
            return True
        else:
            print(f"❌ Aster API returned status {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
    return False

def test_aster_funding():
    print("\n=== Testing Aster API (Funding Rates) ===")
    url = "https://fapi.asterdex.com/fapi/v1/premiumIndex"
    params = {"symbol": "BTCUSDT"}
    
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            print("✅ Aster Funding Rates accessible!")
            print(f"Response (first 200 chars): {r.text[:200]}")
        else:
            print(f"❌ Status {r.status_code} | {r.text[:200]}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_aster_klines()
    test_aster_funding()
