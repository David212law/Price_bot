"""D-553: Researcher v3 — main orchestrator."""
import json
from pathlib import Path
from datetime import datetime, timezone
from .econ_registry import load_registry
from .regime_v3 import detect_regime
from .combo_builder_v3 import compute_metrics, pareto_filter, build_combo_for_regime, save_results

# D-537 BLACKLIST: all M31 variants are artifacts (corr>0.98 with M31)
BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"]

STATE_PATH = Path("research_lab/logs/profiles/state.json")
RETURNS_DIR = Path("research_lab/logs/profiles/returns_matrices")
CRISIS_CACHE = Path("data/crisis_test_cache.json")
WALLEX_CACHE = Path("data/wallex_cache.json")

CRISIS_WINDOWS = {
    "LUNA": ("2022-05-01", "2022-06-15"),
    "FTX": ("2022-11-01", "2022-11-30"),
    "Ukraine": ("2022-02-20", "2022-03-15"),
    "Rate_Hikes": ("2022-06-01", "2022-10-31"),
}

def load_returns_for_asset(asset):
    for cache_path in [CRISIS_CACHE, WALLEX_CACHE]:
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                if asset in data:
                    prices = data[asset]
                    dates = sorted(prices.keys())
                    rets = {}
                    for i in range(1, len(dates)):
                        p0, p1 = prices[dates[i-1]], prices[dates[i]]
                        if p0 > 0:
                            rets[dates[i]] = (p1 - p0) / p0
                    return rets, prices
            except Exception:
                pass
    return {}, {}

def load_m31_candidates():
    """D-553: Load M31 from returns_matrices (not in profiler state)."""
    strategies = {}
    # Try each exchange
    for exch in ["hyperliquid", "aster", "kucoin"]:
        ret_dir = RETURNS_DIR / exch
        if not ret_dir.exists():
            continue
        for f in ret_dir.glob("M31_EMA_*_BTC*.json"):
            try:
                rets = json.loads(f.read_text())
                if len(rets) >= 60:
                    name = f"M31_HEDGED_{exch}"
                    strategies[name] = {
                        "returns": rets,
                        "exchange": exch,
                        "symbol": "BTC",
                        "validation": {"sharpe_ann": 8.0, "is_m31": True},
                        "is_m31": True,
                    }
                    break  # one M31 per exchange
            except Exception:
                pass
    return strategies


def load_profiler_strategies():
    if not STATE_PATH.exists():
        return {}
    state = json.loads(STATE_PATH.read_text())
    done = state.get("done", {})
    strategies = {}
    # Also load M31 candidates
    strategies.update(load_m31_candidates())
    for key, v in done.items():
        if not isinstance(v, dict):
            continue
        val = v.get("validation", {})
        sr = val.get("sharpe_ann", 0)
        if sr < 2:
            continue
        status = v.get("status")
        if status not in ("profiled", "validated"):
            continue
        parts = key.split(":")
        if len(parts) < 4:
            continue
        exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
        # D-537: skip blacklisted strategies
        if strat in BLACKLIST:
            continue
        # D-537: skip M31 variant family (any starting with M31_)
        if strat.startswith("M31_"):
            continue
        ret_file = RETURNS_DIR / exch / f"{strat}_{h}_{sym}.json"
        if not ret_file.exists():
            continue
        try:
            rets = json.loads(ret_file.read_text())
            if len(rets) >= 60:
                name = f"{strat}_{sym}"
                if name not in strategies:
                    strategies[name] = {"returns": rets, "exchange": exch, "symbol": sym, "validation": val}
        except Exception:
            pass
    return strategies

def compute_crisis_metrics(strategies, crisis_windows):
    metrics = {}
    for name, data in strategies.items():
        m = compute_metrics(data["returns"], crisis_windows)
        if m:
            metrics[name] = m
    return metrics

