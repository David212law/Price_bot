"""Fetch KuCoin funding + 4h klines for last N years (paginated)."""
import sys, os, json, time, requests
from datetime import datetime, timezone, timedelta

BASE = "https://api-futures.kucoin.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DATA_DIR = "exchanges/kucoin/data"
YEARS = 3

def fetch_funding_paginated(symbol, start_ms, end_ms):
    """KuCoin funding: 8h intervals. Page backward in chunks."""
    out = []
    cursor = end_ms
    seen = set()
    for _ in range(50):  # safety limit
        url = f"{BASE}/api/v1/contract/funding-rates"
        try:
            r = requests.get(url, params={"symbol": symbol, "from": start_ms, "to": cursor},
                             headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"  ⚠️ {symbol} funding HTTP {r.status_code}")
                break
            data = r.json().get("data", [])
            if not data:
                break
            new = [d for d in data if d.get("timepoint") and d["timepoint"] not in seen]
            if not new:
                break
            for d in new:
                seen.add(d["timepoint"])
                out.append(d)
            oldest = min(d["timepoint"] for d in new)
            if oldest <= start_ms:
                break
            cursor = oldest - 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ {symbol} funding err: {e}")
            break
    out.sort(key=lambda x: x["timepoint"], reverse=True)
    return out

def fetch_klines_paginated(symbol, start_ms, end_ms, granularity=240):
    """KuCoin klines: FORWARD pagination from start_ms."""
    out = []
    cursor = start_ms
    seen = set()
    for _ in range(200):  # safety: up to 200 pages
        url = f"{BASE}/api/v1/kline/query"
        try:
            r = requests.get(url, params={"symbol": symbol, "granularity": granularity,
                                          "from": cursor, "to": end_ms},
                             headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"  ⚠️ {symbol} klines HTTP {r.status_code}")
                break
            data = r.json().get("data", [])
            if not data:
                break
            new = [d for d in data if d[0] not in seen]
            if not new:
                break
            for d in new:
                seen.add(d[0])
                out.append({"t": int(d[0]), "o": float(d[1]), "h": float(d[2]),
                            "l": float(d[3]), "c": float(d[4]), "v": float(d[5])})
            latest = max(d[0] for d in new)
            if latest >= end_ms:
                break
            cursor = latest + 1  # forward
            time.sleep(0.25)
        except Exception as e:
            print(f"  ⚠️ {symbol} klines err: {e}")
            break
    out.sort(key=lambda x: x["t"])
    return out

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_kucoin_extended.py SYMBOL"); sys.exit(1)
    symbol = sys.argv[1]
    os.makedirs(DATA_DIR, exist_ok=True)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=YEARS*365)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    print(f"═══ {symbol} ═══")
    print(f"Period: {start.date()} → {end.date()}")

    print(f"  Fetching funding...")
    funding = fetch_funding_paginated(symbol, start_ms, end_ms)
    print(f"  → {len(funding)} records")
    fp = f"{DATA_DIR}/{symbol}_funding.json"
    with open(fp, "w") as f:
        json.dump(funding, f)
    print(f"  → {fp} ({os.path.getsize(fp)} bytes)")

    print(f"  Fetching klines (4h)...")
    klines = fetch_klines_paginated(symbol, start_ms, end_ms)
    print(f"  → {len(klines)} records")
    kp = f"{DATA_DIR}/{symbol}_4h.json"
    with open(kp, "w") as f:
        json.dump(klines, f)
    print(f"  → {kp} ({os.path.getsize(kp)} bytes)")

if __name__ == "__main__":
    main()
