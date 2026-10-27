import json
import os
import time
import requests

# ─── Configuration ───
GATEWAY_URL = "https://gateway.prod.vertexprotocol.com/v1/query"
ARCHIVE_URL = "https://archive.prod.vertexprotocol.com/v1"
DATA_DIR = "data/vertex"
SYMBOLS_TO_FETCH = ["BTC", "ETH", "SOL"]
INTERVAL = 14400  # 4 hours in seconds

def fetch_products():
    print("Fetching product list from Vertex...")
    payload = {"type": "symbols"}
    try:
        r = requests.post(GATEWAY_URL, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("data", [])
        else:
            print(f"Failed to fetch products. Status: {r.status_code}")
            return []
    except Exception as e:
        print(f"Exception fetching products: {e}")
        return []

def fetch_candlesticks(product_id, granularity, limit=500):
    print(f"  Fetching candlesticks for product {product_id} (granularity: {granularity}s)...")
    payload = {
        "type": "candlesticks",
        "product_id": product_id,
        "granularity": granularity,
        "limit": limit
    }
    try:
        r = requests.post(ARCHIVE_URL, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("candlesticks", [])
        else:
            print(f"  Error fetching candles: {r.status_code} - {r.text[:100]}")
            return []
    except Exception as e:
        print(f"  Exception fetching candles: {e}")
        return []

def fetch_funding_history(product_id, limit=500):
    print(f"  Fetching funding history for product {product_id}...")
    payload = {
        "type": "funding_rate",
        "product_id": product_id,
        "limit": limit
    }
    try:
        r = requests.post(ARCHIVE_URL, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("funding_rates", [])
        else:
            print(f"  Error fetching funding: {r.status_code} - {r.text[:100]}")
            return []
    except Exception as e:
        print(f"  Exception fetching funding: {e}")
        return []

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    products = fetch_products()
    if not products:
        print("Could not retrieve product list. Aborting.")
        return
        
    product_map = {}
    for p in products:
        if p.get("symbol") in SYMBOLS_TO_FETCH and p.get("type") == "perp":
            product_map[p["symbol"]] = p["product_id"]
            
    print(f"Target products found: {product_map}")
    
    for symbol, pid in product_map.items():
        print(f"\n--- Processing {symbol} ---")
        
        candles = fetch_candlesticks(pid, INTERVAL)
        if candles:
            for c in candles:
                for key in ["open", "high", "low", "close", "volume"]:
                    if f"{key}_x18" in c:
                        c[key] = float(c[f"{key}_x18"]) / 1e18
            with open(f"{DATA_DIR}/{symbol}_4h.json", "w") as f:
                json.dump(candles, f, indent=2)
            print(f"  Saved {len(candles)} candles for {symbol}.")
            
        funding = fetch_funding_history(pid)
        if funding:
            with open(f"{DATA_DIR}/{symbol}_funding.json", "w") as f:
                json.dump(funding, f, indent=2)
            print(f"  Saved {len(funding)} funding records for {symbol}.")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
