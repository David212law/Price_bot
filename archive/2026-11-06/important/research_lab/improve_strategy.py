"""D-530: Strategy Improver — auto-improvement via fixed filters.

Runs on Stage 1 survivors (filter_candidates output).
For each survivor, tries 6 fixed filters (no ML, no learning):
  1. momentum_20d  — trade only when past 20d mean > 0
  2. vol_low       — trade only in calm market (BTC |ret| < 1.5x median)
  3. vol_high      — trade only in volatile market
  4. regime_TREND  — trade only in TREND regime
  5. regime_RANGE  — trade only in RANGE regime
  6. regime_NEUTRAL— trade only in NEUTRAL regime

Validation (fee-aware, 70/30 time split):
  - Train improvement >= 15%
  - Test improvement >= 10%
  - Test coverage >= 30%

Output:
  - improvements.json (all proposals with metrics)
  - pending_approvals.json (PASS/MARGINAL only)
  - Bale notification

This file does NOT touch Paper. Research-only.
"""
import json
import math
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import requests

BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

THRESHOLDS = {
    "fee_per_transition": 0.001,   # 0.1% roundtrip
    "train_split": 0.70,
    "min_train_improvement": 15.0,
    "min_test_improvement": 10.0,
    "min_test_coverage": 0.30,
    "min_baseline_sr": 1.0,
    "require_quartile_4of4": True,  # D-530: filter must preserve stability
    "min_data_days": 60,
    "min_test_days": 30,
}


