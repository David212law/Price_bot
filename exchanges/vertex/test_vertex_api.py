import requests
import time
from datetime import datetime, timezone

def test_vertex_candles():
    print("=== Testing Vertex API (Candles) ===")
    # Vertex uses an indexer. We try to fetch BTC-PERP candles.
    url = "https://api.vertexprotocol.com/v1/query"
    # Payload for Vertex indexer GraphQL-like API
    payload = {
        "type": "candles",
        "product_id": 1, # 1 is usually BTC-PERP
        "granularity": 3600, # 1 hour
        "limit": 10
    }
    
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print("✅ Vertex API is accessible!")
            print(f"Response (first 200 chars): {r.text[:200]}")
            return True
        else:
            print(f"❌ Vertex API returned status {r.status_code}")
            print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
    return False

def test_vertex_funding():
    print("\n=== Testing Vertex API (Funding Rates) ===")
    url = "https://api.vertexprotocol.com/v1/query"
    payload = {
        "type": "funding_rates",
        "product_id": 1,
        "limit": 10
    }
    
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print("✅ Funding Rates accessible!")
            print(f"Response (first 200 chars): {r.text[:200]}")
        else:
            print(f"❌ Status {r.status_code} | {r.text[:200]}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_vertex_candles()
    test_vertex_funding()
