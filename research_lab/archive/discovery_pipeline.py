"""D-525: Discovery Pipeline — Stage 2 (improvement filters).

Pipeline stages:
  Stage 1: edge signature  (uses composer.filter_candidates)
  Stage 2: improvement     (momentum, vol_low, vol_high, regime) ← THIS FILE
  Stage 3: combination     (uses composer.build_combination)
  
Output: per-strategy proposals (improvements + combos) → pending_review.json
"""
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ═════════════════════════════════════════════════════════════════════
# Thresholds — all based on what we TESTED to work
# ═════════════════════════════════════════════════════════════════════
THRESHOLDS = {
    "min_coverage":        0.30,   # from D-522/D-523
    "min_improvement_pct": 15.0,   # from D-522 (M31_MOMENTUM: +63%)
    "min_baseline_sr":     1.5,    # from D-523
    "max_baseline_sr":     8.0,    # skip already-optimal (M31 SR=13)
    "fee_per_transition":  0.001,  # 0.1% roundtrip
    "holdout_fraction":    0.30,   # 70/30 split
    "min_holdout_improvement_pct": 10.0,  # must replicate in holdout
}


def sharpe(values):
    if len(values) < 10: return 0.0
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / len(values)
    sd = v ** 0.5
    return (m / sd) * (365 ** 0.5) if sd > 0 else 0.0


