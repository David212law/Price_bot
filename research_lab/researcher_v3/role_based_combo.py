"""D-566: Role-Based Combo — champion per regime based on THESIS, not SR.

Key difference from previous version:
  OLD: For each regime, weight top strategies by SR (M31 dominates everywhere)
  NEW: For each regime, use THESIS-based champion:
       - TREND_UP → M31 (funding carry pays in trends)
       - RANGE_*  → Keltner (mean reversion works in ranges)
       - CRISIS   → Cash (no strategy works)
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

# Thesis mapping by strategy prefix
THESIS_MAP = {
    "M31": "funding_carry",
    "KELTNER": "mean_reversion",
    "MR_": "mean_reversion",
    "MEAN_": "mean_reversion",
    "PAIRS": "mean_reversion",
    "ZSCORE": "mean_reversion",
    "WEEKLY": "mean_reversion",
    "BB": "mean_reversion",
    "RSI": "momentum",
    "MOM": "momentum",
    "ROC": "momentum",
    "MACD": "momentum",
    "SUPERTREND": "trend",
    "EMA": "trend",
    "SMA": "trend",
    "DONCHIAN": "trend",
    "PSAR": "trend",
    "ICHIMOKU": "trend",
    "T_": "trend",
    "VOLUME": "volume",
    "VOL_": "volatility",
    "ATR": "volatility",
    "MFI": "volume",
    "OBV": "volume",
    "VWAP": "volume",
}

# Champion thesis per regime
REGIME_CHAMPION_THESIS = {
    "TREND_UP": "funding_carry",       # funding pays during uptrend
    "TREND_DOWN": "mean_reversion",    # oversold reversal in downtrend
    "RANGE_LOW": "mean_reversion",     # range → strong mean reversion
    "RANGE_MED": "mean_reversion",
    "RANGE_HIGH": "mean_reversion",
    "CRISIS_NEGATIVE": "cash",         # no strategy works
    "CRISIS_VOL": "cash",
}


def get_thesis(name):
    for prefix, thesis in THESIS_MAP.items():
        if name.startswith(prefix):
            return thesis
    return "unknown"


def sharpe(vals, tpy=365):
    if len(vals) < 10: return 0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return (m/sd)*(tpy**0.5) if sd > 0 else 0


def compute_metrics_on_subset(rets_subset):
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
        cur = (peak-e)/peak*100 if peak > 0 else 0
        if cur > dd: dd = cur
    return {"sr": sr, "dd": dd, "ret": ret, "n": n}


def load_strategies():
    strategies = {}
    for exch in ["hyperliquid", "aster", "kucoin"]:
        for f in (RETURNS_DIR / exch).glob("M31_EMA_*_BTC*.json"):
            try:
                rets = json.loads(f.read_text())
                if len(rets) >= 60:
                    strategies[f"M31_{exch}"] = rets
                    break
            except: pass
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
                        strategies[name] = rets
            except: pass
    return strategies


def load_btc_prices():
    cache = Path("data/crisis_test_cache.json")
    if not cache.exists(): return {}
    try:
        data = json.loads(cache.read_text())
        return data.get("BTC-USD", {})
    except: return {}


def detect_regime(prices, i, ma_period=50):
    dates = sorted(prices.keys())
    if i < ma_period + 14: return None
    rets = []
    for j in range(1, i+1):
        p0, p1 = prices[dates[j-1]], prices[dates[j]]
        if p0 > 0: rets.append((p1-p0)/p0)
    if len(rets) < 20: return None
    recent = rets[-20:]
    m = sum(recent)/len(recent)
    var = sum((r-m)**2 for r in recent)/len(recent)
    vol = var**0.5
    trend = sum(rets[-7:]) if len(rets) >= 7 else 0
    ma = sum([prices[dates[j]] for j in range(i-ma_period, i)])/ma_period
    price = prices[dates[i-1]]
    below = price < ma
    if vol > 0.045: return "CRISIS_VOL"
    if trend > 0.08 and not below: return "TREND_UP"
    if trend < -0.08 and below: return "TREND_DOWN"
    if vol < 0.02: return "RANGE_LOW"
    if vol < 0.04: return "RANGE_MED"
    return "RANGE_HIGH"


def build_regime_map(prices):
    dates = sorted(prices.keys())
    regime_map = {}
    for i in range(65, len(dates)):
        r = detect_regime(prices, i)
        if r: regime_map[dates[i]] = r
    return regime_map


def compute_per_regime_metrics(strategies, regime_map):
    results = {}
    for name, rets in strategies.items():
        per_regime = {}
        for regime in REGIMES:
            regime_dates = [d for d in rets if regime_map.get(d) == regime]
            if len(regime_dates) < 10: continue
            regime_rets = {d: rets[d] for d in regime_dates}
            m = compute_metrics_on_subset(regime_rets)
            if m: per_regime[regime] = m
        results[name] = per_regime
    return results


def find_champion(regime, strategies, per_regime_metrics, roles):
    """Find champion for regime based on THESIS (not SR)."""
    target_thesis = REGIME_CHAMPION_THESIS.get(regime, "cash")
    if target_thesis == "cash":
        return "CASH"
    
    candidates = []
    for name in strategies:
        role = roles.get(name)
        if not role: continue
        if role["thesis"] != target_thesis: continue
        m = per_regime_metrics[name].get(regime)
        if m and m["sr"] >= 2:
            candidates.append((name, m["sr"]))
    
    if not candidates:
        for name in strategies:
            m = per_regime_metrics[name].get(regime)
            if m and m["sr"] >= 3:
                candidates.append((name, m["sr"]))
    
    if not candidates: return "CASH"
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]


def find_supporting(champion, regime, strategies, per_regime_metrics, roles, max_n=2):
    if champion == "CASH": return []
    champion_thesis = roles.get(champion, {}).get("thesis", "unknown")
    candidates = []
    for name in strategies:
        if name == champion: continue
        role = roles.get(name)
        if not role: continue
        if role["thesis"] == champion_thesis: continue  # diversity
        m = per_regime_metrics[name].get(regime)
        if m and m["sr"] >= 3:
            candidates.append((name, m["sr"]))
    candidates.sort(key=lambda x: -x[1])
    return [c[0] for c in candidates[:max_n]]


def build_combo(regime, strategies, per_regime_metrics, roles):
    champion = find_champion(regime, strategies, per_regime_metrics, roles)
    if champion == "CASH":
        return {
            "champion": "CASH",
            "champion_thesis": "cash",
            "components": [{"strategy": "CASH", "weight": 1.0, "role": "champion"}],
            "fallback": "cash_only",
        }
    supporting = find_supporting(champion, regime, strategies, per_regime_metrics, roles)
    components = [{"strategy": champion, "weight": 0.45, "role": "champion"}]
    if supporting:
        per_w = 0.20
        for s in supporting:
            components.append({"strategy": s, "weight": per_w, "role": "supporting"})
    total = sum(c["weight"] for c in components)
    cash_w = round(1.0 - total, 3)
    if cash_w > 0.01:
        components.append({"strategy": "CASH", "weight": cash_w, "role": "buffer"})
    return {
        "champion": champion,
        "champion_thesis": roles[champion]["thesis"],
        "components": components,
        "fallback": None,
    }


def validate_combo(combo, strategies, regime_map, regime):
    """Validate on last 30% of regime days (holdout)."""
    regime_dates = sorted([d for d in regime_map if regime_map[d] == regime])
    if len(regime_dates) < 60: return None
    split = int(len(regime_dates) * 0.7)
    test_dates = regime_dates[split:]
    
    combo_rets = {}
    for d in test_dates:
        ret = 0
        for c in combo["components"]:
            s = c["strategy"]
            w = c["weight"]
            if s == "CASH": continue
            if s in strategies:
                ret += w * strategies[s].get(d, 0)
        combo_rets[d] = ret
    
    m = compute_metrics_on_subset(combo_rets)
    if not m: return None
    
    # Compare to champion alone on same test dates
    champ = combo["champion"]
    if champ != "CASH" and champ in strategies:
        champ_rets = {d: strategies[champ].get(d, 0) for d in test_dates}
        cm = compute_metrics_on_subset(champ_rets)
        if cm:
            m["champion_sr"] = cm["sr"]
            m["champion_dd"] = cm["dd"]
            m["combo_vs_champion"] = round(m["sr"] / cm["sr"], 2) if cm["sr"] > 0 else 0
    
    return m


def main():
    print("=" * 72)
    print(" D-566: Role-Based Combo")
    print("=" * 72)
    
    print("\n[1] Loading strategies + prices...")
    strategies = load_strategies()
    prices = load_btc_prices()
    print(f"  {len(strategies)} strategies, {len(prices)} price days")
    
    print("\n[2] Detecting regimes...")
    regime_map = build_regime_map(prices)
    counts = defaultdict(int)
    for r in regime_map.values(): counts[r] += 1
    for r, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c} days")
    
    print("\n[3] Computing per-regime metrics...")
    per_regime = compute_per_regime_metrics(strategies, regime_map)
    print(f"  done for {len(per_regime)} strategies")
    
    print("\n[4] Assigning roles (thesis-based)...")
    roles = {}
    for name in strategies:
        m = per_regime.get(name, {})
        if not m: continue
        srs = {r: v["sr"] for r, v in m.items() if v["sr"] > 0}
        if not srs: continue
        home = max(srs, key=srs.get)
        roles[name] = {
            "thesis": get_thesis(name),
            "home_regime": home,
            "srs": srs,
        }
    print(f"  {len(roles)} roles assigned")
    
    print("\n[5] Building role-based combos...")
    combos = {}
    for regime in REGIMES:
        combo = build_combo(regime, strategies, per_regime, roles)
        combos[regime] = combo
    
    print("\n" + "=" * 72)
    print(" 📊 RESULT — Role-Based Combos")
    print("=" * 72)
    
    for regime in REGIMES:
        if regime not in combos: continue
        c = combos[regime]
        print(f"\n  {regime}:")
        for comp in c["components"]:
            print(f"    {comp['weight']*100:>5.1f}%  {comp['strategy']:<35} ({comp['role']})")
        if c["champion"] == "CASH":
            print(f"    fallback: cash_only (no strategy works in crisis)")
        else:
            print(f"    champion thesis: {c['champion_thesis']}")
    
    print("\n[6] Validating on holdout...")
    for regime in REGIMES:
        if regime not in combos: continue
        v = validate_combo(combos[regime], strategies, regime_map, regime)
        if v:
            print(f"  {regime}: holdout SR={v['sr']:.2f}, DD={v['dd']:.1f}%, n={v['n']}")
            if "combo_vs_champion" in v:
                ratio = v["combo_vs_champion"]
                marker = "✅" if ratio >= 1.0 else "⚠️"
                print(f"    {marker} combo/champion: {ratio:.2f} (champion SR={v['champion_sr']:.2f})")
            combos[regime]["validation"] = v
    
    # Save
    out = Path("research_lab/logs/researcher_v3/role_combos.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "role-based (thesis champion per regime)",
        "regime_counts": dict(counts),
        "combos": combos,
    }, indent=2, ensure_ascii=False))
    print(f"\n💾 saved: {out}")
    
    return combos


if __name__ == "__main__":
    main()
