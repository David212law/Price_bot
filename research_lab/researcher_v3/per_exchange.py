"""D-558: Per-Exchange Tester — Test strategies per exchange."""
import json
from pathlib import Path
from datetime import datetime, timezone


RETURNS_DIR = Path("research_lab/logs/profiles/returns_matrices")


def load_returns_for_exchange(exchange):
    """Load all returns files for an exchange."""
    result = {}
    p = RETURNS_DIR / exchange
    if not p.exists(): return result
    for f in p.glob("*.json"):
        try:
            rets = json.loads(f.read_text())
            if len(rets) >= 60:
                name = f.stem
                result[name] = rets
        except: pass
    return result


def sharpe(vals, tpy=365):
    if len(vals) < 20: return 0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return (m/sd)*(tpy**0.5) if sd > 0 else 0


def compute_metrics(rets):
    if len(rets) < 20: return None
    dates = sorted(rets.keys())
    vals = [rets[d] for d in dates]
    n = len(vals)
    span = (datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(dates[0], "%Y-%m-%d")).days
    tpy = n / (span/365.25) if span > 0 else 365
    m = sum(vals)/n
    v = sum((x-m)**2 for x in vals)/n
    sd = v**0.5
    sr = (m/sd)*(tpy**0.5) if sd > 0 else 0
    eq = [1.0]
    for r in vals: eq.append(eq[-1]*(1+r))
    ret = (eq[-1]-1)*100
    peak = eq[0]; dd = 0
    for e in eq:
        if e > peak: peak = e
        cur = (peak-e)/peak*100
        if cur > dd: dd = cur
    return {"sr": sr, "dd": dd, "ret": ret, "n": n}


def test_per_exchange():
    """Test all strategies per exchange. Returns per-exchange ranked list."""
    results = {}
    for exch in ["hyperliquid", "aster", "kucoin"]:
        strategies = load_returns_for_exchange(exch)
        ranked = []
        BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"]
        for name, rets in strategies.items():
            # D-559: skip blacklisted + M31 variants
            if any(bl in name for bl in BLACKLIST): continue
            if name.startswith("M31_") and not name.startswith("M31_HEDGED"): continue
            m = compute_metrics(rets)
            if m and m["sr"] >= 3:
                ranked.append({"name": name, "sr": m["sr"], "dd": m["dd"], "ret": m["ret"]})
        ranked.sort(key=lambda x: -x["sr"])
        results[exch] = {
            "n_strategies": len(ranked),
            "top10": ranked[:10],
            "best": ranked[0]["name"] if ranked else "none",
        }
    return results


if __name__ == "__main__":
    results = test_per_exchange()
    for exch, info in results.items():
        print(f"{exch}: {info['n_strategies']} strategies")
        for s in info["top10"][:3]:
            print(f"  {s['name'][:40]:<42} SR={s['sr']:>5.1f} DD={s['dd']:>5.1f}%")
