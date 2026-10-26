import requests
import time

# ─── Endpoints to test ───
endpoints = [
    "https://api.exir.io/v1/udf/history",
    "https://api.exir.io/v2/udf/history",
    "https://api.exir.io/v1/chart",
    "https://api.exir.io/v2/chart",
    "https://api.exir.io/v1/ohlc",
    "https://api.exir.io/v2/ohlc",
    "https://api.exir.io/v1/candles",
    "https://api.exir.io/v2/candles",
    "https://api.exir.io/v1/market/candles",
    "https://api.exir.io/v2/market/candles",
    "https://api.exir.io/v1/market/ohlc",
    "https://api.exir.io/v2/market/ohlc"
]

# ─── Test Parameters ───
symbols = ["btc-usdt", "BTC-USDT", "btc_usdt", "BTC_USDT"]
resolutions = ["240", "4h", "4H"]
now = int(time.time())
start = now - (7 * 24 * 3600) # Just 7 days for test

def test_url(url):
    for sym in symbols:
        for res in resolutions:
            params = {
                "symbol": sym,
                "resolution": res,
                "from": start,
                "to": now
            }
            try:
                r = requests.get(url, params=params, timeout=5)
                # If status is 200 and response is not an error message
                if r.status_code == 200:
                    resp_text = r.text[:150].replace('\n', ' ')
                    if "error" not in resp_text.lower() and "not found" not in resp_text.lower() and resp_text.strip() != "":
                        print(f"\n✅ SUCCESS: {url}")
                        print(f"   Params: symbol={sym}, resolution={res}")
                        print(f"   Response: {resp_text}...")
                        return True
            except Exception:
                pass
    return False

def main():
    print("=== Probing Exir API Endpoints ===")
    print("Testing multiple URLs, symbols, and resolutions...\n")
    
    found = False
    for url in endpoints:
        print(f"Testing: {url}")
        if test_url(url):
            found = True
            break # Stop when we find a working endpoint
            
    if not found:
        print("\n❌ No working endpoint found among the tested URLs.")
        print("We may need to test POST requests or other structures.")

if __name__ == "__main__":
    main()
