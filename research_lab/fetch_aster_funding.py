"""D-444: Fetch Aster funding 2 years."""
import sys, os, json, time, requests
from datetime import datetime, timezone, timedelta

BASE = "https://fapi.asterdex.com"
DATA_DIR = "data/aster"
YEARS = 2

def fetch_funding(symbol, years=YEARS):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=years*365)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    out = []; cursor = start_ms; seen = set()
    for _ in range(100):
        try:
            r = requests.get(f"{BASE}/fapi/v1/fundingRate",
                params={"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000},
                timeout=20)
            if r.status_code != 200:
                print(f"  ⚠ {symbol}: HTTP {r.status_code}"); break
            data = r.json()
            if not data: break
            new = [d for d in data if d["fundingTime"] not in seen]
            if not new: break
            for d in new:
                seen.add(d["fundingTime"])
                out.append({"t": int(d["fundingTime"]), "rate": float(d["fundingRate"])})
            latest = max(int(d["fundingTime"]) for d in new)
            if latest >= end_ms: break
            cursor = latest + 1
            time.sleep(0.25)
        except Exception as e:
            print(f"  ⚠ {symbol}: {e}"); break
    out.sort(key=lambda x: x["t"])
    return out


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_aster_funding.py SYMBOL")
        sys.exit(1)
    symbol = sys.argv[1]
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"═══ {symbol} ═══")
    funding = fetch_funding(symbol)
    if not funding:
        print("  ❌ no data"); return
    path = f"{DATA_DIR}/{symbol}_funding.json"
    with open(path, "w") as f:
        json.dump(funding, f)
    f0 = datetime.fromtimestamp(funding[0]["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
    f1 = datetime.fromtimestamp(funding[-1]["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"  ✅ {len(funding)} records | {f0} → {f1}")


if __name__ == "__main__":
    main()
