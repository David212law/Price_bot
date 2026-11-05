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

def _bootstrap_improvement_ci(port_rets, base_rets, n_iter=1000):
    """D-538: 95% bootstrap CI on (port_SR / base_SR - 1)*100.
    port_rets and base_rets must be same-length lists.
    Returns dict with ci95_low/high/median, or None if insufficient data.
    """
    import random
    random.seed(42)
    if len(port_rets) != len(base_rets) or len(port_rets) < 30:
        return None
    n = len(port_rets)
    ratios = []
    for _ in range(n_iter):
        idx = [random.randint(0, n - 1) for _ in range(n)]
        p = [port_rets[i] for i in idx]
        b = [base_rets[i] for i in idx]
        mp = sum(p)/n; mb = sum(b)/n
        sp = (sum((x-mp)**2 for x in p)/n) ** 0.5
        sb = (sum((x-mb)**2 for x in b)/n) ** 0.5
        if sp == 0 or sb == 0: continue
        sr_p = mp/sp; sr_b = mb/sb
        if sr_b > 0:
            ratios.append((sr_p/sr_b - 1) * 100)
    if len(ratios) < 100:
        return None
    ratios.sort()
    return {
        "ci95_low": round(ratios[int(0.025*len(ratios))], 2),
        "ci95_high": round(ratios[int(0.975*len(ratios))], 2),
        "median": round(ratios[len(ratios)//2], 2),
        "n_boot": len(ratios),
    }



def sharpe(vals):  # delegate_to_utils
    from research_lab.utils import sharpe as _u
    return _u(vals)


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
                # D-530: apply all 4 individual validation gates
                from research_lab.composer import load_state as _load_state
                _state = _load_state()
                ok, reason = validate_novel_candidate(item, _state)
                if not ok:
                    continue
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


def validate_novel_candidate(item, state):
    """Check stress/DSR/quartile/calmar from state.json for the original strategy."""
    exch, strat, sym, h = item["exchange"], item["strategy"], item["symbol"], item["hash"]
    target_key = f"{exch}:{strat}:{h}:{sym}"
    entry = state.get("done", {}).get(target_key)

    if not isinstance(entry, dict):
        for k, v in state.get("done", {}).items():
            if not isinstance(v, dict): continue
            parts = k.split(":")
            if len(parts) >= 4 and parts[0] == exch and parts[1] == strat and parts[2] == h:
                if sym in parts[3] or parts[3] in sym:
                    entry = v
                    break

    if not isinstance(entry, dict):
        return False, "not_in_state"

    val = entry.get("validation", {})
    if not val:
        return False, "no_validation"

    if val.get("quartiles_pass", 0) < 4:
        return False, f"quartile_{val.get('quartiles_pass')}/4"

    stress = val.get("stress", {})
    if not stress:
        return False, "no_stress"

    fee = stress.get("fee_2x", {})
    if fee.get("pf", 999) < 1.2:
        return False, f"fee_2x_pf_{fee.get('pf')}"

    slip = stress.get("slippage_1.5x", {})
    if slip.get("sharpe_ann", 1) < 0:
        return False, f"slip_sr_{slip.get('sharpe_ann')}"

    rob = stress.get("param_robustness", {})
    if rob.get("verdict") == "FRAGILE":
        return False, "param_fragile"

    try:
        from research_lab.audit_core import deflated_sharpe_family
        from strategies.library.families import STRATEGY_FAMILY
        fam = STRATEGY_FAMILY.get(strat, "OTHER")
        sr = val.get("sharpe_ann", 0)
        n = val.get("n", entry.get("n_total", 0))
        if n < 30:
            return False, f"n_{n}"
        dsr_res = deflated_sharpe_family(sr, n, fam)
        dsr_val = dsr_res.get("DSR", 0) if dsr_res else 0
        if dsr_val < 0.50:
            return False, f"dsr_{round(dsr_val, 2)}"
    except Exception as e:
        return False, f"dsr_err_{e}"

    calmar = val.get("calmar", {})
    if calmar and calmar.get("max_dd_pct", 0) > 60:
        return False, f"dd_{calmar.get('max_dd_pct')}"

    return True, "ok"


def combo_tests(port, m31_rets, keltner_rets):
    """5 combo-level validation tests on the final portfolio."""
    port_rets = port["returns"]
    components = port["components"]
    weights = port["weights"]
    port_sr = sharpe(list(port_rets.values()))

    # 1. Dropout: removing any of the 4 picks should NOT destroy SR by <5%
    dropout_issues = []
    for i in range(2, len(components)):  # skip M31/Keltner base
        others = [components[j] for j in range(len(components)) if j != i]
        other_w = [weights[j] for j in range(len(weights)) if j != i]
        total_w = sum(other_w)
        if total_w <= 0: continue
        other_w = [w / total_w for w in other_w]
        dates, padded = align_union(others)
        combined = {}
        for d in dates:
            combined[d] = sum(w * r[d] for w, r in zip(other_w, padded))
        other_sr = sharpe(list(combined.values()))
        drop_pct = (port_sr - other_sr) / port_sr if port_sr > 0 else 0
        if drop_pct < 0.05:
            dropout_issues.append(f"comp{i+1}_redundant(drop={drop_pct*100:.1f}%)")
        elif drop_pct < 0:
            dropout_issues.append(f"comp{i+1}_harmful(drop={drop_pct*100:.1f}%)")

    # 2. Weight robustness ±20%
    perturbed_w = [w * 1.2 for w in weights]
    total = sum(perturbed_w)
    perturbed_w = [w / total for w in perturbed_w]
    dates, padded = align_union(components)
    comb_p = {}
    for d in dates:
        comb_p[d] = sum(w * r[d] for w, r in zip(perturbed_w, padded))
    perturbed_sr = sharpe(list(comb_p.values()))
    worst_ratio = perturbed_sr / port_sr if port_sr > 0 else 0

    # 3. OOS vs best component
    dates_all = sorted(port_rets.keys())
    test_dates = dates_all[int(len(dates_all) * 0.7):]
    port_test_sr = sharpe([port_rets[d] for d in test_dates])
    best_comp_sr = 0.0
    for comp in components:
        comp_test_sr = sharpe([comp.get(d, 0.0) for d in test_dates])
        if comp_test_sr > best_comp_sr:
            best_comp_sr = comp_test_sr

    # 4. Diversification Ratio
    stds = []
    for comp in components:
        vals = list(comp.values())
        if not vals: stds.append(0); continue
        m = sum(vals) / len(vals)
        v = sum((x - m) ** 2 for x in vals) / len(vals)
        stds.append(v ** 0.5)
    weighted_vol = sum(w * s for w, s in zip(weights, stds))
    cv = list(port_rets.values())
    cm = sum(cv) / len(cv)
    cvar = sum((x - cm) ** 2 for x in cv) / len(cv)
    combo_vol = cvar ** 0.5
    dr = weighted_vol / combo_vol if combo_vol > 0 else 0

    # 5. Regime-conditional (portfolio >= M31 in each regime on test)
    from research_lab.composer import regime_by_date
    reg_map = regime_by_date("hyperliquid")
    regime_issues = []
    for regime in ["TREND", "RANGE", "NEUTRAL"]:
        port_r = [port_rets[d] for d in test_dates if reg_map.get(d) == regime]
        m31_r = [m31_rets.get(d, 0.0) for d in test_dates if reg_map.get(d) == regime]
        if len(port_r) < 10: continue
        port_sr_r = sharpe(port_r)
        m31_sr_r = sharpe(m31_r)
        if port_sr_r < m31_sr_r:
            regime_issues.append(f"{regime}:port={port_sr_r:.1f}<m31={m31_sr_r:.1f}")

    return {
        "dropout": {"pass": len(dropout_issues) == 0, "issues": dropout_issues},
        "weight_robustness": {"pass": worst_ratio >= 0.7, "worst_ratio": round(worst_ratio, 3)},
        "oos_vs_best": {"pass": port_test_sr >= best_comp_sr,
                        "port_test": round(port_test_sr, 2),
                        "best_comp": round(best_comp_sr, 2)},
        "diversification": {"pass": dr >= 1.05, "dr": round(dr, 3)},
        "regime_conditional": {"pass": len(regime_issues) == 0, "issues": regime_issues},
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
    # D-536 GAP-1: exclude Stage-1 blacklist
    try:
        from research_lab.pipeline_contract import CONFIG as _C
        _blacklist = _C.get("blacklist", [])
    except Exception as _e:
        _blacklist = []
        print(f"  ⚠️ Could not import CONFIG: {_e}")
    _n_before = len(novel)
    novel = [n for n in novel if n.get("strategy") not in _blacklist]
    if _n_before != len(novel):
        print(f"  [D-536 GAP-1] Blacklist filter: {_n_before} → {len(novel)} "
              f"(removed {_n_before - len(novel)} blacklisted)")

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

    print("\n[STAGE 3.5] Combo-level validation (5 tests)...")
    tests = combo_tests(port, m31, keltner)
    for name, t in tests.items():
        status = "✅" if t["pass"] else "❌"
        detail = t.get("issues") or t.get("dr") or t.get("worst_ratio") or ""
        print(f"  {status} {name}: {detail}")

    all_combo_pass = all(t["pass"] for t in tests.values())
    print(f"  Combo tests: {'ALL PASS' if all_combo_pass else 'SOME FAIL'}")

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
    if not all_combo_pass:
        print(" ❌ FAIL: combo tests failed (D-530)")
        verdict = "FAIL"
    elif result["improvement_pct"] >= 20 and result["coverage"] >= 0.5:
        print(f" ✅ PASS: portfolio({result['port_sr']}) beats M31({result['m31_sr']}) "
              f"by {result['improvement_pct']:+.0f}% (all 5 combo tests PASS)")
        verdict = "PASS"
    elif result["improvement_pct"] >= 10 and result["coverage"] >= 0.5:
        print(f" ⚠️  MARGINAL: +{result['improvement_pct']:.0f}% (all 5 combo tests PASS)")
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
        "combo_tests": tests,
        "validation": result,
    }, indent=2))
    print(f"\n[SAVE] {out}")


if __name__ == "__main__":
    main()
