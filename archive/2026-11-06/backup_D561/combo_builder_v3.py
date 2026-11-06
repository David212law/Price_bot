"""D-553: Combo Builder v3 — Pareto-based combination per regime."""
import json
from pathlib import Path
from datetime import datetime, timezone
from .econ_registry import load_registry, get_strategies_for_regime

def sharpe(vals, tpy=365):
    if len(vals) < 20:
        return 0
    m = sum(vals) / len(vals)
    v = sum((x - m)**2 for x in vals) / len(vals)
    sd = v ** 0.5
    return (m / sd) * (tpy ** 0.5) if sd > 0 else 0

def compute_metrics(rets_dict, crisis_windows):
    if not rets_dict or len(rets_dict) < 20:
        return None
    dates = sorted(rets_dict.keys())
    vals = [rets_dict[d] for d in dates]
    n = len(vals)
    span = (datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(dates[0], "%Y-%m-%d")).days
    tpy = n / (span / 365.25) if span > 0 else 365
    m = sum(vals) / n
    v = sum((x - m)**2 for x in vals) / n
    sd = v ** 0.5
    sr = (m / sd) * (tpy ** 0.5) if sd > 0 else 0
    eq = [1.0]
    for r in vals:
        eq.append(eq[-1] * (1 + r))
    ret = (eq[-1] - 1) * 100
    peak = eq[0]
    dd = 0
    for e in eq:
        if e > peak:
            peak = e
        cur = (peak - e) / peak * 100 if peak > 0 else 0
        if cur > dd:
            dd = cur
    wr = sum(1 for v in vals if v > 0) / n * 100
    neg_pct = sum(1 for v in vals if v < 0) / n * 100
    n4 = n // 4
    pfs = []
    for i in range(4):
        chunk = vals[i*n4:(i+1)*n4]
        w = sum(v for v in chunk if v > 0)
        l = abs(sum(v for v in chunk if v < 0))
        pfs.append(w / l if l > 0 else (999 if w > 0 else 0))
    q4 = all(p > 1 for p in pfs)
    crisis_perf = {}
    for name, (start, end) in crisis_windows.items():
        crisis_dates = [d for d in dates if start <= d <= end]
        if crisis_dates:
            crisis_perf[name] = sum(rets_dict.get(d, 0) for d in crisis_dates) * 100
    return {"sr": sr, "dd": dd, "ret": ret, "wr": wr, "neg_pct": neg_pct, "q4": q4, "n": n, "crisis_perf": crisis_perf}

def pareto_filter(candidates, metrics_dict):
    pareto = []
    for name in candidates:
        m = metrics_dict.get(name)
        if not m:
            continue
        dominated = False
        for other in candidates:
            if other == name:
                continue
            o = metrics_dict.get(other)
            if not o:
                continue
            if (o["sr"] >= m["sr"] and o["dd"] <= m["dd"] and o["wr"] >= m["wr"] and o["ret"] >= m["ret"]):
                if (o["sr"] > m["sr"] or o["dd"] < m["dd"] or o["wr"] > m["wr"] or o["ret"] > m["ret"]):
                    dominated = True
                    break
        if not dominated:
            pareto.append(name)
    return pareto

def build_combo_for_regime(regime, candidates, all_returns, metrics_dict, crisis_windows, min_sr=3.0):
    registry = load_registry()
    compatible = get_strategies_for_regime(registry, regime)
    compatible_names = [s["strategy"] for s in compatible]
    valid = [c for c in candidates if c in compatible_names or any(c.startswith(s["strategy"]) for s in compatible)]
    if not valid:
        return {"error": f"no valid candidates for {regime}"}
    best_combo = None
    best_coverage = 0
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            name_i, name_j = valid[i], valid[j]
            if name_i not in all_returns or name_j not in all_returns:
                continue
            common = sorted(set(all_returns[name_i].keys()) & set(all_returns[name_j].keys()))
            if len(common) < 60:
                continue
            for w_i in [0.9, 0.8, 0.7, 0.6, 0.5]:
                w_j = 1 - w_i
                combo_rets = {d: all_returns[name_i][d] * w_i + all_returns[name_j][d] * w_j for d in common}
                combo_metrics = compute_metrics(combo_rets, crisis_windows)
                if not combo_metrics:
                    continue
                if combo_metrics["sr"] < min_sr:
                    continue
                coverage = 0
                if combo_metrics["sr"] >= 3: coverage += 1
                if combo_metrics["sr"] >= 2: coverage += 1
                if combo_metrics["ret"] / max(combo_metrics["dd"], 0.1) >= 5: coverage += 1
                if combo_metrics["dd"] < 10: coverage += 1
                if combo_metrics["dd"] < 5: coverage += 1
                if combo_metrics["ret"] > 20: coverage += 1
                if combo_metrics["wr"] > 50: coverage += 1
                if combo_metrics["neg_pct"] < 40: coverage += 1
                if combo_metrics["q4"]: coverage += 1
                for crisis_name, crisis_ret in combo_metrics["crisis_perf"].items():
                    if crisis_ret > 0:
                        coverage += 1
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_combo = {
                        "components": [
                            {"strategy": name_i, "weight": w_i},
                            {"strategy": name_j, "weight": w_j},
                        ],
                        "metrics": combo_metrics,
                        "coverage": coverage,
                        "regime": regime,
                    }
    return best_combo

def save_results(results, output_path="research_lab/logs/researcher_v3/combo_recipes.json"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "version": "3.0", "results": results}, indent=2, ensure_ascii=False))
