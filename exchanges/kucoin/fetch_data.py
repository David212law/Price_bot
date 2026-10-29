import requests
import time
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def test_kucoin_spot_klines():
    print("--- KuCoin Spot Klines (BTC-USDT, 4H) ---")
    url = "https://api.kucoin.com/api/v1/market/candles?type=4hour&symbol=BTC-USDT"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"  ✅ Received {len(data)} candles.")
            if data:
                latest = data[0]
                dt = datetime.fromtimestamp(int(latest[0]), tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                print(f"  Latest Candle: {dt} | Close: {latest[2]}")
        else:
            print(f"  ❌ Failed: {r.status_code}")
    except Exception as e:
        print(f"  Exception: {e}")

def test_kucoin_futures_klines():
    print("--- KuCoin Futures Klines (XBTUSDTM, 4H) ---")
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (10 * 4 * 60 * 60 * 1000)
    url = f"https://api-futures.kucoin.com/api/v1/kline/query?symbol=XBTUSDTM&granularity=240&from={start_ms}&to={now_ms}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            print(f"  ✅ Received {len(data)} futures candles.")
            if data:
                latest = data[-1]
                dt = datetime.fromtimestamp(latest[0] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                print(f"  Latest Candle: {dt} | Close: {latest[4]}")
        else:
            print(f"  ❌ Failed: {r.status_code}")
    except Exception as e:
        print(f"  Exception: {e}")

def test_kucoin_funding():
    print("--- KuCoin Futures Current Funding Rate (XBTUSDTM) ---")
    # اصلاح اندپوینت: استفاده از /api/v1/funding-rate/{symbol}/current طبق مستندات
    url = "https://api-futures.kucoin.com/api/v1/funding-rate/XBTUSDTM/current"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data:
                print(f"  ✅ SUCCESS!")
                print(f"  Current Funding Rate: {float(data.get('value', 0)) * 100:.4f}%")
                print(f"  Granularity: {data.get('granularity')} ms ({data.get('granularity')/3600000} hours)")
        else:
            print(f"  ❌ Failed: {r.status_code} | Response: {r.text[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

if __name__ == "__main__":
    print(f"=== KuCoin Data Collector Test ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    test_kucoin_spot_klines()
    print()
    test_kucoin_futures_klines()
    print()
    test_kucoin_funding()
