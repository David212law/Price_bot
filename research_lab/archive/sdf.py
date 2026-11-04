"""D-524: Strategy Discovery Framework (SDF).

A GENERALIZABLE method to improve ANY strategy by learning from data:
  - Extract 10 features per trade (no look-ahead)
  - Train logistic regression to predict "above-median" trades
  - Apply learned filter to test data (30% holdout)
  - Report improvement per strategy

If many strategies improve → method generalizes.
If few → we learn the boundary of what's possible.
"""
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def sigmoid(z):
    if z > 500: return 1.0
    if z < -500: return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def logistic_train(X, y, lr=0.05, epochs=150, l2=0.001):
    if not X: return [], 0.0
    n_features = len(X[0])
    w = [0.0] * n_features
    b = 0.0
    for epoch in range(epochs):
        for i in range(len(X)):
            z = sum(w[j] * X[i][j] for j in range(n_features)) + b
            p = sigmoid(z)
            err = p - y[i]
            for j in range(n_features):
                w[j] -= lr * (err * X[i][j] + l2 * w[j])
            b -= lr * err
    return w, b


def logistic_predict(x, w, b):
    return sigmoid(sum(w[j] * x[j] for j in range(len(x))) + b)


def sharpe(values):
    if len(values) < 10: return 0.0
    m = sum(values) / len(values)
    var = sum((v - m) ** 2 for v in values) / len(values)
    sd = var ** 0.5
    return (m / sd) * (365 ** 0.5) if sd > 0 else 0.0


