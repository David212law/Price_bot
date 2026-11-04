"""D-521: Thesis-Driven Strategy Framework.

Every strategy must claim:
  1. Which regime it works in (economic thesis)
  2. Which regime it fails in (where it should be weak)

A strategy survives ONLY if its data confirms BOTH claims.
This separates real edges from statistical noise.
"""
import json
from pathlib import Path
from collections import defaultdict


# ═════════════════════════════════════════════════════════════════════
# THESIS REGISTRY — what each family claims
# ═════════════════════════════════════════════════════════════════════
FAMILY_THESES = {
    "funding": {
        "works_in": ["TREND", "RANGE", "NEUTRAL"],
        "fails_in": [],
        "min_sr": 2.0,
        "reason": "Funding is paid regardless of market regime (structural)",
    },
    "mr": {
        "works_in": ["RANGE"],
        "fails_in": ["TREND"],
        "min_sr": 1.5,
        "reason": "Mean reversion requires sideways markets (no trend to fight)",
    },
    "trend": {
        "works_in": ["TREND"],
        "fails_in": ["RANGE"],
        "min_sr": 1.5,
        "reason": "Trend following requires an actual trend",
    },
    "momentum": {
        "works_in": ["TREND"],
        "fails_in": ["RANGE"],
        "min_sr": 1.5,
        "reason": "Momentum requires continuation, absent in ranges",
    },
    "vol": {
        "works_in": ["RANGE", "NEUTRAL"],
        "fails_in": [],
        "min_sr": 1.5,
        "reason": "Volatility cycles are regime-agnostic",
    },
    "volume": {
        "works_in": ["TREND"],
        "fails_in": ["RANGE"],
        "min_sr": 1.5,
        "reason": "Volume signals confirm directional moves",
    },
}


def _annualize(daily_sr):
    return daily_sr * (365 ** 0.5)


def check_thesis_fit(entry, family):
    """Check if a strategy's data confirms its family thesis.

    Returns (score 0-1, sr_by_regime dict, reason).
    """
    thesis = FAMILY_THESES.get(family)
    if not thesis:
        return 0.0, {}, "no_thesis"

    mbr = entry.get("metrics_by_regime", {})
    if not mbr:
        return 0.0, {}, "no_regime_data"

    sr_by_regime = {}
    for regime in ["TREND", "RANGE", "NEUTRAL"]:
        m = mbr.get(regime, {})
        if m.get("sufficient") and m.get("sharpe_daily") is not None:
            sr_by_regime[regime] = _annualize(m["sharpe_daily"])

    if not sr_by_regime:
        return 0.0, {}, "no_regime_sr"

    # Score: works_in check
    works_scores = []
    for r in thesis["works_in"]:
        if r in sr_by_regime:
            works_scores.append(1.0 if sr_by_regime[r] >= thesis["min_sr"] else 0.0)
    works_score = sum(works_scores) / len(works_scores) if works_scores else 0.0

    # Score: fails_in check
    fails_score = 1.0
    if thesis["fails_in"]:
        works_regimes = [r for r in thesis["works_in"] if r in sr_by_regime]
        fails_regimes = [r for r in thesis["fails_in"] if r in sr_by_regime]
        if works_regimes and fails_regimes:
            works_avg = sum(sr_by_regime[r] for r in works_regimes) / len(works_regimes)
            fails_avg = sum(sr_by_regime[r] for r in fails_regimes) / len(fails_regimes)
            if works_avg > fails_avg * 1.2:
                fails_score = 1.0  # confirms: works regime > fails regime
            elif works_avg > fails_avg:
                fails_score = 0.5  # mild confirmation
            else:
                fails_score = 0.0  # contradicts

    score = 0.6 * works_score + 0.4 * fails_score
    return score, sr_by_regime, f"works={works_score:.2f} fails={fails_score:.2f}"


