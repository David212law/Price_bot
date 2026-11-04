"""D-528: Multi-Layer Portfolio — combine novel strategies with M31.

Pipeline (fully automatic):
  1. Load deduped representatives (90 candidates from D-527)
  2. Filter by cross-corr (|corr|<0.5 with BOTH M31 and Keltner) → truly novel
  3. Pick top per thesis group (one per thesis, max 4)
  4. Build risk-parity portfolio (M31 + Keltner + picks)
  5. Validate on 30% holdout vs M31-only

Verdict:
  PASS     : portfolio SR ≥ M31 SR × 1.20, coverage ≥ 50%
  MARGINAL : improvement 10-20%
  FAIL     : portfolio ≤ M31
"""
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


def sharpe(vals):
    if len(vals) < 10: return 0.0
    m = sum(vals) / len(vals)
    v = sum((x - m) ** 2 for x in vals) / len(vals)
    sd = v ** 0.5
    return (m / sd) * (365 ** 0.5) if sd > 0 else 0.0


def corr_on_union(a, b, min_days=30):
    dates = sorted(set(a.keys()) & set(b.keys()))
    if len(dates) < min_days: return 0.0
    va = [a[d] for d in dates]; vb = [b[d] for d in dates]
    ma = sum(va) / len(va); mb = sum(vb) / len(vb)
    cov = sum((va[i] - ma) * (vb[i] - mb) for i in range(len(va)))
    sa = sum((x - ma) ** 2 for x in va) ** 0.5
    sb = sum((x - mb) ** 2 for x in vb) ** 0.5
    return round(cov / (sa * sb), 3) if sa * sb > 0 else 0.0


def load_returns_file(exchange, strategy, hash_val, symbol):
    p = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}/{strategy}_{hash_val}_{symbol}.json")
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except: return {}


def load_m31_returns():
    from research_lab.composer import portfolio_daily_returns, apply_m31_fees
    raw = dict(portfolio_daily_returns("hyperliquid", ["BTC","ETH","SOL","BNB","XRP","AVAX"]))
    return apply_m31_fees(raw)


def load_keltner_returns():
    for exch, strat, hash_val, sym in [
        ("aster", "KELTNER_REV", "16598fcc", "AVAXUSDT"),
        ("hyperliquid", "KELTNER_REV", "16598fcc", "AVAX"),
        ("aster", "KELTNER_REV", "80e7c85f", "AVAXUSDT"),
    ]:
        rets = load_returns_file(exch, strat, hash_val, sym)
        if rets and len(rets) >= 100:
            return rets
    return {}


def filter_novel(deduped, m31, keltner, threshold=0.5):
    novel = []
    for thesis, items in deduped.items():
        for item in items:
            rets = load_returns_file(item["exchange"], item["strategy"], item["hash"], item["symbol"])
            if not rets or len(rets) < 100: continue
            c_m31 = corr_on_union(rets, m31)
            c_kelt = corr_on_union(rets, keltner) if keltner else 0
            if abs(c_m31) < threshold and abs(c_kelt) < threshold:
                novel.append({
                    **item,
                    "thesis": thesis,
                    "corr_m31": c_m31,
                    "corr_keltner": c_kelt,
                    "_rets": rets,
                })
    return novel


def pick_per_thesis(novel, top_n=4):
    novel_sorted = sorted(novel, key=lambda x: -x["baseline_sr"])
    picked = []
    seen = set()
    for c in novel_sorted:
        if c["thesis"] in seen: continue
        seen.add(c["thesis"])
        picked.append(c)
        if len(picked) >= top_n: break
    return picked


def align_union(components):
    all_dates = set()
    for r in components:
        all_dates |= set(r.keys())
    all_dates = sorted(all_dates)
    padded = [{d: r.get(d, 0.0) for d in all_dates} for r in components]
    return all_dates, padded


def compute_risk_parity_weights(padded):
    stds = []
    for r in padded:
        vals = list(r.values())
        if not vals: stds.append(1.0); continue
        m = sum(vals) / len(vals)
        var = sum((v - m) ** 2 for v in vals) / len(vals)
        stds.append(var ** 0.5 if var > 0 else 1.0)
    inv = [1 / s if s > 0 else 0 for s in stds]
    total = sum(inv)
    return [iv / total for iv in inv] if total > 0 else [1/len(padded)] * len(padded)


def build_portfolio(m31, keltner, picks):
    components = [m31, keltner] + [p["_rets"] for p in picks]
    names = ["M31", "Keltner"] + [f"{p['strategy']}_{p['symbol']}" for p in picks]
    dates, padded = align_union(components)
    weights = compute_risk_parity_weights(padded)
    combined = {}
    for d in dates:
        combined[d] = sum(w * r[d] for w, r in zip(weights, padded))
    return {
        "names": names,
        "weights": weights,
        "returns": combined,
        "dates": dates,
        "components": components,
    }


