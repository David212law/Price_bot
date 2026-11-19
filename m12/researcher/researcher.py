import json, csv, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_CORE)
sys.path.insert(0, _CORE)
from calc import regime_label, win_rate, mean, correlation, normalize
from m12_strategies import STRATEGIES
_PF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prefilter_keep.json")
_keep = set(json.load(open(_PF))["keep"]) if os.path.exists(_PF) else None
STRATEGIES = {k: v for k, v in STRATEGIES.items() if _keep is None or k in _keep}

CSV_DIR = os.path.join(_HERE, "research")
CONFIG_FILE = os.path.join(_CORE, "config.json")
DATA_DIR = os.path.join(_ROOT, "data")

FEE = {"TMN": 0.006, "USDT": 0.0026, "GLOBAL": 0.001}
MAX_SYMBOLS = 185
SPREAD = 0.005
START_MS = 1700000000000
DAY_MS = 86400000

def _load(path, suffix=None):
    if not os.path.exists(path): return {}
    raw = json.load(open(path))
    out = {}
    for k, v in raw.items():
        if not isinstance(v, (list, dict)) or len(v) < 300: continue
        if suffix:
            if not k.endswith(suffix): continue
            sym = k[:-len(suffix)]
        else:
            sym = k
        if isinstance(v, dict):
            items = sorted(v.items(), key=lambda kv: kv[0])
            prices = [float(x) for _, x in items]
        else:
            prices = [float(x) for x in v]
        if len(prices) >= 300: out[sym] = prices
    return out

def label_regimes(prices):
    r = [None] * len(prices)
    for i in range(31, len(prices)):
        r[i] = regime_label(prices[i] / prices[i-30] - 1)
    return r

def to_candles(prices):
    return [{"t": START_MS + i*DAY_MS, "o": p, "h": p*(1+SPREAD),
             "l": p*(1-SPREAD), "c": p, "v": 1.0}
            for i, p in enumerate(prices)]

def evaluate(symbols, btc_regimes, fee, n_btc):
    result = {s: {r: {"won": [], "ret": []} for r in ["BULL","FLAT","BEAR","CRASH"]}
              for s in STRATEGIES}
    n_ok = 0
    for sym, prices in symbols.items():
        prices = prices[-n_btc:]
        if len(prices) < 300: continue
        if len(prices) > n_btc: prices = prices[-n_btc:]
        n_ok += 1
        candles = to_candles(prices)
        for sname, sfn in STRATEGIES.items():
            try: trades = sfn(candles) or []
            except Exception: continue
            for t in trades:
                entry = t.get("t")
                if entry is None: continue
                idx = int((entry - START_MS) / DAY_MS)
                if idx < 0 or idx >= n_btc: continue
                r = btc_regimes[idx]
                if r is None: continue
                net = t["ret"] - fee
                result[sname][r]["won"].append(1 if net > 0 else 0)
                result[sname][r]["ret"].append(net)
    return result, n_ok

def export_csv(market, name, regime, won, ret):
    os.makedirs(CSV_DIR, exist_ok=True)
    base = f"{market}__{name}__{regime}"
    with open(f"{CSV_DIR}/{base}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["idx","won","ret"])
        for i in range(len(won)): w.writerow([i, won[i], round(ret[i], 6)])
    with open(f"{CSV_DIR}/{base}.json", "w") as f:
        json.dump({"market": market, "strategy": name, "regime": regime,
                   "n": len(won), "win_rate": win_rate(won),
                   "avg_ret": mean(ret)}, f, indent=2)

def select(agg):
    config = {}
    for regime in ["BULL","FLAT","BEAR","CRASH"]:
        if regime == "CRASH": config[regime] = {}; continue
        cands = []
        for sname in STRATEGIES:
            won = agg[sname][regime]["won"]; ret = agg[sname][regime]["ret"]
            if len(won) < 20: continue
            wr = win_rate(won); mr = mean(ret)
            if wr >= 0.52 and mr > 0: cands.append((sname, wr, mr, ret))
        if not cands: config[regime] = {}; continue
        cands.sort(key=lambda x: -x[1])
        picked, picked_rets = [], []
        for name, wr, mr, rets in cands:
            if not picked:
                picked.append(name); picked_rets.append(rets); continue
            max_c = 0.0
            for ex in picked_rets:
                n = min(len(rets), len(ex))
                if n < 10: continue
                max_c = max(max_c, abs(correlation(rets[:n], ex[:n])))
            if max_c < 0.5: picked.append(name); picked_rets.append(rets)
        if picked:
            w = {n: next(c[1] for c in cands if c[0]==n) for n in picked}
            config[regime] = normalize(w)
    return config

def main():
    print("=" * 70); print(" M12 v3"); print("=" * 70)
    tmn = _load(os.path.join(DATA_DIR, "wallex_tmn_all.json"), "TMN")
    if "BTC" not in tmn: print("BTC missing"); return
    btc = tmn["BTC"]; btc_r = label_regimes(btc); n = len(btc)
    print(f"BTC: {n} days | BULL={btc_r.count('BULL')} FLAT={btc_r.count('FLAT')} BEAR={btc_r.count('BEAR')} CRASH={btc_r.count('CRASH')}\n")
    markets = {
        "TMN": dict(sorted(tmn.items(), key=lambda x: -len(x[1]))[:MAX_SYMBOLS]),
        "USDT": dict(sorted(_load(os.path.join(DATA_DIR, "wallex_usdt_all.json"), "USDT").items(), key=lambda x: -len(x[1]))[:MAX_SYMBOLS]),
        "GLOBAL": dict(sorted(_load(os.path.join(DATA_DIR, "crypto_5y_usd.json")).items(), key=lambda x: -len(x[1]))[:MAX_SYMBOLS]),
    }
    all_config = {}
    for mname, syms in markets.items():
        if not syms: all_config[mname] = {}; print(f"[{mname}] no data"); continue
        print(f"[{mname}] {len(syms)} symbols...")
        agg, n_ok = evaluate(syms, btc_r, FEE[mname], n)
        print(f"  aligned: {n_ok}/{len(syms)}")
        for regime in ["BULL","FLAT","BEAR","CRASH"]:
            cnt, best = 0, None
            for sn in STRATEGIES:
                won = agg[sn][regime]["won"]; ret = agg[sn][regime]["ret"]
                if len(won) < 20: continue
                wr = win_rate(won); mr = mean(ret)
                if wr >= 0.52 and mr > 0:
                    cnt += 1
                    if best is None or wr > best[1]: best = (sn, wr, mr)
            bs = f"best={best[0]} wr={best[1]:.3f} ret={best[2]:+.4f}" if best else "-"
            print(f"  {regime:6s}: {cnt:2d} valid | {bs}")
        for sn in STRATEGIES:
            for regime in ["BULL","FLAT","BEAR","CRASH"]:
                won = agg[sn][regime]["won"]; ret = agg[sn][regime]["ret"]
                if len(won) >= 5: export_csv(mname, sn, regime, won, ret)
        cfg = select(agg); all_config[mname] = cfg
        for regime, w in cfg.items():
            if w: print(f"  -> {regime:6s}: {list(w.keys())}")
        print()
    with open(CONFIG_FILE, "w") as f: json.dump(all_config, f, indent=2)
    print(f"[5] Saved {CONFIG_FILE}")
    print("NEXT: python3 verify.py")

if __name__ == "__main__":
    main()