def sharpe_with_fees(returns_dict, fee_per_transition=0.001):
    """Sharpe on full range with padded zeros and per-transition fees."""
    if not returns_dict: return {"sr": 0, "coverage": 0, "n_active": 0}
    dates = sorted(returns_dict.keys())
    start = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(dates[-1], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    all_days = []
    d = start
    while d <= end:
        all_days.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    vals = [returns_dict.get(dd, 0.0) for dd in all_days]
    n_active = sum(1 for v in vals if abs(v) > 1e-9)
    trans = sum(1 for i in range(1, len(vals)) if (vals[i] > 0) != (vals[i-1] > 0))
    fee_drag = trans * fee_per_transition
    fee_per_day = fee_drag / len(all_days) if all_days else 0
    adj = [v - fee_per_day for v in vals]
    return {
        "sr": round(sharpe(adj), 2),
        "coverage": round(n_active / len(all_days), 2) if all_days else 0,
        "n_active": n_active,
        "n_total": len(all_days),
        "transitions": trans,
    }


# ═════════════════════════════════════════════════════════════════════
# Improvement Filters (Stage 2)
# ═════════════════════════════════════════════════════════════════════
def momentum_filter(returns, lookback=20):
    """Trade only when past 20d mean > 0 (no look-ahead)."""
    dates = sorted(returns.keys())
    filtered = {}
    for i, d in enumerate(dates):
        past = [returns[dates[j]] for j in range(max(0, i - lookback), i)]
        mean_past = sum(past) / len(past) if past else 0
        filtered[d] = returns[d] if mean_past > 0 else 0.0
    return filtered


def vol_filter(returns, btc_daily, keep_low=True):
    if not btc_daily: return returns
    abs_rets = sorted(abs(r) for r in btc_daily.values())
    median_abs = abs_rets[len(abs_rets) // 2] if abs_rets else 0
    threshold = median_abs * 1.5
    filtered = {}
    for d, r in returns.items():
        btc_r = btc_daily.get(d, 0)
        is_high = abs(btc_r) > threshold
        keep = (not is_high) if keep_low else is_high
        filtered[d] = r if keep else 0.0
    return filtered


def regime_filter(returns, regime_map, keep_regime):
    return {
        d: (r if regime_map.get(d) == keep_regime else 0.0)
        for d, r in returns.items()
    }


# ═════════════════════════════════════════════════════════════════════
# Validation (70/30 time split)
# ═════════════════════════════════════════════════════════════════════
def validate_improvement(original, filtered, fee_per_transition=0.001):
    """Split into 70% train / 30% holdout. Improvement must hold in BOTH."""
    if not original or not filtered: return None
    dates = sorted(original.keys())
    n = len(dates)
    split = int(n * (1 - THRESHOLDS["holdout_fraction"]))
    
    train_dates = dates[:split]
    test_dates = dates[split:]
    
    if len(train_dates) < 50 or len(test_dates) < 20:
        return None
    
    # Baseline and filtered on train
    orig_train = {d: original[d] for d in train_dates}
    filt_train = {d: filtered[d] for d in train_dates}
    
    # Baseline and filtered on test
    orig_test = {d: original[d] for d in test_dates}
    filt_test = {d: filtered[d] for d in test_dates}
    
    base_train = sharpe_with_fees(orig_train, fee_per_transition)
    filt_train_r = sharpe_with_fees(filt_train, fee_per_transition)
    base_test = sharpe_with_fees(orig_test, fee_per_transition)
    filt_test_r = sharpe_with_fees(filt_test, fee_per_transition)
    
    if base_train["sr"] <= 0 or base_test["sr"] <= 0:
        return None
    
    imp_train = (filt_train_r["sr"] / base_train["sr"] - 1) * 100
    imp_test = (filt_test_r["sr"] / base_test["sr"] - 1) * 100
    
    # Both must improve, test coverage must be adequate
    if imp_train < THRESHOLDS["min_improvement_pct"]: return None
    if imp_test < THRESHOLDS["min_holdout_improvement_pct"]: return None
    if filt_test_r["coverage"] < THRESHOLDS["min_coverage"]: return None
    
    return {
        "train_improvement_pct": round(imp_train, 1),
        "test_improvement_pct": round(imp_test, 1),
        "test_coverage": filt_test_r["coverage"],
        "filtered_train_sr": filt_train_r["sr"],
        "filtered_test_sr": filt_test_r["sr"],
        "baseline_train_sr": base_train["sr"],
        "baseline_test_sr": base_test["sr"],
    }


# ═════════════════════════════════════════════════════════════════════
# Main pipeline
# ═════════════════════════════════════════════════════════════════════
def load_btc_daily(exchange="hyperliquid", symbol="BTC"):
    from strategies.core_engine import load_data
    btc = load_data(exchange, symbol)
    if not btc: return {}
    prices = defaultdict(list)
    for c in btc:
        if not isinstance(c, dict): continue
        t = c.get("t"); close = c.get("c")
        if t and close:
            day = datetime.fromtimestamp(int(t) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[day].append(float(close))
    sorted_days = sorted(prices.keys())
    rets = {}
    for i in range(1, len(sorted_days)):
        prev = prices[sorted_days[i-1]][-1]
        curr = prices[sorted_days[i]][-1]
        if prev > 0:
            rets[sorted_days[i]] = (curr - prev) / prev
    return rets


def load_returns_file(exchange, strategy, hash_val, symbol):
    p = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}/{strategy}_{hash_val}_{symbol}.json")
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except: return {}


def run_stage_2(exchange, strategy, hash_val, symbol, btc_daily, regime_map):
    """Stage 2: Try all improvement filters on ONE strategy."""
    returns = load_returns_file(exchange, strategy, hash_val, symbol)
    if not returns or len(returns) < 60: return None
    
    base = sharpe_with_fees(returns)
    if base["sr"] < THRESHOLDS["min_baseline_sr"]: return None
    if base["sr"] > THRESHOLDS["max_baseline_sr"]: return None
    
    proposals = []
    filters = [
        ("momentum", momentum_filter(returns)),
        ("vol_low", vol_filter(returns, btc_daily, keep_low=True)),
        ("vol_high", vol_filter(returns, btc_daily, keep_low=False)),
        ("regime_TREND", regime_filter(returns, regime_map, "TREND")),
        ("regime_RANGE", regime_filter(returns, regime_map, "RANGE")),
        ("regime_NEUTRAL", regime_filter(returns, regime_map, "NEUTRAL")),
    ]
    
    for fname, filtered in filters:
        result = validate_improvement(returns, filtered)
        if result:
            proposals.append({
                "filter": fname,
                "train_improvement_pct": result["train_improvement_pct"],
                "test_improvement_pct": result["test_improvement_pct"],
                "test_coverage": result["test_coverage"],
                "baseline_train_sr": result["baseline_train_sr"],
                "baseline_test_sr": result["baseline_test_sr"],
                "filtered_train_sr": result["filtered_train_sr"],
                "filtered_test_sr": result["filtered_test_sr"],
            })
    
    if not proposals: return None
    
    return {
        "exchange": exchange,
        "strategy": strategy,
        "hash": hash_val,
        "symbol": symbol,
        "baseline_sr": base["sr"],
        "proposals": proposals,
    }


def main():
    print("=" * 78)
    print(" Discovery Pipeline — Stage 2 (Improvement Filters)")
    print("=" * 78)
    print(f"Thresholds:")
    for k, v in THRESHOLDS.items():
        print(f"  {k}: {v}")
    print()
    
    # Load context
    btc_daily = load_btc_daily()
    from research_lab.composer import regime_by_date, load_state, filter_candidates
    regime_map = regime_by_date("hyperliquid")
    print(f"[PREP] BTC={len(btc_daily)}d, regime={len(regime_map)}d\n")
    
    # Stage 1: filter_candidates (proven)
    state = load_state()
    all_survivors = []
    for exchange in ["hyperliquid", "aster", "kucoin"]:
        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            cands = filter_candidates(state, regime, exchange)
            for c in cands:
                key = (c["strategy"], c["hash"], c["symbol"], exchange)
                if key not in [(s["strategy"], s["hash"], s["symbol"], s["exchange"]) for s in all_survivors]:
                    all_survivors.append({
                        "strategy": c["strategy"],
                        "hash": c["hash"],
                        "symbol": c["symbol"],
                        "exchange": exchange,
                    })
    
    print(f"STAGE 1 (edge signature): {len(all_survivors)} survivors")
    for s in all_survivors:
        print(f"  {s['strategy']:25s} {s['symbol']:10s} {s['exchange']}")
    print()
    
    # Stage 2: improvements
    print("STAGE 2 (improvement filters)...")
    stage2_results = []
    for s in all_survivors:
        result = run_stage_2(s["exchange"], s["strategy"], s["hash"], s["symbol"],
                             btc_daily, regime_map)
        if result:
            stage2_results.append(result)
            print(f"  ✅ {s['strategy']:25s} {s['symbol']:10s}: {len(result['proposals'])} improvements")
    
    if not stage2_results:
        print("  ⚠️  No improvements found in Stage 2")
        print("  → Strategies are already optimal OR too small sample")
    print()
    
    # Save proposals
    out = Path("research_lab/logs/discovery_proposals.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage1_survivors": all_survivors,
        "stage2_proposals": stage2_results,
    }, indent=2))
    
    print(f"[SAVE] {out}")
    print()
    print("=" * 78)
    print(f" VERDICT: {len(stage2_results)} strategies have improvement proposals")
    print("=" * 78)
    print()
    print("Next: review discovery_proposals.json, then Stage 3 (combine) runs")
    print("      via composer.build_combination on the improved strategies.")


if __name__ == "__main__":
    main()
