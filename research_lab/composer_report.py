"""D-447: Structured report of composer results (JSON + Markdown)."""
import os, sys, json
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())
from research_lab.composer import (
    EXCHANGES, CONFIG, FAMILY, PROFILE_DIR,
    _pooled_get, regime_by_date, apply_m31_fees,
)
from research_lab.audit_core import portfolio_daily_returns
from research_lab.strategy_signature import signature_for_m31, find_m31_weaknesses


def _audit(v, regime, exchange, state):
    fails = []
    st = v.get("strategy", "")
    fam = FAMILY.get(st, "OTHER")
    if st in CONFIG["blacklist"]: fails.append("blacklist")
    if fam in CONFIG["exclude_families"]: fails.append("family_excluded")
    m = v.get("metrics_by_regime", {}).get(regime)
    if not m or not m.get("sufficient"):
        fails.append(f"regime_n={m.get('n', 0) if m else 0}")
    else:
        pn = len(_pooled_get(exchange, st, state))
        if pn < CONFIG["min_n"]: fails.append(f"pooled_n={pn}")
    val = v.get("validation", {})
    if not val:
        fails.append("no_validation")
    else:
        if val.get("quartiles_pass", 0) < CONFIG["min_q_pass"]:
            fails.append(f"quartiles={val.get('quartiles_pass')}/4")
        sr = val.get("sharpe_ann", 0)
        if sr <= CONFIG["min_ann_sr"]: fails.append(f"sharpe_ann={sr:.2f}")
        stress = val.get("stress", {})
        if stress:
            fee = stress.get("fee_2x", {})
            if fee.get("pf", 0) and fee["pf"] < 1.2:
                fails.append(f"fee_2x={fee['pf']:.2f}")
            rob = stress.get("param_robustness", {})
            if rob.get("verdict") == "FRAGILE": fails.append("param_fragile")
        calmar = val.get("calmar", {})
        if calmar and calmar.get("max_dd_pct", 0) > 60:
            fails.append(f"dd={calmar['max_dd_pct']:.0f}%")
    detail = {
        "strategy": st, "symbol": v.get("symbol"), "family": fam,
        "sharpe_ann": val.get("sharpe_ann") if val else None,
        "quartiles": val.get("quartiles_pass") if val else None,
        "n_regime": m.get("n") if m else 0,
        "pooled_n": len(_pooled_get(exchange, st, state)),
    }
    return len(fails) == 0, fails, detail


def generate():
    state = json.load(open(os.path.join(PROFILE_DIR, "state.json")))
    pending_path = "exchanges/pending_approvals.json"
    pending = json.load(open(pending_path)) if os.path.exists(pending_path) else {}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_entries": sum(1 for v in state["done"].values() if isinstance(v, dict)),
        "config": {k: CONFIG[k] for k in ["min_n", "min_q_pass", "min_ann_sr"]},
        "exchanges": {},
    }

    for exchange, symbols in EXCHANGES.items():
        m31_rets = apply_m31_fees(dict(portfolio_daily_returns(exchange, symbols)))
        if exchange == "aster":
            _r = regime_by_date("aster")
            if len(set(m31_rets) & set(_r)) < 30:
                m31_rets = apply_m31_fees(
                    dict(portfolio_daily_returns("hyperliquid", EXCHANGES["hyperliquid"]))
                )
        m31_sig = signature_for_m31(exchange, m31_rets)
        weaknesses = find_m31_weaknesses(m31_sig)
        ex = {
            "m31_sharpe_by_regime": m31_sig.get("sharpe_by_regime"),
            "m31_low_vol": m31_sig.get("sharpe_low_vol"),
            "m31_high_vol": m31_sig.get("sharpe_high_vol"),
            "m31_weaknesses": weaknesses,
            "regimes": {},
        }
        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            stats = {"examined": 0, "passed_gates": [], "rejected_by_gate": {},
                     "sample_rejections": [], "pending_combo": pending.get(f"{exchange}/{regime}")}
            for key, v in state["done"].items():
                if not isinstance(v, dict): continue
                if v.get("exchange") != exchange: continue
                if regime not in v.get("metrics_by_regime", {}): continue
                stats["examined"] += 1
                passed, fails, detail = _audit(v, regime, exchange, state)
                if passed:
                    stats["passed_gates"].append(detail)
                else:
                    primary = fails[0].split("=")[0].split("(")[0]
                    stats["rejected_by_gate"][primary] = stats["rejected_by_gate"].get(primary, 0) + 1
                    if len(stats["sample_rejections"]) < 10:
                        stats["sample_rejections"].append({**detail, "first_fail": fails[0], "all_fails": fails})
            stats["passed_gates"].sort(key=lambda x: -(x.get("sharpe_ann") or 0))
            stats["passed_gates"] = stats["passed_gates"][:15]
            ex["regimes"][regime] = stats
        report["exchanges"][exchange] = ex

    json.dump(report, open("research_lab/logs/composer_full_report.json", "w"),
              indent=2, default=str)
    md = _md(report)
    open("research_lab/logs/composer_summary.md", "w").write(md)
    print("✅ composer_full_report.json")
    print("✅ composer_summary.md")


def _md(r):
    L = [f"# Composer Report — {r['generated_at'][:10]}", ""]
    L.append(f"**Total entries**: {r['total_entries']}  ")
    L.append(f"**Thresholds**: n≥{r['config']['min_n']}, "
             f"q≥{r['config']['min_q_pass']}/4, SR>{r['config']['min_ann_sr']}")
    for ex, ed in r["exchanges"].items():
        L.append(f"\n## {ex.upper()}\n")
        L.append(f"- M31 weaknesses: `{ed['m31_weaknesses']}`")
        L.append(f"- M31 by regime: `{ed['m31_sharpe_by_regime']}`")
        L.append(f"- M31 vol: low={ed['m31_low_vol']}, high={ed['m31_high_vol']}")
        for reg, s in ed["regimes"].items():
            L.append(f"\n### {reg}\n")
            L.append(f"- Examined: **{s['examined']}** | Passed: **{len(s['passed_gates'])}**")
            if s["rejected_by_gate"]:
                L.append(f"- **Rejected by gate**:")
                for g, c in sorted(s["rejected_by_gate"].items(), key=lambda x: -x[1]):
                    L.append(f"  - `{g}`: {c}")
            if s["passed_gates"]:
                L.append(f"- **Top passed**:")
                for p in s["passed_gates"][:5]:
                    L.append(f"  - `{p['strategy']}/{p['symbol']}`: SR={p['sharpe_ann']:.2f}, "
                             f"q={p['quartiles']}/4, n_reg={p['n_regime']}, n_pooled={p['pooled_n']}")
            pc = s.get("pending_combo")
            if pc:
                combo = pc.get("combo", {})
                L.append(f"- **Pending**: `{pc.get('status')}`")
                cs = ", ".join(f"{c['name']}={c.get('weight',0)*100:.1f}%" for c in combo.get("components", []))
                L.append(f"  - Weights: `{cs}`")
                L.append(f"  - SR={combo.get('combined_sharpe')}, n_days={combo.get('n_days')}")
                if pc.get("reasons"):
                    L.append(f"  - Reasons: {pc['reasons']}")
    return "\n".join(L)


if __name__ == "__main__":
    generate()
