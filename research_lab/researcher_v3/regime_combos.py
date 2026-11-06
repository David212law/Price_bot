"""D-561: True regime-aware evaluation.

For each strategy, compute metrics ONLY on days of each regime.
Then rank and combine PER REGIME — different regimes get different combos.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


RETURNS_DIR = Path("research_lab/logs/profiles/returns_matrices")
STATE_PATH = Path("research_lab/logs/profiles/state.json")

REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE_LOW", "RANGE_MED", 
           "RANGE_HIGH", "CRISIS_NEGATIVE", "CRISIS_VOL"]

BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE",
             "FUNDING_MEAN_REV", "FUNDING_ZSCORE", "FUNDING_CARRY"]

CRISIS_WINDOWS = {
    "LUNA": ("2022-05-01", "2022-06-15"),
    "FTX": ("2022-11-01", "2022-11-30"),
    "Ukraine": ("2022-02-20", "2022-03-15"),
    "Rate_Hikes": ("2022-06-01", "2022-10-31"),
}


def sharpe(vals, tpy=365):
    if len(vals) < 10: return 0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return (m/sd)*(tpy**0.5) if sd > 0 else 0


def compute_metrics_on_subset(rets_subset):
    """Compute metrics on a subset of days."""
    if len(rets_subset) < 10: return None
    dates = sorted(rets_subset.keys())
    vals = [rets_subset[d] for d in dates]
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
    wr = sum(1 for v in vals if v > 0)/n*100
    return {"sr": sr, "dd": dd, "ret": ret, "wr": wr, "n": n}


def detect_regime_from_prices(prices, lookback=14, ma_period=50):
    """Detect regime per day from prices (per-asset)."""
    dates = sorted(prices.keys())
    if len(dates) < ma_period + lookback: return {}
    
    # Daily returns
    rets = {}
    for i in range(1, len(dates)):
        p0 = prices[dates[i-1]]
        p1 = prices[dates[i]]
        if p0 > 0: rets[dates[i]] = (p1-p0)/p0
    
    regimes = {}
    for i in range(ma_period + lookback, len(dates)):
        d = dates[i]
        # Vol (20-day)
        recent_rets = [rets.get(dates[j], 0) for j in range(i-20, i) if j >= 1]
        if len(recent_rets) < 20: continue
        mean_r = sum(recent_rets)/len(recent_rets)
        var = sum((r-mean_r)**2 for r in recent_rets)/len(recent_rets)
        vol = var**0.5
        
        # Trend (7-day)
        trend = sum(recent_rets[-7:]) if len(recent_rets) >= 7 else 0
        
        # MA50
        ma50 = sum([prices[dates[j]] for j in range(i-ma_period, i)])/ma_period
        price = prices[dates[i-1]]
        below_ma = price < ma50 if ma50 > 0 else False
        
        # Classify
        if vol > 0.06: 
            r = "CRISIS_VOL"
        elif abs(trend) > 0.08 and not below_ma:
            r = "TREND_UP"
        elif abs(trend) > 0.08 and below_ma:
            r = "TREND_DOWN"
        elif vol < 0.02:
            r = "RANGE_LOW"
        elif vol < 0.04:
            r = "RANGE_MED"
        else:
            r = "RANGE_HIGH"
        
        regimes[d] = r
    return regimes


def load_all_strategies():
    """Load all valid strategies + their returns."""
    strategies = {}
    # M31 base
    for exch in ["hyperliquid", "aster", "kucoin"]:
        for f in (RETURNS_DIR / exch).glob("M31_EMA_*_BTC*.json"):
            try:
                rets = json.loads(f.read_text())
                if len(rets) >= 60:
                    strategies[f"M31_{exch}"] = {"returns": rets, "exchange": exch}
                    break
            except: pass
    
    # From profiler
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
        for key, v in state.get("done", {}).items():
            if not isinstance(v, dict): continue
            if v.get("status") not in ("profiled", "validated"): continue
            strat = v.get("strategy", "")
            if strat in BLACKLIST or strat.startswith("M31_"): continue
            val = v.get("validation", {})
            if not isinstance(val, dict): continue
            if val.get("sharpe_ann", 0) < 2: continue
            parts = key.split(":")
            if len(parts) < 4: continue
            exch, s, h, sym = parts[0], parts[1], parts[2], parts[3]
            f = RETURNS_DIR / exch / f"{s}_{h}_{sym}.json"
            if not f.exists(): continue
            try:
                rets = json.loads(f.read_text())
                if len(rets) >= 60:
                    name = f"{s}_{sym}"
                    if name not in strategies:
                        strategies[name] = {"returns": rets, "exchange": exch, "symbol": sym}
            except: pass
    return strategies


def load_prices_from_cache():
    """Load BTC prices from crisis cache for regime detection."""
    cache_file = Path("data/crisis_test_cache.json")
    if not cache_file.exists(): return {}
    try:
        data = json.loads(cache_file.read_text())
        return data.get("BTC-USD", {})
    except: return {}


def rank_strategies_per_regime(strategies, regime_map):
    """Rank strategies ONLY on days of each regime."""
    rankings = defaultdict(list)
    
    for name, data in strategies.items():
        rets = data["returns"]
        for regime in REGIMES:
            regime_dates = [d for d in rets if regime_map.get(d) == regime]
            if len(regime_dates) < 10: continue
            regime_rets = {d: rets[d] for d in regime_dates}
            m = compute_metrics_on_subset(regime_rets)
            if m:
                rankings[regime].append({"name": name, "sr": m["sr"], "dd": m["dd"],
                                          "ret": m["ret"], "wr": m["wr"], "n": m["n"]})
    
    for regime in rankings:
        rankings[regime].sort(key=lambda x: -x["sr"])
    return rankings


def build_combos(rankings, top_n=3):
    """Build DIFFERENT combos per regime."""
    combos = {}
    for regime in REGIMES:
        ranked = rankings.get(regime, [])
        if len(ranked) < 2: continue
        top = ranked[:top_n]
        # Weights based on SR (normalized)
        total_sr = sum(t["sr"] for t in top)
        if total_sr <= 0: continue
        components = [{"strategy": t["name"], "weight": round(t["sr"]/total_sr, 3)} for t in top]
        # For CRISIS, add cash buffer
        if regime.startswith("CRISIS"):
            for c in components:
                c["weight"] = round(c["weight"] * 0.7, 3)
            components.append({"strategy": "CASH", "weight": 0.3})
        combos[regime] = {
            "components": components,
            "top_strategies": top[:3],
            "total_sr_sum": round(total_sr, 2),
        }
    return combos


def main():
    print("=" * 72)
    print(" D-561: True regime-aware evaluation")
    print("=" * 72)
    
    print("\n[1] Loading strategies...")
    strategies = load_all_strategies()
    print(f"  {len(strategies)} strategies")
    
    print("\n[2] Loading prices for regime detection...")
    prices = load_prices_from_cache()
    if not prices:
        print("  ❌ no prices in cache")
        return
    print(f"  {len(prices)} days")
    
    print("\n[3] Detecting regimes per day...")
    regime_map = detect_regime_from_prices(prices)
    print(f"  {len(regime_map)} days with regime")
    counts = defaultdict(int)
    for r in regime_map.values():
        counts[r] += 1
    for r, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {r}: {c} days")
    
    print("\n[4] Ranking strategies PER REGIME...")
    rankings = rank_strategies_per_regime(strategies, regime_map)
    for regime in REGIMES:
        n = len(rankings.get(regime, []))
        print(f"  {regime}: {n} strategies")
    
    print("\n[5] Building DIFFERENT combos per regime...")
    combos = build_combos(rankings)
    
    print("\n" + "=" * 72)
    print(" 📊 RESULT — Different combos per regime")
    print("=" * 72)
    
    for regime in REGIMES:
        if regime not in combos:
            continue
        combo = combos[regime]
        print(f"\n  {regime}:")
        for c in combo["components"]:
            print(f"    {c['weight']*100:>5.1f}%  {c['strategy']}")
        print(f"    (top SR: {combo['top_strategies'][0]['sr']:.2f})")
    
    # Save
    out = Path("research_lab/logs/researcher_v3/regime_combos.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regime_counts": dict(counts),
        "combos": combos,
    }, indent=2, ensure_ascii=False))
    print(f"\n💾 saved: {out}")
    
    return combos


if __name__ == "__main__":
    main()
