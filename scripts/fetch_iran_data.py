"""Iran market data fetcher — TGJU (USD/IRR) + Wallex (crypto pairs in TMN)."""

import urllib.request
import json
import time
import os
from datetime import datetime, timezone

WALLEX_ASSETS = [
    "USDTTMN", "BTCTMN", "ETHTMN", "XRPTMN", "TRXTMN", "BNBTMN",
    "SOLTMN", "DOGETMN", "ADATMN", "LINKTMN", "AVAXTMN", "DOTTMN",
]


def fetch_tgju_usd_irr():
    """Fetch all USD/IRR records from TGJU (~4000 records, 10+ years)."""
    all_data = {}
    for start in range(0, 4000, 500):
        url = f"https://api.tgju.org/v1/market/indicator/summary-table-data/price_dollar_rl?start={start}&length=500"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read())
            rows = d.get("data", [])
            if not rows:
                break
            for row in rows:
                try:
                    price_str = str(row[0]).replace(",", "").strip()
                    date_str = str(row[6]).replace("/", "-")
                    all_data[date_str] = float(price_str)
                except (ValueError, IndexError):
                    continue
            print(f"  TGJU start={start}: {len(rows)} rows (total {len(all_data)})")
            time.sleep(0.3)
        except Exception as e:
            print(f"  TGJU error at start={start}: {e}")
            break
    return all_data


def fetch_wallex_symbol(symbol, days=1100):
    """Fetch daily history for one Wallex symbol."""
    now = int(datetime.now().timestamp())
    start = now - days * 86400
    url = f"https://api.wallex.ir/v1/udf/history?symbol={symbol}&resolution=1D&from={start}&to={now}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        if d.get("s") != "ok" or not d.get("t"):
            return None
        result = {}
        for i in range(len(d["t"])):
            ts = d["t"][i]
            date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            result[date] = float(d["c"][i])
        return result
    except Exception as e:
        print(f"  {symbol}: {e}")
        return None


def main():
    os.makedirs("data", exist_ok=True)

    print("=" * 60)
    print(" Fetching TGJU USD/IRR...")
    print("=" * 60)
    usd_irr = fetch_tgju_usd_irr()
    if usd_irr:
        with open("data/usd_irr_tgju.json", "w") as f:
            json.dump(usd_irr, f)
        dates = sorted(usd_irr.keys())
        print(f"  SAVED: {len(usd_irr)} records ({dates[0]} -> {dates[-1]})")
    else:
        print("  ERROR: no TGJU data")

    print("\n" + "=" * 60)
    print(" Fetching Wallex crypto history...")
    print("=" * 60)
    wallex = {}
    for sym in WALLEX_ASSETS:
        data = fetch_wallex_symbol(sym)
        if data:
            wallex[sym] = data
            print(f"  OK {sym}: {len(data)} days")
        else:
            print(f"  FAIL {sym}")
        time.sleep(0.2)
    if wallex:
        with open("data/wallex_full.json", "w") as f:
            json.dump(wallex, f)
        print(f"  SAVED: {len(wallex)} symbols")

    print("\n" + "=" * 60)
    print(" Done")
    print("=" * 60)


if __name__ == "__main__":
    main()