def validate_70_30(port_rets, m31_rets, holdout=0.30):
    dates = sorted(port_rets.keys())
    n = len(dates)
    split = int(n * (1 - holdout))
    test_dates = dates[split:]
    if len(test_dates) < 60:
        return None
    port_vals = [port_rets[d] for d in test_dates]
    m31_vals = [m31_rets.get(d, 0.0) for d in test_dates]
    port_sr = sharpe(port_vals)
    m31_sr = sharpe(m31_vals)
    improvement = (port_sr / m31_sr - 1) * 100 if m31_sr > 0 else 0
    active = sum(1 for v in port_vals if abs(v) > 1e-9)
    coverage = active / len(test_dates)
    return {
        "n_test": len(test_dates),
        "port_sr": round(port_sr, 2),
        "m31_sr": round(m31_sr, 2),
        "improvement_pct": round(improvement, 1),
        "coverage": round(coverage, 2),
    }


def main():
    print("=" * 78)
    print(" Multi-Layer Portfolio — D-528")
    print("=" * 78)

    print("\n[PREP] Loading M31, Keltner, deduped representatives...")
    m31 = load_m31_returns()
    keltner = load_keltner_returns()
    print(f"  M31: {len(m31)} days")
    print(f"  Keltner: {len(keltner)} days")

    deduped_path = Path("research_lab/logs/thesis_deduped.json")
    if not deduped_path.exists():
        print(f"❌ {deduped_path} not found — run thesis_dedup first")
        return
    deduped = json.loads(deduped_path.read_text())["by_thesis"]
    total_reps = sum(len(v) for v in deduped.values())
    print(f"  Deduped representatives: {total_reps}")

    print("\n[STAGE 1] Filter for novelty (|corr| < 0.5 with BOTH M31 and Keltner)...")
    novel = filter_novel(deduped, m31, keltner, threshold=0.5)
    print(f"  Novel candidates: {len(novel)}/{total_reps}")
    by_thesis = defaultdict(list)
    for c in novel:
        by_thesis[c["thesis"]].append(c)
    for t, items in sorted(by_thesis.items(), key=lambda x: -len(x[1])):
        print(f"    {t}: {len(items)}")

    if len(novel) < 3:
        print("\n⚠️  <3 novel candidates. Cannot build portfolio.")
        return

    print("\n[STAGE 2] Pick one per thesis (top SR)...")
    picks = pick_per_thesis(novel, top_n=4)
    print(f"  Picked {len(picks)}:")
    for p in picks:
        print(f"    {p['strategy']:25s} {p['symbol']:10s} {p['exchange']:10s} "
              f"SR={p['baseline_sr']:5.2f} "
              f"corrM31={p['corr_m31']:+.2f} corrKelt={p['corr_keltner']:+.2f} "
              f"[{p['thesis']}]")

    print("\n[STAGE 3] Build risk-parity portfolio...")
    port = build_portfolio(m31, keltner, picks)
    print(f"  Components: {len(port['names'])}")
    for name, w in zip(port["names"], port["weights"]):
        print(f"    {name:35s}: {w*100:5.2f}%")

    print("\n[STAGE 4] Validate on 30% holdout vs M31-only...")
    result = validate_70_30(port["returns"], m31)
    if not result:
        print("  ⚠️  Not enough test data")
        return
    print(f"  Test window:   {result['n_test']} days")
    print(f"  Portfolio SR:  {result['port_sr']}")
    print(f"  M31-only SR:   {result['m31_sr']}")
    print(f"  Improvement:   {result['improvement_pct']:+.1f}%")
    print(f"  Coverage:      {result['coverage']:.0%}")

    print("\n" + "=" * 78)
    print(" VERDICT")
    print("=" * 78)
    if result["improvement_pct"] >= 20 and result["coverage"] >= 0.5:
        print(f" ✅ PASS: portfolio({result['port_sr']}) beats M31({result['m31_sr']}) "
              f"by {result['improvement_pct']:+.0f}%")
        verdict = "PASS"
    elif result["improvement_pct"] >= 10 and result["coverage"] >= 0.5:
        print(f" ⚠️  MARGINAL: +{result['improvement_pct']:.0f}% — might not survive Live")
        verdict = "MARGINAL"
    else:
        print(f" ❌ FAIL: portfolio({result['port_sr']}) ≤ M31({result['m31_sr']})")
        verdict = "FAIL"

    out = Path("research_lab/logs/multi_layer_portfolio.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "picks": [{k: v for k, v in p.items() if not k.startswith("_")} for p in picks],
        "weights": {name: round(w, 4) for name, w in zip(port["names"], port["weights"])},
        "validation": result,
    }, indent=2))
    print(f"\n[SAVE] {out}")


if __name__ == "__main__":
    main()
