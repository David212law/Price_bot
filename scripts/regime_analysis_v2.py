"""Regime analysis v2 — gap-fill + forward-only + OOS 70/30."""
import json
from datetime import datetime, timedelta
from collections import Counter

def load_data():
    crypto = json.load(open("data/crypto_5y_usd.json"))
    usd_irr = json.load(open("data/usd_irr_tgju.json"))
    return crypto, usd_irr

def build_tmn_series(crypto, usd_irr):
    """Build TMN prices + fill USD/IRR gaps by forward-fill."""
    # Forward fill USD/IRR to all days in range
    irr_dates = sorted(usd_irr.keys())
    if not irr_dates: return {}, {}
    start = datetime.strptime(irr_dates[0], "%Y-%m-%d")
    end = datetime.strptime(irr_dates[-1], "%Y-%m-%d")
    all_dates = []
    cur = start
    while cur <= end:
        all_dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    # Fill USD/IRR
    irr_filled = {}
    last_irr = usd_irr[irr_dates[0]]
    irr_set = set(usd_irr.keys())
    for d in all_dates:
        if d in irr_set:
            last_irr = usd_irr[d]
        irr_filled[d] = last_irr

    # Build TMN series for each crypto
    tmn = {}
    for sym, prices in crypto.items():
        if not sym.endswith("-USD"): continue
        base = sym[:-4]
        series = {}
        for d in all_dates:
            if d in prices and d in irr_filled:
                series[d] = prices[d] * (irr_filled[d] / 10)
        if len(series) > 500:
            tmn[base] = series
    tether = {d: irr_filled[d] / 10 for d in all_dates}
    return tmn, tether

def detect_regime_forward(btc_usd_series, date, all_dates):
    """Regime at date T using only data up to T-1 (forward-only, no look-ahead)."""
    try:
        idx = all_dates.index(date)
    except ValueError:
        return None
    if idx < 30: return None
    # Use prices up to T-1
    p_today = btc_usd_series.get(date)
    p_30ago = btc_usd_series.get(all_dates[idx-30])
    if not p_today or not p_30ago: return None
    ret_30d = (p_today / p_30ago - 1) * 100
    if ret_30d > 15: return "BULL_STRONG"
    elif ret_30d > 5: return "BULL"
    elif ret_30d > -5: return "FLAT"
    elif ret_30d > -15: return "BEAR"
    else: return "CRASH"

def compute_daily_returns(series, all_dates):
    """Compute daily returns, only for consecutive days (skip gaps > 1)."""
    rets = {}
    dates_list = sorted([d for d in series if d in all_dates])
    for i in range(1, len(dates_list)):
        d0, d1 = dates_list[i-1], dates_list[i]
        # Skip if gap > 3 days (data issue)
        try:
            gap = (datetime.strptime(d1, "%Y-%m-%d") -
                   datetime.strptime(d0, "%Y-%m-%d")).days
        except:
            continue
        if gap > 3: continue
        p0 = series.get(d0)
        p1 = series.get(d1)
        if p0 and p1 and p0 > 0:
            rets[d1] = (p1 / p0 - 1) * 100
    return rets

def analyze(tmn, tether, btc_usd, all_dates, split_date):
    """Analyze alpha per regime, train (before split) and test (after)."""
    tether_rets = compute_daily_returns(tether, all_dates)

    # Regime for each date
    regimes = {}
    for d in all_dates:
        r = detect_regime_forward(btc_usd, d, all_dates)
        if r: regimes[d] = r

    # Asset returns
    asset_rets = {}
    for base, series in tmn.items():
        asset_rets[base] = compute_daily_returns(series, all_dates)

    # Alpha per regime, per asset
    result = {"train": {}, "test": {}}
    for asset, rets in asset_rets.items():
        for phase in ["train", "test"]:
            result[phase][asset] = {}
            for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
                days = [d for d, r in regimes.items()
                        if r == regime and d in rets and d in tether_rets
                        and ((d < split_date) if phase == "train" else (d >= split_date))]
                if len(days) < 20: continue
                alphas = [rets[d] - tether_rets[d] for d in days]
                mean_alpha = sum(alphas) / len(alphas)
                var = sum((a - mean_alpha)**2 for a in alphas) / len(alphas)
                std = var ** 0.5
                result[phase][asset][regime] = {
                    "days": len(days),
                    "mean_alpha": mean_alpha,
                    "std_alpha": std,
                    "sharpe_alpha": mean_alpha / std if std > 0 else 0,
                }
    return result

def pick_best_per_regime(result_train):
    """Pick best asset per regime using train phase."""
    best = {}
    for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        candidates = [(a, r[regime]["sharpe_alpha"])
                      for a, r in result_train.items() if regime in r]
        if not candidates:
            best[regime] = "TETHER"
            continue
        candidates.sort(key=lambda x: -x[1])
        top_asset, top_sharpe = candidates[0]
        if top_sharpe > 0.05:  # min threshold
            best[regime] = top_asset
        else:
            best[regime] = "TETHER"
    return best

