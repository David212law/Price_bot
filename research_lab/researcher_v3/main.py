"""D-553: Researcher v3 — main orchestrator."""
import json
from pathlib import Path
from datetime import datetime, timezone
from .econ_registry import load_registry
from .regime_v3 import detect_regime
from .combo_builder_v3 import compute_metrics, pareto_filter, build_combo_for_regime, save_results

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

def load_profiler_strategies():
    if not STATE_PATH.exists():
        return {}
    state = json.loads(STATE_PATH.read_text())
    done = state.get("done", {})
    strategies = {}
    for key, v in done.items():
        if not isinstance(v, dict):
            continue
        val = v.get("validation", {})
        sr = val.get("sharpe_ann", 0)
        if sr < 2:
            continue
        if v.get("status") != "profiled":
            continue
        parts = key.split(":")
        if len(parts) < 4:
            continue
        exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
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
    combos = {}
    for regime in ["TREND_UP", "TREND_DOWN", "RANGE_LOW_VOL", "RANGE_MED_VOL", "CRISIS_NEGATIVE_FUNDING"]:
        combo = build_combo_for_regime(regime, pareto, all_returns, metrics, CRISIS_WINDOWS)
        if combo and "error" not in combo:
            combos[regime] = combo
            comps = ", ".join(f"{c['strategy']}@{c['weight']:.0%}" for c in combo["components"])
            print(f"  {regime:<28} → {comps}")
            print(f"    Coverage: {combo['coverage']}/16")
    print("\n[6] Saving results...")
    save_results({"combos": combos, "pareto": pareto})
    print(f"  ✅ research_lab/logs/researcher_v3/combo_recipes.json")
    print("\n" + "=" * 72)
    print(f" ✅ Researcher v3 complete: {len(combos)} combos")
    print("=" * 72)
    return combos

if __name__ == "__main__":
    main()