def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT:
        print(f"[BALE-SKIP] {msg[:80]}")
        return
    try:
        requests.post(f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage",
                      json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except Exception as e:
        print(f"[BALE-ERR] {e}")


def sharpe_annual(values):
    if len(values) < 10: return 0.0
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / len(values)
    sd = v ** 0.5
    return (m / sd) * (365 ** 0.5) if sd > 0 else 0.0


def sharpe_with_fee(rets_dict, fee_per_transition=0.001):
    """Returns (sharpe, coverage, n_active, transitions)."""
    if not rets_dict: return 0.0, 0.0, 0, 0
    dates = sorted(rets_dict.keys())
    vals = [rets_dict[d] for d in dates]
    n_active = sum(1 for v in vals if abs(v) > 1e-9)
    trans = sum(1 for i in range(1, len(vals)) if (vals[i] > 0) != (vals[i-1] > 0))
    fee_total = trans * fee_per_transition
    fee_per_day = fee_total / len(vals) if vals else 0
    adjusted = [v - fee_per_day for v in vals]
    return (
        round(sharpe_annual(adjusted), 2),
        round(n_active / len(vals), 2) if vals else 0.0,
        n_active,
        trans,
    )


def load_btc_daily(exchange="hyperliquid", symbol="BTC"):
    from strategies.core_engine import load_data
    btc = load_data(exchange, symbol)
    if not btc: return {}
    prices = defaultdict(list)
    for c in btc:
        if not isinstance(c, dict): continue
        t, close = c.get("t"), c.get("c")
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


# ═══════════════════════════════════════════════════════════════
# Filters
# ═══════════════════════════════════════════════════════════════
def filter_momentum(returns, lookback=20):
    dates = sorted(returns.keys())
    out = {}
    for i, d in enumerate(dates):
        past = [returns[dates[j]] for j in range(max(0, i - lookback), i)]
        if not past or sum(past) / len(past) > 0:
            out[d] = returns[d]
        else:
            out[d] = 0.0
    return out


def filter_vol(returns, btc_daily, keep_low=True):
    if not btc_daily: return dict(returns)
    abs_btc = sorted(abs(v) for v in btc_daily.values())
    median_abs = abs_btc[len(abs_btc) // 2] if abs_btc else 0
    threshold = median_abs * 1.5
    out = {}
    for d, r in returns.items():
        is_high = abs(btc_daily.get(d, 0)) > threshold
        keep = (not is_high) if keep_low else is_high
        out[d] = r if keep else 0.0
    return out


def filter_regime(returns, regime_map, keep_regime):
    return {d: (r if regime_map.get(d) == keep_regime else 0.0)
            for d, r in returns.items()}


# ═══════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════
def check_quartile_4of4(filtered_rets, min_pf=1.0):
    """Quartile 4/4 check on filtered returns. PF>min_pf in each quartile."""
    dates = sorted(filtered_rets.keys())
    n = len(dates)
    if n < 20:
        return False, []
    chunks = [dates[i * n // 4:(i + 1) * n // 4] for i in range(4)]
    pfs = []
    for chunk in chunks:
        if not chunk:
            pfs.append(0.0); continue
        vals = [filtered_rets[d] for d in chunk]
        wins = sum(v for v in vals if v > 0)
        losses = abs(sum(v for v in vals if v < 0))
        pf = wins / losses if losses > 0 else (999 if wins > 0 else 1.0)
        pfs.append(round(pf, 3))
    pass_count = sum(1 for pf in pfs if pf > min_pf)
    return pass_count == 4, pfs


def validate(returns, filtered):
    dates = sorted(returns.keys())
    n = len(dates)
    if n < THRESHOLDS["min_data_days"]:
        return None
    split = int(n * THRESHOLDS["train_split"])
    train = dates[:split]
    test = dates[split:]
    if len(test) < THRESHOLDS["min_test_days"]:
        return None

    train_base = {d: returns[d] for d in train}
    train_filt = {d: filtered.get(d, 0.0) for d in train}
    test_base = {d: returns[d] for d in test}
    test_filt = {d: filtered.get(d, 0.0) for d in test}

    base_sr_tr, _, _, _ = sharpe_with_fee(train_base)
    filt_sr_tr, _, _, _ = sharpe_with_fee(train_filt)
    base_sr_te, _, _, _ = sharpe_with_fee(test_base)
    filt_sr_te, cov_te, _, _ = sharpe_with_fee(test_filt)

    if base_sr_tr <= 0 or base_sr_te <= 0:
        return None

    imp_tr = (filt_sr_tr / base_sr_tr - 1) * 100
    imp_te = (filt_sr_te / base_sr_te - 1) * 100

    if imp_tr < THRESHOLDS["min_train_improvement"]: return None
    if imp_te < THRESHOLDS["min_test_improvement"]: return None
    if cov_te < THRESHOLDS["min_test_coverage"]: return None

    # D-530: quartile 4/4 on filtered (defense against filter breaking stability)
    q_ok, q_pfs = check_quartile_4of4(filtered)
    if not q_ok:
        return None  # filter broke quartile stability → reject

    return {
        "train_improvement_pct": round(imp_tr, 1),
        "test_improvement_pct": round(imp_te, 1),
        "test_coverage": cov_te,
        "baseline_train_sr": base_sr_tr,
        "baseline_test_sr": base_sr_te,
        "filtered_train_sr": filt_sr_tr,
        "filtered_test_sr": filt_sr_te,
        "quartile_pf": q_pfs,
    }


# ═══════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════
def main():
    print("="*78)
    print(" STRATEGY IMPROVER — D-530")
    print("="*78)
    print(f"Thresholds: train>={THRESHOLDS['min_train_improvement']}%, "
          f"test>={THRESHOLDS['min_test_improvement']}%, "
          f"coverage>={THRESHOLDS['min_test_coverage']}%")
    print()

    from research_lab.composer import load_state, filter_candidates, regime_by_date
    state = load_state()
    btc_daily = load_btc_daily()
    regime_map = regime_by_date("hyperliquid")
    print(f"[PREP] BTC={len(btc_daily)}d, regime={len(regime_map)}d\n")

    improvements = []
    near_misses = []  # improvement 5-15%, for learning
    seen = set()

    for exchange in ["hyperliquid", "aster", "kucoin"]:
        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            cands = filter_candidates(state, regime, exchange)
            for c in cands:
                key = (c["strategy"], c["hash"], c["symbol"], exchange)
                if key in seen: continue
                seen.add(key)

                returns = load_returns_file(exchange, c["strategy"], c["hash"], c["symbol"])
                if len(returns) < THRESHOLDS["min_data_days"]: continue

                # Baseline must be meaningful
                base_sr, _, _, _ = sharpe_with_fee(returns)
                if base_sr < THRESHOLDS["min_baseline_sr"]: continue

                filters = [
                    ("momentum_20d", filter_momentum(returns, 20)),
                    ("vol_low", filter_vol(returns, btc_daily, keep_low=True)),
                    ("vol_high", filter_vol(returns, btc_daily, keep_low=False)),
                    ("regime_TREND", filter_regime(returns, regime_map, "TREND")),
                    ("regime_RANGE", filter_regime(returns, regime_map, "RANGE")),
                    ("regime_NEUTRAL", filter_regime(returns, regime_map, "NEUTRAL")),
                ]

                best = None
                for fname, filtered in filters:
                    result = validate(returns, filtered)
                    if result and (best is None or
                                    result["test_improvement_pct"] > best["test_improvement_pct"]):
                        best = {"filter": fname, **result}

                if best:
                    improvements.append({
                        "strategy": c["strategy"],
                        "exchange": exchange,
                        "symbol": c["symbol"],
                        "hash": c["hash"],
                        "baseline_sr": base_sr,
                        **best,
                    })
                    print(f"  ✅ {c['strategy'][:25]:25s} {c['symbol']:10s} "
                          f"+{best['filter']:15s} "
                          f"train={best['train_improvement_pct']:+.0f}% "
                          f"test={best['test_improvement_pct']:+.0f}% "
                          f"cov={best['test_coverage']:.0%}")
                else:
                    # Record near-misses for transparency (best test improvement < 10%)
                    best_near = None
                    for fname, filtered in filters:
                        # Try with looser thresholds for recording
                        dates = sorted(returns.keys())
                        n = len(dates)
                        if n < THRESHOLDS["min_data_days"]: continue
                        split = int(n * THRESHOLDS["train_split"])
                        if len(dates[split:]) < THRESHOLDS["min_test_days"]: continue
                        tr = {d: returns[d] for d in dates[:split]}
                        te = {d: returns[d] for d in dates[split:]}
                        tr_f = {d: filtered.get(d, 0) for d in dates[:split]}
                        te_f = {d: filtered.get(d, 0) for d in dates[split:]}
                        b_tr, _, _, _ = sharpe_with_fee(tr)
                        f_tr, _, _, _ = sharpe_with_fee(tr_f)
                        b_te, _, _, _ = sharpe_with_fee(te)
                        f_te, cov_te, _, _ = sharpe_with_fee(te_f)
                        if b_tr <= 0 or b_te <= 0: continue
                        imp_te = (f_te / b_te - 1) * 100
                        if imp_te >= 5 and (best_near is None or imp_te > best_near["test_improvement_pct"]):
                            best_near = {
                                "strategy": c["strategy"], "symbol": c["symbol"],
                                "exchange": exchange, "filter": fname,
                                "test_improvement_pct": round(imp_te, 1),
                                "test_coverage": cov_te,
                            }
                    if best_near:
                        near_misses.append(best_near)

    print(f"\n{'='*78}")
    print()
    print("  ⚠️  KNOWN LIMITATION (D-538):")
    print("      Improvements are measured vs each strategy's OWN baseline,")
    print("      NOT vs M31. A filter may improve Keltner while raising corr")
    print("      with M31. Treat all results as CANDIDATES, not confirmed.")
    print()
    print(f" RESULTS")
    print(f"{'='*78}")
    print(f"  Strategies analyzed: {len(seen)}")
    print(f"  Passed all thresholds: {len(improvements)}")
    print(f"  Near-misses (5-15%): {len(near_misses)}")

    # Save
    out = Path("research_lab/logs/improvements.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": THRESHOLDS,
        "n_analyzed": len(seen),
        "improvements": improvements,
        "near_misses": near_misses,
    }, indent=2))
    print(f"\n[SAVE] {out}")

    # Append to pending_approvals
    if improvements:
        pending_path = Path("exchanges/pending_approvals.json")
        pending = {}
        if pending_path.exists():
            try: pending = json.loads(pending_path.read_text())
            except: pending = {}
        for imp in improvements:
            key = f"improved_{imp['strategy']}_{imp['symbol']}_{imp['filter']}"
            pending[key] = {
                "type": "strategy_improvement",
                "verdict": "PASS",
                "original_sr": imp["baseline_sr"],
                "improvement": imp,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
        pending_path.write_text(json.dumps(pending, indent=2))
        print(f"  [PENDING] Added {len(improvements)} improvements")

        # Bale notification
        if BALE_TOKEN and BALE_CHAT:
            msg = f"🔧 Strategy Improver — {len(improvements)} improvement(s)\n"
            for imp in improvements[:5]:
                msg += (f"  {imp['strategy']}_{imp['symbol']} "
                        f"+{imp['filter']} → test {imp['test_improvement_pct']:+.0f}%\n")
            send_bale(msg)

    print(f"\n{'='*78}")
    if improvements:
        print(f" ✅ {len(improvements)} strategy improvement(s) ready for review")
    else:
        print(f" ⚠️  0 improvements passed thresholds. Methods verified, data limited.")
        print(f"     ({len(near_misses)} near-misses at 5-15%)")
    print(f"{'='*78}")


if __name__ == "__main__":
    main()