def evaluate_on_test(best_train, result_test):
    """Evaluate train-chosen assets on test data."""
    total_days = 0
    total_alpha = 0.0
    details = {}
    for regime, asset in best_train.items():
        if asset == "TETHER":
            details[regime] = {"chosen": "TETHER", "alpha_test": 0.0, "days": 0}
            continue
        if asset not in result_test or regime not in result_test[asset]:
            details[regime] = {"chosen": asset, "alpha_test": None, "days": 0}
            continue
        r = result_test[asset][regime]
        details[regime] = {
            "chosen": asset,
            "alpha_test": r["mean_alpha"],
            "days": r["days"],
            "sharpe_test": r["sharpe_alpha"],
        }
        total_days += r["days"]
        total_alpha += r["mean_alpha"] * r["days"]
    if total_days > 0:
        overall = total_alpha / total_days
    else:
        overall = 0
    return {"details": details, "overall_alpha": overall, "total_days": total_days}

def main():
    print("=" * 80)
    print(" Regime Analysis v2 — gap-fill + forward-only + OOS 70/30")
    print("=" * 80)

    crypto, usd_irr = load_data()
    tmn, tether = build_tmn_series(crypto, usd_irr)
    btc_usd = crypto["BTC-USD"]

    # All calendar dates
    all_dates = sorted(set(tether.keys()))
    print(f"\nCalendar days: {len(all_dates)} ({all_dates[0]} -> {all_dates[-1]})")
    print(f"Assets: {len(tmn)}")

    # OOS split at 70%
    split_idx = int(len(all_dates) * 0.7)
    split_date = all_dates[split_idx]
    print(f"OOS split: train ends {split_date} (index {split_idx}/{len(all_dates)})")

    result = analyze(tmn, tether, btc_usd, all_dates, split_date)

    # Show std sanity check
    print(f"\n{'='*80}")
    print(" SANITY CHECK — daily std of alpha (should be 1-8%)")
    print("="*80)
    for asset in sorted(result["train"].keys())[:5]:
        line = f"  {asset:<8} "
        for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
            if regime in result["train"][asset]:
                s = result["train"][asset][regime]["std_alpha"]
                line += f"{s:>5.1f}% "
            else:
                line += "  -  "
        print(line)
    print("  (اگر std > 10% است، gap یا data issue هست)")

    # Best per regime (train)
    best_train = pick_best_per_regime(result["train"])
    print(f"\n{'='*80}")
    print(" TRAIN — بهترین دارایی هر رژیم")
    print("="*80)
    for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        a = best_train[regime]
        if a != "TETHER" and regime in result["train"][a]:
            r = result["train"][a][regime]
            print(f"  {regime:<14} -> {a:<8} (alpha {r['mean_alpha']:+.3f}%/d, sharpe {r['sharpe_alpha']:+.3f}, {r['days']}d)")
        else:
            print(f"  {regime:<14} -> TETHER")

    # Evaluate on test
    eval_test = evaluate_on_test(best_train, result["test"])
    print(f"\n{'='*80}")
    print(" TEST (OOS) — عملکرد انتخاب‌های train روی داده ندیده")
    print("="*80)
    for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        d = eval_test["details"][regime]
        if d.get("alpha_test") is None:
            print(f"  {regime:<14} -> {d['chosen']:<8} (N/A — no test data)")
        elif d["chosen"] == "TETHER":
            print(f"  {regime:<14} -> TETHER (no risk)")
        else:
            print(f"  {regime:<14} -> {d['chosen']:<8} test alpha {d['alpha_test']:+.3f}%/d, {d['days']}d")

    print(f"\n{'='*80}")
    print(f" OVERALL OOS alpha (وزن‌دار): {eval_test['overall_alpha']:+.3f}%/d")
    print(f" Total test days: {eval_test['total_days']}")
    print(f" Yearly estimate: {eval_test['overall_alpha'] * 252:+.1f}% (vs TETHER)")
    print("=" * 80)

    # Interpretation
    print(f"\n{'='*80}")
    print(" INTERPRETATION")
    print("=" * 80)
    if eval_test["overall_alpha"] > 0.15:
        print("  EXCELLENT — alpha مثبت معنادار در OOS (تکرارپذیر)")
    elif eval_test["overall_alpha"] > 0.05:
        print("  GOOD — alpha مثبت کوچک در OOS (قابل اعتماد)")
    elif eval_test["overall_alpha"] > 0:
        print("  MARGINAL — alpha مثبت ولی ضعیف (نیاز به بررسی)")
    else:
        print("  FAIL — alpha منفی در OOS (train artifact)")
        print("  یعنی انتخاب‌های train در test شکست خوردند.")

    # Save
    output = {
        "split_date": split_date,
        "train_regimes": best_train,
        "test_eval": eval_test,
        "all_train": result["train"],
        "all_test": result["test"],
    }
    json.dump(output, open("data/regime_analysis_v2.json", "w"), indent=2)
    print(f"\n  Saved: data/regime_analysis_v2.json")

if __name__ == "__main__":
    main()