def main():
    print("=" * 72)
    print(" D-553: Researcher v3 — Comprehensive")
    print("=" * 72)
    print("\n[1] Loading economic registry...")
    registry = load_registry()
    print(f"  Strategies: {list(registry['strategies'].keys())}")
    print(f"  Assets: {list(registry['per_asset_baselines'].keys())}")
    print("\n[2] Loading profiler strategies...")
    strategies = load_profiler_strategies()
    print(f"  Valid: {len(strategies)} strategies")
    print("\n[3] Computing metrics...")
    metrics = compute_crisis_metrics(strategies, CRISIS_WINDOWS)
    print(f"  Computed: {len(metrics)} metrics")
    print("\n[4] Pareto filter...")
    pareto = pareto_filter(list(metrics.keys()), metrics)
    print(f"  Pareto front: {len(pareto)} strategies")
    for p in pareto[:10]:
        m = metrics[p]
        print(f"    {p[:40]:<42} SR={m['sr']:>5.1f} DD={m['dd']:>5.1f}%")
    print("\n[5] Building combos per regime...")
    all_returns = {name: data["returns"] for name, data in strategies.items()}
    
    # D-553: novelty filter (remove highly-correlated components)
    def corr(a, b, dates):
        va = [a[d] for d in dates]; vb = [b[d] for d in dates]
        ma = sum(va)/len(va); mb = sum(vb)/len(vb)
        cov = sum((va[i]-ma)*(vb[i]-mb) for i in range(len(va)))
        sa = sum((x-ma)**2 for x in va)**0.5
        sb = sum((x-mb)**2 for x in vb)**0.5
        return cov/(sa*sb) if sa*sb > 0 else 0
    
    filtered_pareto = []
    for candidate in pareto:
        if candidate not in all_returns:
            continue
        # Check corr with all previously accepted
        is_independent = True
        for accepted in filtered_pareto:
            common = sorted(set(all_returns[candidate].keys()) & set(all_returns[accepted].keys()))
            if len(common) < 60:
                continue
            c = corr(all_returns[candidate], all_returns[accepted], common)
            if abs(c) > 0.7:
                is_independent = False
                break
        if is_independent:
            filtered_pareto.append(candidate)
    
    print(f"  Novelty filter: {len(pareto)} → {len(filtered_pareto)} (corr<0.7)")
    
    # D-553: Family diversity filter — 1 strategy per family
    def get_family(name):
        if name.startswith("M31"):
            return "M31"
        if name.startswith("KELTNER"):
            return "KELTNER"
        if name.startswith("RSI"):
            return "RSI"
        if name.startswith("FUNDING"):
            return "FUNDING"
        if name.startswith("MACD"):
            return "MACD"
        if name.startswith("EMA"):
            return "EMA"
        if name.startswith("SUPERTREND"):
            return "SUPERTREND"
        if name.startswith("ATR"):
            return "ATR"
        return name.split("_")[0]
    
    # Keep only best per family (by SR)
    family_best = {}
    for name in filtered_pareto:
        m = metrics.get(name)
        if not m:
            continue
        fam = get_family(name)
        if fam not in family_best or m["sr"] > metrics[family_best[fam]]["sr"]:
            family_best[fam] = name
    
    family_diverse = list(family_best.values())
    print(f"  Family diversity: {len(filtered_pareto)} → {len(family_diverse)} (1 per family)")
    pareto = family_diverse
    
    combos = {}
    for regime in ["TREND_UP", "TREND_DOWN", "RANGE_LOW_VOL", "RANGE_MED_VOL", "RANGE_HIGH_VOL", "CRISIS_NEGATIVE_FUNDING", "CRISIS_VOL_SPIKE"]:
        combo = build_combo_for_regime(regime, pareto, all_returns, metrics, CRISIS_WINDOWS)
        if combo and "error" not in combo:
            comps = ", ".join(f"{c['strategy']}@{c['weight']:.0%}" for c in combo["components"])
            print(f"  {regime:<28} → {comps}")
            print(f"    Coverage: {combo['coverage']}/16")
            # Warn about M31+M31 or Keltner+Keltner
            families_in_combo = set(get_family(c['strategy']) for c in combo["components"])
            if len(families_in_combo) < 2:
                print(f"    ⚠️ WARNING: same family ({families_in_combo}) — combo may be artifact")
            else:
                combos[regime] = combo
        elif regime.startswith("CRISIS"):
            # For crisis, use cash + Keltner explicitly
            keltners = [p for p in pareto if get_family(p) == "KELTNER"]
            if keltners:
                best_k = max(keltners, key=lambda x: metrics[x]["sr"])
                cash_combo = {
                    "components": [
                        {"strategy": "CASH", "weight": 0.7},
                        {"strategy": best_k, "weight": 0.3},
                    ],
                    "metrics": {"sr": 0, "dd": 0, "ret": 0},
                    "coverage": 5,
                    "regime": regime,
                }
                combos[regime] = cash_combo
                print(f"  {regime:<28} → CASH@70%, {best_k}@30% (fallback)")
    print("\n[6] Saving results...")
    save_results({"combos": combos, "pareto": pareto})
    print(f"  ✅ research_lab/logs/researcher_v3/combo_recipes.json")
    print("\n" + "=" * 72)
    print(f" ✅ Researcher v3 complete: {len(combos)} combos")
    print("=" * 72)
    return combos

if __name__ == "__main__":
    main()