def main():
    from strategies.library.families import STRATEGY_FAMILY

    state_path = Path("research_lab/logs/profiles/state.json")
    if not state_path.exists():
        print(f"❌ {state_path} not found")
        return

    state = json.loads(state_path.read_text())
    done = state.get("done", {})

    print("=" * 70)
    print(" THESIS-DRIVEN STRATEGY FILTER (D-521)")
    print("=" * 70)
    print(f"Total entries: {len(done)}")

    by_family = defaultdict(lambda: {"total": 0, "fit": 0, "survivors": []})

    for key, entry in done.items():
        if not isinstance(entry, dict):
            continue
        val = entry.get("validation")
        if not val:
            continue
        st = entry.get("strategy", "")
        fam = STRATEGY_FAMILY.get(st, "OTHER")
        if fam not in FAMILY_THESES:
            continue

        by_family[fam]["total"] += 1
        score, sr_by_regime, reason = check_thesis_fit(entry, fam)

        if score >= 0.7:
            by_family[fam]["fit"] += 1
            by_family[fam]["survivors"].append({
                "key": key,
                "strategy": st,
                "family": fam,
                "exchange": entry.get("exchange"),
                "symbol": entry.get("symbol"),
                "score": round(score, 2),
                "sr": val.get("sharpe_ann", 0),
                "q": val.get("quartiles_pass", 0),
                "n": val.get("n"),
                "sr_by_regime": sr_by_regime,
                "reason": reason,
            })

    # Per-family summary
    print("\n=== Thesis Fit by Family ===")
    total_fit = 0
    total_all = 0
    for fam in sorted(by_family.keys()):
        d = by_family[fam]
        pct = 100 * d["fit"] / d["total"] if d["total"] > 0 else 0
        print(f"  {fam:12s}: {d['fit']:3d}/{d['total']:3d} pass ({pct:5.1f}%)")
        total_fit += d["fit"]
        total_all += d["total"]

    print(f"\nTotal survivors (score>=0.7): {total_fit}/{total_all} "
          f"({100*total_fit/total_all:.1f}%)")

    # Top survivors by SR
    all_survivors = []
    for fam, d in by_family.items():
        all_survivors.extend(d["survivors"])
    all_survivors.sort(key=lambda x: -x["sr"])

    print("\n=== Top 20 survivors (fit thesis + high SR) ===")
    for s in all_survivors[:20]:
        sr_str = " ".join(f"{r[:1]}={v:.1f}" for r, v in s["sr_by_regime"].items())
        print(f"  {s['strategy'][:28]:28s} {s['exchange']:10s} {s['symbol']:10s} "
              f"SR={s['sr']:5.2f} q={s['q']}/4 n={s['n']:3} | {sr_str}")
        print(f"    Family: {s['family']:10s} | Fit: {s['reason']}")

    # Best per family
    print("\n=== Best strategy per family (that fits thesis) ===")
    best_per_family = {}
    for s in all_survivors:
        if s["family"] not in best_per_family:
            best_per_family[s["family"]] = s
    for fam, best in sorted(best_per_family.items()):
        print(f"  {fam:12s}: {best['strategy'][:28]:28s} {best['exchange']:10s} "
              f"{best['symbol']:10s} SR={best['sr']:.2f}")

    # Cross-check with M31
    print("\n=== M31 baseline (from signature) ===")
    print("  TREND:   SR=12.27")
    print("  RANGE:   SR=11.91")
    print("  NEUTRAL: SR=10.80")
    print("  low_vol: SR=19.04")
    print("  high_vol: SR=8.01")

    # Save
    out_path = Path("research_lab/logs/thesis_analysis.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "generated_at": "2026-11-04",
        "total_analyzed": total_all,
        "survivors_count": total_fit,
        "by_family": {
            fam: {"pass": d["fit"], "fail": d["total"] - d["fit"]}
            for fam, d in by_family.items()
        },
        "survivors": all_survivors[:100],
    }, indent=2, default=str))
    print(f"\n[SAVE] {out_path}")
    print("\n" + "=" * 70)
    print(" DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
