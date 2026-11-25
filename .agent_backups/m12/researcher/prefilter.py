"""Cheap screening: run each strategy on a small representative subset,
keep only those with enough trades + usable raw win-rate."""
import json, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.dirname(_HERE); _ROOT = os.path.dirname(_CORE)
sys.path.insert(0, _CORE)
from calc import win_rate, mean
from m12_strategies import STRATEGIES

DATA_DIR = os.path.join(_ROOT, "data")
OUT = os.path.join(_HERE, "prefilter_keep.json")
FEE = {"TMN": 0.006, "USDT": 0.0026, "GLOBAL": 0.001}
SPREAD = 0.005
START_MS = 1700000000000; DAY_MS = 86400000
SUBSET = 8          # representative symbols
MIN_TRADES = 15      # min total trades across all regimes
MIN_WR = 0.50        # raw bar

def _load(path, suffix=None):
    if not os.path.exists(path): return {}
    raw = json.load(open(path)); out = {}
    for k, v in raw.items():
        if not isinstance(v, (list, dict)) or len(v) < 300: continue
        if suffix:
            if not k.endswith(suffix): continue
            sym = k[:-len(suffix)]
        else: sym = k
        if isinstance(v, dict):
            items = sorted(v.items(), key=lambda kv: kv[0]); prices = [float(x[1]) for x in items]
        else: prices = [float(x) for x in v]
        if len(prices) >= 300: out[sym] = prices
    return out

def to_candles(prices):
    return [{"t": START_MS + i*DAY_MS, "o": p, "h": p*(1+SPREAD),
             "l": p*(1-SPREAD), "c": p, "v": 1.0} for i, p in enumerate(prices)]

def screen(mname, syms, fee, n_btc):
    syms = dict(sorted(syms.items(), key=lambda x: -len(x[1]))[:SUBSET])
    scores = {}
    for sname, sfn in STRATEGIES.items():
        won, ret = [], []
        for sym, prices in syms.items():
            prices = prices[-n_btc:]
            if len(prices) < 300: continue
            try: trades = sfn(to_candles(prices)) or []
            except Exception: trades = []
            for t in trades:
                e = t.get("t")
                if e is None: continue
                idx = int((e - START_MS) / DAY_MS)
                if idx < 0 or idx >= n_btc: continue
                net = t["ret"] - fee
                won.append(1 if net > 0 else 0); ret.append(net)
        scores[sname] = {"n": len(won), "wr": win_rate(won) if won else 0.0,
                         "mr": mean(ret) if ret else 0.0}
    keep = [n for n, s in scores.items()
            if s["n"] >= MIN_TRADES and s["wr"] >= MIN_WR]
    print(f"[{mname}] screened {len(STRATEGIES)} -> kept {len(keep)}")
    return keep, scores

if __name__ == "__main__":
    tmn = _load(os.path.join(DATA_DIR, "wallex_tmn_all.json"), "TMN")
    btc = tmn.get("BTC", [])
    if not btc: print("BTC missing"); sys.exit(1)
    n = len(btc)
    markets = {
        "TMN": _load(os.path.join(DATA_DIR, "wallex_tmn_all.json"), "TMN"),
        "USDT": _load(os.path.join(DATA_DIR, "wallex_usdt_all.json"), "USDT"),
        "GLOBAL": _load(os.path.join(DATA_DIR, "crypto_5y_usd.json")),
    }
    union, all_scores = set(), {}
    for mname, syms in markets.items():
        keep, scores = screen(mname, syms, FEE[mname], n)
        union.update(keep); all_scores[mname] = scores
    json.dump({"keep": sorted(union)}, open(OUT, "w"), indent=2)
    json.dump(all_scores, open(os.path.join(_HERE, "prefilter_scores.json"), "w"), indent=2)
    print(f"Total kept across markets: {len(union)} -> {OUT}")
