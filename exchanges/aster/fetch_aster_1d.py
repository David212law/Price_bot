import json, os, time, requests

BASE_URL = "https://fapi.asterdex.com/fapi/v1"
DATA_DIR = "data/aster"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"]

def fetch_klines(symbol, interval="1d", limit=500):
    print(f"[{symbol}] Fetching {interval} klines...")
    url = f"{BASE_URL}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in r.json()]
    except Exception as e:
        print(f"  Error: {e}")
    return []

def main():
    for sym in SYMBOLS:
        path = f"{DATA_DIR}/{sym}_1d.json"
        if os.path.exists(path):
            print(f"[{sym}] 1D data exists, skipping.")
            continue
        candles = fetch_klines(sym)
        with open(path, "w") as f: json.dump(candles, f)
        print(f"  → {len(candles)} candles")
        time.sleep(1)

if __name__ == "__main__":
    main()
