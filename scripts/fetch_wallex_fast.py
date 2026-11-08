"""Fast parallel fetch for Wallex using ThreadPool."""
import urllib.request, json, os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_sym(sym, start, end):
    try:
        url = f"https://api.wallex.ir/v1/udf/history?symbol={sym}&resolution=1D&from={start}&to={end}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if d.get("s") == "ok" and d.get("t"):
            data = {datetime.fromtimestamp(d["t"][j], tz=timezone.utc).strftime("%Y-%m-%d"): float(d["c"][j]) for j in range(len(d["t"]))}
            return sym, data
    except: pass
    return sym, None

def main():
    print("Fetching symbols list...")
    req = urllib.request.Request("https://api.wallex.ir/v1/markets", headers={"User-Agent": "Mozilla/5.0"})
    res = json.loads(urllib.request.urlopen(req).read())
    syms = list(res.get("result", {}).get("symbols", {}).keys())
    now = int(datetime.now().timestamp()); start = now - 1095*86400

    tmn, usdt = {}, {}
    print(f"Fetching {len(syms)} symbols in parallel...")
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_sym, s, start, now): s for s in syms}
        for f in as_completed(futures):
            sym, data = f.result()
            if data and len(data) >= 30:
                if sym.endswith("TMN"): tmn[sym] = data
                elif sym.endswith("USDT"): usdt[sym] = data
                
    os.makedirs("data", exist_ok=True)
    json.dump(tmn, open("data/wallex_tmn_all.json", "w"))
    json.dump(usdt, open("data/wallex_usdt_all.json", "w"))
    print(f"Done! TMN: {len(tmn)}, USDT: {len(usdt)}")

if __name__ == "__main__": main()
