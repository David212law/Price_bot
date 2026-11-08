"""Fetch ALL Wallex symbols — both TMN and USDT markets, with full history."""
import urllib.request, json, time, os
from datetime import datetime, timezone

def fetch_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def main():
    os.makedirs("data", exist_ok=True)
    print("="*80)
    print(" FETCH ALL WALLEX SYMBOLS")
    print("="*80)

    # Step 1: Get all symbols
    markets = fetch_json("https://api.wallex.ir/v1/markets")
    symbols_dict = markets.get("result", {}).get("symbols", {})
    all_syms = list(symbols_dict.keys())
    print(f"\nTotal symbols: {len(all_syms)}")

    tmn_syms = [s for s in all_syms if s.endswith("TMN")]
    usdt_syms = [s for s in all_syms if s.endswith("USDT")]
    print(f"  TMN market:  {len(tmn_syms)}")
    print(f"  USDT market: {len(usdt_syms)}")

    # Step 2: Fetch history for all (3 years max)
    now = int(datetime.now().timestamp())
    three_years_ago = now - 1095*86400

    tmn_data = {}
    usdt_data = {}
    failed = []

    print(f"\nFetching {len(tmn_syms)} TMN symbols...")
    for i, sym in enumerate(tmn_syms):
        if i % 20 == 0:
            print(f"  [{i}/{len(tmn_syms)}] {sym}")
        try:
            url = f"https://api.wallex.ir/v1/udf/history?symbol={sym}&resolution=1D&from={three_years_ago}&to={now}"
            d = fetch_json(url, timeout=15)
            if d.get("s") == "ok" and d.get("t") and len(d["t"]) >= 30:
                data = {}
                for j in range(len(d["t"])):
                    ts = d["t"][j]
                    close = float(d["c"][j])
                    if close > 0:
                        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                        data[date_str] = close
                tmn_data[sym] = data
            else:
                failed.append(sym)
        except Exception:
            failed.append(sym)
        time.sleep(0.1)

    print(f"  OK: {len(tmn_data)}, Failed: {len(failed)}")

    print(f"\nFetching {len(usdt_syms)} USDT symbols...")
    failed_usdt = []
    for i, sym in enumerate(usdt_syms):
        if i % 20 == 0:
            print(f"  [{i}/{len(usdt_syms)}] {sym}")
        try:
            url = f"https://api.wallex.ir/v1/udf/history?symbol={sym}&resolution=1D&from={three_years_ago}&to={now}"
            d = fetch_json(url, timeout=15)
            if d.get("s") == "ok" and d.get("t") and len(d["t"]) >= 30:
                data = {}
                for j in range(len(d["t"])):
                    ts = d["t"][j]
                    close = float(d["c"][j])
                    if close > 0:
                        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                        data[date_str] = close
                usdt_data[sym] = data
            else:
                failed_usdt.append(sym)
        except Exception:
            failed_usdt.append(sym)
        time.sleep(0.1)

    print(f"  OK: {len(usdt_data)}, Failed: {len(failed_usdt)}")

    # Step 3: Summary by days
    def summarize(name, data):
        print(f"\n{name}:")
        bins = {"<100 days": 0, "100-499": 0, "500-799": 0, "800+": 0}
        for sym, prices in data.items():
            n = len(prices)
            if n < 100: bins["<100 days"] += 1
            elif n < 500: bins["100-499"] += 1
            elif n < 800: bins["500-799"] += 1
            else: bins["800+"] += 1
        for k, v in bins.items():
            print(f"  {k}: {v}")
        # Top by days
        top = sorted(data.items(), key=lambda x: -len(x[1]))[:10]
        print(f"  Top 10 (by days):")
        for sym, prices in top:
            ds = sorted(prices.keys())
            print(f"    {sym:<14} {len(prices):>4}d  ({ds[0]} -> {ds[-1]})")

    summarize("TMN market", tmn_data)
    summarize("USDT market", usdt_data)

    # Save
    json.dump(tmn_data, open("data/wallex_tmn_all.json", "w"))
    json.dump(usdt_data, open("data/wallex_usdt_all.json", "w"))
    print(f"\nSaved:")
    print(f"  data/wallex_tmn_all.json ({len(tmn_data)} symbols)")
    print(f"  data/wallex_usdt_all.json ({len(usdt_data)} symbols)")

if __name__ == "__main__":
    main()
