"""D-527: Thesis Dedup — reduce each thesis group to distinct representatives.

Input: research_lab/logs/thesis_evidence.json (from D-526)
Output: per-thesis-group list of distinct representatives (corr < 0.5)
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


def corr(a, b):
    dates = sorted(set(a.keys()) & set(b.keys()))
    if len(dates) < 30: return 0.0
    va = [a[d] for d in dates]
    vb = [b[d] for d in dates]
    ma = sum(va) / len(va); mb = sum(vb) / len(vb)
    cov = sum((va[i] - ma) * (vb[i] - mb) for i in range(len(va)))
    sa = sum((x - ma) ** 2 for x in va) ** 0.5
    sb = sum((x - mb) ** 2 for x in vb) ** 0.5
    return round(cov / (sa * sb), 3) if sa * sb > 0 else 0.0


def load_returns(exchange, strategy, hash_val, symbol):
    p = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}/{strategy}_{hash_val}_{symbol}.json")
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except: return {}


def dedup_group(items, corr_threshold=0.70):
    """Greedy: sort by SR desc, keep item if corr < threshold with all kept."""
    items_sorted = sorted(items, key=lambda x: -x["baseline_sr"])
    kept = []
    for item in items_sorted:
        rets = load_returns(item["exchange"], item["strategy"], item["hash"], item["symbol"])
        if not rets: continue
        # D-536 GAP-3: reject artifacts with <30 days
        if len(rets) < 30: continue
        item["_rets"] = rets
        max_corr = 0.0
        is_dup = False
        for k in kept:
            c = corr(item["_rets"], k["_rets"])
            max_corr = max(max_corr, abs(c))
            if abs(c) > corr_threshold:
                is_dup = True
                break
        if not is_dup:
            item["_max_corr_with_kept"] = round(max_corr, 3)
            kept.append(item)
    return kept


def main():
    print("=" * 78)
    print(" Thesis Dedup — D-527")
    print("=" * 78)

    evidence_path = Path("research_lab/logs/thesis_evidence.json")
    if not evidence_path.exists():
        print(f"❌ {evidence_path} not found")
        return
    data = json.loads(evidence_path.read_text())
    by_hint = defaultdict(list)
    for r in data["results"]:
        by_hint[r["interpretation"]["primary"]].append(r)

    print(f"[LOAD] {len(data['results'])} strategies across {len(by_hint)} thesis groups\n")

    CORR_THRESHOLD = 0.70  # anything above this = duplicate

    final = {}
    for hint, items in sorted(by_hint.items(), key=lambda x: -len(x[1])):
        deduped = dedup_group(items, CORR_THRESHOLD)
        final[hint] = [
            {
                "strategy": d["strategy"],
                "exchange": d["exchange"],
                "symbol": d["symbol"],
                "hash": d["hash"],
                "baseline_sr": d["baseline_sr"],
                "hints": d["interpretation"]["hints"],
                "max_corr_with_kept": d.get("_max_corr_with_kept", 0),
            }
            for d in deduped
        ]
        print(f"{hint}: {len(items)} → {len(deduped)} distinct")
        for d in final[hint]:
            print(f"  {d['strategy']:25s} {d['exchange']:10s} {d['symbol']:10s} "
                  f"SR={d['baseline_sr']:5.2f} (max_corr={d['max_corr_with_kept']})")
        print()

    # Now check cross-group correlation between representatives
    print("=" * 78)
    print(" CROSS-GROUP CORRELATION (representatives only)")
    print("=" * 78)
    reps = []
    for hint, items in final.items():
        for item in items[:2]:  # top 2 per group
            reps.append({**item, "thesis": hint})

    if len(reps) > 1:
        print(f"\n{'':25s}", end="")
        for r in reps:
            print(f"{r['strategy'][:6]:>8s}", end="")
        print()
        for i, r1 in enumerate(reps):
            print(f"{r1['strategy'][:24]:25s}", end="")
            rets1 = load_returns(r1["exchange"], r1["strategy"], r1["hash"], r1["symbol"])
            for j, r2 in enumerate(reps):
                if i == j:
                    print(f"{'—':>8s}", end="")
                else:
                    rets2 = load_returns(r2["exchange"], r2["strategy"], r2["hash"], r2["symbol"])
                    c = corr(rets1, rets2)
                    print(f"{c:>8.2f}", end="")
            print()

    # Save
    out = Path("research_lab/logs/thesis_deduped.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corr_threshold": CORR_THRESHOLD,
        "by_thesis": final,
    }, indent=2))
    print(f"\n[SAVE] {out}")
    print(f"\n{'='*78}")
    print(f" TOTAL REPRESENTATIVES: {sum(len(v) for v in final.values())}")
    print(f" (was {len(data['results'])} raw)")
    print(f"{'='*78}")


if __name__ == "__main__":
    main()