def load_btc_daily(exchange="hyperliquid", symbol="BTC"):
    from strategies.core_engine import load_data
    btc = load_data(exchange, symbol)
    if not btc: return {}
    daily_prices = defaultdict(list)
    for c in btc:
        if not isinstance(c, dict): continue
        t = c.get("t"); close = c.get("c")
        if t and close:
            day = datetime.fromtimestamp(int(t) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            daily_prices[day].append(float(close))
    sorted_days = sorted(daily_prices.keys())
    daily_rets = {}
    for i in range(1, len(sorted_days)):
        prev = daily_prices[sorted_days[i - 1]][-1]
        curr = daily_prices[sorted_days[i]][-1]
        if prev > 0:
            daily_rets[sorted_days[i]] = (curr - prev) / prev
    return daily_rets


def extract_features(strategy_returns, btc_daily, regime_map, lookback_min=60):
    """For each trade day, extract 10 features (all from data BEFORE that day)."""
    dates = sorted(strategy_returns.keys())
    rets = [strategy_returns[d] for d in dates]

    # Target threshold: top 40% of this strategy's returns
    sorted_rets = sorted(rets)
    p60_idx = int(len(sorted_rets) * 0.6)
    threshold = sorted_rets[p60_idx] if p60_idx < len(sorted_rets) else sorted_rets[-1]

    features, targets, feat_dates = [], [], []
    for i, d in enumerate(dates):
        if i < lookback_min: continue
        past_dates = dates[:i]
        prev_d = past_dates[-1]

        regime = regime_map.get(prev_d, "UNKNOWN")
        regime_oh = [1.0 if regime == r else 0.0 for r in ["TREND", "RANGE", "NEUTRAL"]]

        btc_ret = btc_daily.get(prev_d, 0.0)
        btc_vol = 1.0 if abs(btc_ret) > 0.015 else 0.0

        btc_20 = [btc_daily.get(pd, 0) for pd in past_dates[-20:]]
        btc_mom_20 = sum(btc_20) / len(btc_20) if btc_20 else 0.0

        btc_60 = [btc_daily.get(pd, 0) for pd in past_dates[-60:]]
        btc_mom_60 = sum(btc_60) / len(btc_60) if btc_60 else 0.0

        s_30 = [strategy_returns.get(pd, 0) for pd in past_dates[-30:]]
        s_mean = sum(s_30) / len(s_30) if s_30 else 0.0
        s_std = (sum((x - s_mean) ** 2 for x in s_30) / len(s_30)) ** 0.5 if s_30 else 0.0

        dow = datetime.strptime(d, "%Y-%m-%d").weekday()
        dow_sin = math.sin(2 * math.pi * dow / 7)
        dow_cos = math.cos(2 * math.pi * dow / 7)

        feature_vec = regime_oh + [
            btc_vol, btc_mom_20, btc_mom_60,
            s_mean, s_std, dow_sin, dow_cos,
        ]
        target = 1 if strategy_returns[d] > threshold else 0
        features.append(feature_vec)
        targets.append(target)
        feat_dates.append(d)
    return features, targets, feat_dates, threshold


def analyze_file(fpath, btc_daily, regime_map, min_days=150):
    """Analyze one strategy file with 70/30 time split."""
    try:
        returns = json.loads(fpath.read_text())
    except Exception:
        return None
    if not returns or len(returns) < min_days:
        return None

    feats, targets, dates, thr = extract_features(returns, btc_daily, regime_map)
    if len(feats) < 100: return None

    n = len(feats)
    split = int(n * 0.7)
    X_tr, y_tr = feats[:split], targets[:split]
    X_te, y_te = feats[split:], targets[split:]
    d_te = dates[split:]

    if len(X_te) < 30 or sum(y_te) < 5 or sum(y_tr) < 5:
        return None

    w, b = logistic_train(X_tr, y_tr, lr=0.05, epochs=150, l2=0.001)

    # Apply filter
    probs = [logistic_predict(x, w, b) for x in X_te]
    kept_dates = [d_te[i] for i in range(len(d_te)) if probs[i] > 0.55]
    kept_rets = [returns[d] for d in kept_dates]
    base_rets = [returns[d] for d in d_te]

    baseline_sr = sharpe(base_rets)
    filtered_sr = sharpe(kept_rets) if len(kept_rets) >= 10 else 0.0
    coverage = len(kept_dates) / len(d_te) if d_te else 0

    improvement = (filtered_sr / baseline_sr - 1) * 100 if baseline_sr > 0 else 0

    return {
        "file": fpath.name,
        "baseline_sr": round(baseline_sr, 2),
        "filtered_sr": round(filtered_sr, 2),
        "improvement_pct": round(improvement, 1),
        "coverage": round(coverage, 2),
        "n_test": len(d_te),
        "n_kept": len(kept_dates),
        "threshold": round(thr, 6),
    }


def main():
    print("=" * 78)
    print(" SDF — Strategy Discovery Framework (D-524)")
    print("=" * 78)
    print("Method: learn feature-based filter per strategy, 70/30 time split")
    print()

    print("[PREP] Loading BTC daily and regime map...")
    btc_daily = load_btc_daily()
    from research_lab.composer import regime_by_date
    regime_map = regime_by_date("hyperliquid")
    print(f"  BTC daily: {len(btc_daily)} days")
    print(f"  Regime map: {len(regime_map)} days\n")

    base_dir = Path("research_lab/logs/profiles/returns_matrices/hyperliquid")
    if not base_dir.exists():
        print(f"❌ {base_dir} not found")
        return

    files = sorted(base_dir.glob("*.json"))
    print(f"[SCAN] {len(files)} files in HL returns_matrices\n")

    results = []
    for fpath in files:
        r = analyze_file(fpath, btc_daily, regime_map)
        if r:
            results.append(r)

    print(f"[ANALYZED] {len(results)} files with sufficient data\n")

    # Filter to meaningful improvements
    improvements = [r for r in results if r["improvement_pct"] >= 15 and r["coverage"] >= 0.3]
    small_imp = [r for r in results if 5 <= r["improvement_pct"] < 15 and r["coverage"] >= 0.3]
    regressions = [r for r in results if r["improvement_pct"] <= -5]

    print("=" * 78)
    print(" RESULTS — IMPROVED (≥15% and ≥30% coverage)")
    print("=" * 78)
    if improvements:
        improvements.sort(key=lambda x: -x["improvement_pct"])
        for r in improvements[:15]:
            print(f"  {r['file']:45s} "
                  f"{r['baseline_sr']:5.2f} → {r['filtered_sr']:5.2f} "
                  f"({r['improvement_pct']:+.0f}%) cov={r['coverage']:.0%}")
    else:
        print("  (none)")

    print(f"\n[SMALL 5-15%] {len(small_imp)} files")
    print(f"[REGRESSIONS < -5%] {len(regressions)} files")

    # Group by strategy
    by_strat = defaultdict(list)
    for r in results:
        strat = r["file"].split("_")[0]
        if strat.startswith("M31") and "_" in r["file"]:
            parts = r["file"].split("_")
            if len(parts) > 1 and parts[0] == "M31":
                strat = f"M31_{parts[1]}"
        by_strat[strat].append(r)

    print("\n" + "=" * 78)
    print(" BY STRATEGY")
    print("=" * 78)
    for strat, rs in sorted(by_strat.items()):
        best = max(rs, key=lambda x: x["improvement_pct"])
        n_improved = sum(1 for r in rs if r["improvement_pct"] >= 15 and r["coverage"] >= 0.3)
        print(f"  {strat:20s} {n_improved:2d}/{len(rs):2d} improved, "
              f"best={best['improvement_pct']:+.0f}% ({best['file'][:30]})")

    # Verdict
    n_strategies = len(by_strat)
    n_gen = sum(1 for rs in by_strat.values()
                if any(r["improvement_pct"] >= 15 and r["coverage"] >= 0.3 for r in rs))

    print("\n" + "=" * 78)
    print(" VERDICT")
    print("=" * 78)
    print(f"  Strategies that improved (≥1 file): {n_gen}/{n_strategies}")
    print(f"  Files that improved (≥15%, ≥30% cov): {len(improvements)}/{len(results)}")
    pct = 100 * n_gen / n_strategies if n_strategies > 0 else 0
    if pct >= 40:
        print(f"\n  ✅ METHOD GENERALIZES ({pct:.0f}% of strategies improved)")
    elif pct >= 20:
        print(f"\n  ⚠️  PARTIALLY GENERALIZES ({pct:.0f}% of strategies improved)")
    else:
        print(f"\n  ❌ METHOD LIMITED ({pct:.0f}% of strategies improved)")

    # Save
    out = Path("research_lab/logs/sdf_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "SDF — logistic regression meta-filter, 70/30 time split",
        "n_files_analyzed": len(results),
        "n_files_improved": len(improvements),
        "n_strategies": n_strategies,
        "n_strategies_improved": n_gen,
        "improvements": improvements,
        "all_results": results,
    }, indent=2))
    print(f"\n[SAVE] {out}")


if __name__ == "__main__":
    main()
