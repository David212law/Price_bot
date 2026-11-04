"""D-523: Strategy Optimizer — does filter-based optimization generalize?

Test on 5 strategies with 3 universal filters (all applied fairly with
zero-padding and fee-per-transition):
  1. Return-momentum: trade only when past returns mean > 0 (no look-ahead)
  2. Vol filter: trade only in low-vol (BTC |ret| < 1.5x median) days
  3. Regime filter: trade only in the best of TREND/RANGE/NEUTRAL

If >=3/5 improve by >20%, method generalizes.
If only 1-2/5 → M31_MOMENTUM was strategy-specific, not a method.
"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def load_btc_daily(exchange="hyperliquid", symbol="BTC"):
    from strategies.core_engine import load_data
    btc = load_data(exchange, symbol)
    if not btc:
        return {}
    daily_prices = defaultdict(list)
    for c in btc:
        if not isinstance(c, dict):
            continue
        t = c.get("t")
        close = c.get("c")
        if t and close:
            day = datetime.fromtimestamp(int(t) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            daily_prices[day].append(float(close))
    sorted_days = sorted(daily_prices.keys())
    btc_daily = {}
    for i in range(1, len(sorted_days)):
        prev = daily_prices[sorted_days[i - 1]][-1]
        curr = daily_prices[sorted_days[i]][-1]
        if prev > 0:
            btc_daily[sorted_days[i]] = (curr - prev) / prev
    return btc_daily


def load_hash_files(exchange, strategy):
    base = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}")
    if not base.exists():
        return []
    return sorted(base.glob(f"{strategy}_*.json"))


def read_returns(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def sharpe_padded(returns, fee_per_transition=0.001):
    if not returns:
        return {"sr": 0, "return_pct": 0, "transitions": 0, "active_days": 0, "full_days": 0}
    dates = sorted(returns.keys())
    start = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(dates[-1], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    all_days = []
    d = start
    while d <= end:
        all_days.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    active = sum(1 for dd in all_days if abs(returns.get(dd, 0)) > 1e-9)
    vals = [returns.get(dd, 0.0) for dd in all_days]
    transitions = sum(1 for i in range(1, len(vals)) if (vals[i] > 0) != (vals[i - 1] > 0))
    fee_drag = transitions * fee_per_transition
    fee_per_day = fee_drag / len(all_days) if all_days else 0
    adj = [v - fee_per_day for v in vals]
    m = sum(adj) / len(adj) if adj else 0
    sd = (sum((x - m) ** 2 for x in adj) / len(adj)) ** 0.5 if adj else 0
    sr = (m / sd) * (365 ** 0.5) if sd > 0 else 0
    return {
        "sr": round(sr, 2),
        "return_pct": round((sum(vals) - fee_drag) * 100, 2),
        "transitions": transitions,
        "active_days": active,
        "full_days": len(all_days),
    }


def momentum_filter(returns, lookback=20):
    """Trade only when past returns mean > 0. No look-ahead."""
    dates = sorted(returns.keys())
    filtered = {}
    for i, d in enumerate(dates):
        past = [returns[dates[j]] for j in range(max(0, i - lookback), i)]
        mean_past = sum(past) / len(past) if past else 0
        filtered[d] = returns[d] if mean_past > 0 else 0.0
    return filtered


def vol_filter(returns, btc_daily, keep_low=True):
    if not btc_daily:
        return returns
    abs_rets = sorted(abs(r) for r in btc_daily.values())
    median_abs = abs_rets[len(abs_rets) // 2]
    threshold = median_abs * 1.5
    filtered = {}
    for d, r in returns.items():
        btc_r = btc_daily.get(d, 0)
        is_high = abs(btc_r) > threshold
        filtered[d] = r if ((keep_low and not is_high) or (not keep_low and is_high)) else 0.0
    return filtered


def regime_filter(returns, regime_map, keep_regime):
    filtered = {}
    for d, r in returns.items():
        filtered[d] = r if regime_map.get(d) == keep_regime else 0.0
    return filtered


def analyze_strategy(exchange, strategy, btc_daily, regime_map):
    files = load_hash_files(exchange, strategy)
    if not files:
        return None
    best_baseline = {"sr": -999, "file": None}
    best_per_filter = defaultdict(lambda: {"sr": -999, "file": None})

    for path in files:
        returns = read_returns(path)
        if not returns or len(returns) < 30:
            continue
        base = sharpe_padded(returns)
        if base["sr"] < 1.0:
            continue
        if base["sr"] > best_baseline["sr"]:
            best_baseline = {"file": path.name, **base}

        for fname, filtered in [
            ("momentum", momentum_filter(returns)),
            ("vol_low", vol_filter(returns, btc_daily, keep_low=True)),
            ("vol_high", vol_filter(returns, btc_daily, keep_low=False)),
        ]:
            r = sharpe_padded(filtered)
            if r["sr"] > best_per_filter[fname]["sr"]:
                best_per_filter[fname] = {"file": path.name, **r}

        for reg in ["TREND", "RANGE", "NEUTRAL"]:
            r = sharpe_padded(regime_filter(returns, regime_map, reg))
            key = f"regime_{reg}"
            if r["sr"] > best_per_filter[key]["sr"]:
                best_per_filter[key] = {"file": path.name, **r, "regime": reg}

    if best_baseline["sr"] <= -999:
        return None
    return {"baseline": best_baseline, "filters": dict(best_per_filter)}


def main():
    print("=" * 80)
    print(" STRATEGY OPTIMIZER — D-523: filter-based optimization generalization test")
    print("=" * 80)
    print("\n[PREP] Loading BTC daily + regime map...")
    btc_daily = load_btc_daily()
    from research_lab.composer import regime_by_date
    regime_map = regime_by_date("hyperliquid")
    print(f"  BTC daily: {len(btc_daily)} days")
    print(f"  Regime map: {len(regime_map)} days")

    strategies = ["KELTNER_REV", "ROC", "BOLLINGER", "DUAL_MOMENTUM", "M31_MOMENTUM"]
    summary = []

    for strat in strategies:
        print(f"\n{'=' * 80}")
        print(f" {strat}")
        print("=" * 80)
        result = analyze_strategy("hyperliquid", strat, btc_daily, regime_map)
        if not result:
            print(f"  ⚠️  No qualifying data")
            summary.append({"strategy": strat, "baseline_sr": 0, "best_sr": 0,
                            "improvement_pct": 0, "best_filter": None, "coverage": 0})
            continue
        base = result["baseline"]
        print(f"  Baseline: SR={base['sr']:.2f} return={base['return_pct']:+.2f}% "
              f"active={base['active_days']}/{base['full_days']} trans={base['transitions']}")
        print(f"  File: {base['file']}\n")

        best_sr = base["sr"]
        best_filter = None
        best_coverage = 1.0
        for fname in ["momentum", "vol_low", "vol_high", "regime_TREND", "regime_RANGE", "regime_NEUTRAL"]:
            if fname not in result["filters"]:
                continue
            r = result["filters"][fname]
            if r["sr"] <= -999:
                continue
            imp = (r["sr"] / base["sr"] - 1) * 100 if base["sr"] > 0 else 0
            coverage = r["active_days"] / base["active_days"] if base["active_days"] > 0 else 0
            marker = "★" if r["sr"] > best_sr else " "
            warn = " ⚠low_coverage" if coverage < 0.3 else ""
            print(f"  {marker} {fname:15s} SR={r['sr']:6.2f} ({imp:+7.1f}%) "
                  f"active={r['active_days']:3d} coverage={coverage:.0%}{warn}")
            if r["sr"] > best_sr:
                best_sr = r["sr"]
                best_filter = fname
                best_coverage = coverage
        imp = (best_sr / base["sr"] - 1) * 100 if base["sr"] > 0 else 0
        summary.append({"strategy": strat, "baseline_sr": base["sr"], "best_sr": best_sr,
                        "improvement_pct": imp, "best_filter": best_filter,
                        "coverage": best_coverage})

    print("\n" + "=" * 80)
    print(" SUMMARY")
    print("=" * 80)
    print(f"{'Strategy':18s} {'Base':>7s} {'Best':>7s} {'Improv':>8s} {'Filter':>15s} {'Coverage':>9s}")
    print("-" * 80)
    improved = 0
    for s in summary:
        print(f"{s['strategy']:18s} {s['baseline_sr']:>7.2f} {s['best_sr']:>7.2f} "
              f"{s['improvement_pct']:>+7.1f}% {s['best_filter'] or '-':>15s} {s['coverage']:>8.0%}")
        if s["improvement_pct"] >= 20 and s["coverage"] >= 0.3:
            improved += 1
    print("\n" + "=" * 80)
    print(f" VERDICT: {improved}/{len(summary)} strategies improve >=20% with >=30% coverage")
    print("=" * 80)
    if improved >= 3:
        print(" ✅ METHOD GENERALIZES")
        print("    → Add StrategyOptimizer to research pipeline (D-523 PASS)")
    elif improved >= 2:
        print(" ⚠️  PARTIALLY GENERALIZES — test more strategies")
    else:
        print(" ❌ DOES NOT GENERALIZE")
        print("    → M31_MOMENTUM was strategy-specific, not universal")


if __name__ == "__main__":
    main()
