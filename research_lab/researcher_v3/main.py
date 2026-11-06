"""D-558: Researcher v3 — Full orchestration with live data + Bale."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Existing
from .econ_registry import load_registry
from .combo_builder_v3 import compute_metrics, pareto_filter, build_combo_for_regime, save_results

# New
from .data_hub import fetch_all
from .bale_reporter import send_bale, format_report
from .per_exchange import test_per_exchange
from .generator import generate_strategies


STATE_PATH = Path("research_lab/logs/profiles/state.json")
RETURNS_DIR = Path("research_lab/logs/profiles/returns_matrices")

CRISIS_WINDOWS = {
    "LUNA": ("2022-05-01", "2022-06-15"),
    "FTX": ("2022-11-01", "2022-11-30"),
    "Ukraine": ("2022-02-20", "2022-03-15"),
    "Rate_Hikes": ("2022-06-01", "2022-10-31"),
}

BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE",
             "FUNDING_MEAN_REV", "FUNDING_ZSCORE", "FUNDING_CARRY"]  # D-560: FUNDING_* = artifact


def load_profiler_strategies():
    if not STATE_PATH.exists(): return {}
    state = json.loads(STATE_PATH.read_text())
    done = state.get("done", {})
    strategies = {}
    
    # Load M31 hedged as base
    for exch in ["hyperliquid", "aster", "kucoin"]:
        for f in (RETURNS_DIR / exch).glob("M31_EMA_*_BTC*.json"):
            try:
                rets = json.loads(f.read_text())
                if len(rets) >= 60:
                    strategies[f"M31_HEDGED_{exch}"] = {"returns": rets, "exchange": exch}
                    break
            except: pass
    
    # Load all valid from profiler
    for key, v in done.items():
        if not isinstance(v, dict): continue
        if v.get("status") not in ("profiled", "validated"): continue
        parts = key.split(":")
        if len(parts) < 4: continue
        exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
        if strat in BLACKLIST or strat.startswith("M31_"): continue
        val = v.get("validation", {})
        if not isinstance(val, dict): continue
        if val.get("sharpe_ann", 0) < 2: continue
        ret_file = RETURNS_DIR / exch / f"{strat}_{h}_{sym}.json"
        if not ret_file.exists(): continue
        try:
            rets = json.loads(ret_file.read_text())
            if len(rets) >= 60:
                name = f"{strat}_{sym}"
                if name not in strategies:
                    strategies[name] = {"returns": rets, "exchange": exch, "symbol": sym}
        except: pass
    return strategies


def compute_all_metrics(strategies):
    metrics = {}
    for name, data in strategies.items():
        m = compute_metrics(data["returns"], CRISIS_WINDOWS)
        if m: metrics[name] = m
    return metrics


def get_family(name):
    if name.startswith("M31"): return "M31"
    if name.startswith("KELTNER"): return "KELTNER"
    return name.split("_")[0]


def main():
    print("=" * 72)
    print(f" D-558: Researcher v3 — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 72)
    
    # Phase 1: Live data
    print("\n[1] Live data from exchanges...")
    live_data = fetch_all()
    live_ok = sum(1 for d in live_data.values() if "error" not in d)
    print(f"  {live_ok}/4 exchanges OK")
    for exch, d in live_data.items():
        status = "✅" if "error" not in d else f"❌ {d['error'][:30]}"
        print(f"  {exch}: {status}")
    
    # Phase 2: Generate candidates
    print("\n[2] Generating strategy candidates...")
    candidates = generate_strategies()
    print(f"  {len(candidates)} candidates generated")
    
    # Phase 3: Load profiler + metrics
    print("\n[3] Loading profiler strategies...")
    strategies = load_profiler_strategies()
    print(f"  {len(strategies)} valid strategies")
    
    print("\n[4] Computing metrics...")
    metrics = compute_all_metrics(strategies)
    print(f"  {len(metrics)} metrics computed")
    
    # Phase 4: Pareto
    print("\n[5] Pareto filter...")
    pareto = []
    _all_exch = set(s.get("exchange") for s in strategies.values() if s.get("exchange"))
    for _exch in sorted(_all_exch):
        _exch_keys = [k for k in metrics if strategies.get(k, {}).get("exchange") == _exch]
        if _exch_keys:
            _exch_metrics = {k: metrics[k] for k in _exch_keys}
            _exch_pareto = pareto_filter(_exch_keys, _exch_metrics)
            pareto.extend(_exch_pareto)
            print(f"  per-exchange Pareto [{_exch}]: {len(_exch_pareto)}")
    print(f"  {len(pareto)} strategies on Pareto front")
    
    # Phase 5: Family diversity
    family_best = {}
    for name in pareto:
        fam = get_family(name)
        if fam not in family_best or metrics[name]["sr"] > metrics[family_best[fam]]["sr"]:
            family_best[fam] = name
    pareto = list(family_best.values())
    print(f"  {len(pareto)} after family diversity: {pareto}")
    
    # Phase 6: Per-exchange
    print("\n[6] Per-exchange testing...")
    per_exchange = test_per_exchange()
    for exch, info in per_exchange.items():
        print(f"  {exch}: {info['n_strategies']} strategies (best: {info['best'][:40]})")
    
    # Phase 7: Combos per regime
    print("\n[7] Building combos per regime...")
    all_returns = {name: data["returns"] for name, data in strategies.items()}
    combos = {}
    for regime in ["TREND_UP", "TREND_DOWN", "RANGE_LOW_VOL", "RANGE_MED_VOL",
                   "RANGE_HIGH_VOL", "CRISIS_NEGATIVE_FUNDING", "CRISIS_VOL_SPIKE"]:
        combo = build_combo_for_regime(regime, pareto, all_returns, metrics, CRISIS_WINDOWS)
        if combo and "error" not in combo:
            combos[regime] = combo
            comps = ", ".join(f"{c['strategy']}@{c['weight']:.0%}" for c in combo["components"])
            print(f"  {regime}: {comps[:70]} [{combo.get('coverage', '?')}/16]")
    
    # Phase 8: Save
    print("\n[8] Saving results...")
    save_results({"combos": combos, "pareto": pareto, "per_exchange": per_exchange})
    print(f"  ✅ saved")
    
    # Phase 9: Bale notification
    print("\n[9] Sending Bale notification...")
    report = format_report(combos, pareto, live_data, per_exchange)
    bale_ok = send_bale(report)
    print(f"  {'✅ sent' if bale_ok else '⚠️ failed'}")
    
    return combos


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        # Try to notify Bale about failure
        try:
            from .bale_reporter import send_bale
            send_bale(f"❌ Researcher v3 failed: {str(e)[:200]}")
        except: pass
        sys.exit(1)
