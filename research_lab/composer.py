"""composer.py — Build per-regime portfolios (Route A: M31+, Route B: free).
D-400: Correlation-aware greedy search with quality gates.
"""
import sys, os, json, math
from collections import defaultdict
sys.path.append(os.getcwd())

from research_lab.audit_core import portfolio_daily_returns

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}
PROFILE_DIR = "research_lab/logs/profiles"
RETURNS_DIR = os.path.join(PROFILE_DIR, "returns_matrices")
OUT_FILE = "exchanges/portfolio_by_regime.json"
REPORT_FILE = "research_lab/logs/composer_report.md"

CONFIG = {
    "min_n": 30, "min_q_pass": 4, "min_ann_sr": 1.5,
    "max_corr": 0.4, "min_improvement": 1.10, "max_components": 3,
    "exclude_families": ["FUNDING_M31"],
    "blacklist": ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"],
    "m31_cap": {"hyperliquid": 0.65, "aster": 0.40, "kucoin": 0.30},
    "min_overlap_days": 60,   # D-400c: was 20, too noisy
}

FAMILY = {}
for s in ["M31","M31_EMA","M31_QUANTILE","M31_MOMENTUM","M31_THRESHOLD","M31_SMA"]: FAMILY[s]="FUNDING_M31"
for s in ["BOLLINGER","KELTNER_REV","ZSCORE","RSI_REVERSAL","MEAN_REV_SMA","RSI_DIVERGENCE","CONNORS_RSI","RSI_MEAN"]: FAMILY[s]="MR"
for s in ["EMA_CROSS","MACD","ADX_TREND","SUPERTREND","DONCHIAN","TRIPLE_EMA","ICHIMOKU","PSAR"]: FAMILY[s]="TREND"
for s in ["ROC","RSI_MOMENTUM","MOMENTUM_EMA","MOMENTUM_SMA","DUAL_MOMENTUM","PRICE_MOMENTUM","ELDER_IMPULSE"]: FAMILY[s]="MOMENTUM"
for s in ["BB_SQUEEZE","KELTNER_SQUEEZE","ATR_BREAKOUT","NR_BREAKOUT","VOL_DONCHIAN"]: FAMILY[s]="VOL"
for s in ["OBV","MFI","VWAP","VOLUME_BREAKOUT"]: FAMILY[s]="VOLUME"
FAMILY["PRICE_SMA"] = "PRICE"


# ─────────── Regime by date (D-400b fix) ───────────
from datetime import datetime, timezone
from research_lab.regime_core import detect_regime
from strategies.core_engine import load_data

_regime_cache = {}

def regime_by_date(exchange):
    """Return {date_str: regime} for exchange based on BTC candles."""
    if exchange in _regime_cache:
        return _regime_cache[exchange]
    syms = EXCHANGES[exchange]
    btc = load_data(exchange, syms[0])
    out = {}
    if not btc or len(btc) < 60:
        _regime_cache[exchange] = out
        return out
    for i in range(60, len(btc)):
        reg = detect_regime(btc, i=i)
        if reg == "UNKNOWN": continue
        day = datetime.fromtimestamp(btc[i]["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        out[day] = reg
    _regime_cache[exchange] = out
    return out

def filter_by_regime(rets_dict, reg_by_date, regime):
    return {d: r for d, r in rets_dict.items() if reg_by_date.get(d) == regime}

def load_state():
    with open(os.path.join(PROFILE_DIR, "state.json")) as f:
        return json.load(f)

def load_returns(ex, st, h, sy):
    p = os.path.join(RETURNS_DIR, ex, f"{st}_{h}_{sy}.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def build_combination(m31_rets, complements_rets, max_components=3):
    """D-407: Take M31 + top N complements (family-diverse), return weights+metrics."""
    if not m31_rets or not complements_rets:
        return None
    
    # Family diversity: max 1 per family
    selected = []
    seen_families = set()
    for comp in complements_rets:
        if comp["family"] in seen_families: continue
        seen_families.add(comp["family"])
        selected.append(comp)
        if len(selected) >= max_components - 1:  # -1 for M31
            break
    
    if not selected:
        return None
    
    # Build weights: M31 + each selected complement (equal weight to complements)
    all_rets = [m31_rets] + [s["rets"] for s in selected]
    common_dates = set(m31_rets.keys())
    for r in all_rets[1:]:
        common_dates &= set(r.keys())
    common_dates = sorted(common_dates)
    if len(common_dates) < 30:
        return None
    
    # Equal weights: M31 gets 50%, rest split 50%
    weights = [0.5] + [0.5/len(selected)] * len(selected)
    combined = {}
    for d in common_dates:
        combined[d] = sum(w * r[d] for w, r in zip(weights, all_rets))
    
    combined_sr = sharpe(list(combined.values()))
    m31_sr = sharpe([m31_rets[d] for d in common_dates])
    
    # MaxDD
    eq = 1.0; peak = 1.0; mdd = 0
    for r in combined.values():
        eq *= (1 + r); peak = max(peak, eq); mdd = max(mdd, (peak-eq)/peak)
    
    return {
        "components": [{"name": "M31", "weight": 0.5}] +
                      [{"name": f"{s['strategy']}_{s['symbol']}", "weight": round(0.5/len(selected),4),
                        "family": s["family"], "corr": s["corr_m31"]} for s in selected],
        "n_days": len(common_dates),
        "combined_sharpe": round(combined_sr, 3),
        "m31_only_sharpe": round(m31_sr, 3),
        "improvement": round(combined_sr / m31_sr if m31_sr > 0 else 0, 2),
        "max_dd_pct": round(mdd*100, 2),
        "passes_gate": combined_sr >= m31_sr * 1.10,
    }

def find_complements(state, regime, exchange, m31_rets, exclude_families=None, max_corr=0.3):
    """D-406: Find strategies with LOW corr to M31 (true complements)."""
    import os as _os, json as _json
    if exclude_families is None:
        exclude_families = {"FUNDING_M31"}

    complements = []
    for key, v in state["done"].items():
        if not isinstance(v, dict): continue
        if v["exchange"] != exchange: continue
        st = v["strategy"]
        fam = FAMILY.get(st, "OTHER")
        if fam in exclude_families: continue

        m = v["metrics_by_regime"].get(regime)
        if not m or not m["sufficient"] or m["n"] < CONFIG["min_n"]: continue
        val = v.get("validation")
        if not val: continue
        if val.get("quartiles_pass", 0) < CONFIG["min_q_pass"]: continue

        # Stress check
        stress = val.get("stress", {})
        if stress:
            if stress.get("fee_2x", {}).get("pf", 0) < 1.2: continue
            if stress.get("param_robustness", {}).get("verdict") == "FRAGILE": continue

        try: h = key.split(":")[2]
        except: continue

        rets_path = _os.path.join(RETURNS_DIR, exchange, f"{st}_{h}_{v['symbol']}.json")
        if not _os.path.exists(rets_path): continue
        rets = _json.load(open(rets_path))

        # Compute corr with M31
        common = sorted(set(rets.keys()) & set(m31_rets.keys()))
        if len(common) < 20: continue
        va = [m31_rets[d] for d in common]
        vb = [rets[d] for d in common]
        ma = sum(va)/len(va); mb = sum(vb)/len(vb)
        cov = sum((va[i]-ma)*(vb[i]-mb) for i in range(len(va)))
        sa = math.sqrt(sum((v-ma)**2 for v in va))
        sb = math.sqrt(sum((v-mb)**2 for v in vb))
        corr = cov/(sa*sb) if sa > 0 and sb > 0 else 1.0

        if corr > max_corr: continue  # not a complement

        complements.append({
            "strategy": st, "family": fam, "symbol": v["symbol"],
            "n": m["n"], "pf": m["pf"], "sr_daily": m["sharpe_daily"],
            "corr_m31": round(corr, 3),
            "ann_sr_validation": val.get("sharpe_ann", 0),
            "quartiles_pass": val.get("quartiles_pass", 0),
        })
    complements.sort(key=lambda x: (-x["ann_sr_validation"], abs(x["corr_m31"])))
    return complements

def filter_candidates(state, regime, exchange):
    out = []
    for key, v in state["done"].items():
        if not isinstance(v, dict): continue
        if v["exchange"] != exchange: continue
        st = v["strategy"]
        if st in CONFIG["blacklist"]: continue
        fam = FAMILY.get(st, "OTHER")
        if fam in CONFIG["exclude_families"]: continue
        m = v["metrics_by_regime"].get(regime)
        if not m or not m["sufficient"] or m["n"] < CONFIG["min_n"]: continue
        val = v.get("validation")
        if not val or val.get("quartiles_pass",0) < CONFIG["min_q_pass"]: continue
        if val.get("sharpe_ann",0) <= CONFIG["min_ann_sr"]: continue

        # D-407: Full validation gates (Calmar + stress)
        stress = val.get("stress", {})
        if stress:
            fee = stress.get("fee_2x", {})
            if fee.get("pf", 0) and fee["pf"] < 1.2: continue
            slip = stress.get("slippage_1.5x", {})
            if slip.get("sharpe_ann", 1) < 0: continue
            rob = stress.get("param_robustness", {})
            if rob.get("verdict") == "FRAGILE": continue

        # D-407: Calmar gate
        calmar_data = val.get("calmar", {})
        if calmar_data:
            if calmar_data.get("max_dd_pct", 0) > 60: continue

        try:
            h = key.split(":")[2]
        except: continue
        out.append({"strategy": st, "exchange": exchange, "symbol": v["symbol"],
                    "hash": h, "family": fam, "n": m["n"], "pf": m["pf"],
                    "sr_daily": m["sharpe_daily"], "val": val})
    return out

def overlap_returns(rets_list):
    """Intersect dates across all return dicts."""
    if not rets_list: return {}
    common = set(rets_list[0].keys())
    for r in rets_list[1:]:
        common &= set(r.keys())
    return {d: [r[d] for r in rets_list] for d in sorted(common)}

def weighted_returns(components, weights):
    """Combine multiple return dicts with weights."""
    dates = set()
    for r in components: dates |= set(r.keys())
    dates = sorted(dates)
    out = {}
    for d in dates:
        total_w = 0; total_r = 0
        for r, w in zip(components, weights):
            if d in r:
                total_r += w * r[d]
                total_w += w
        if total_w > 0: out[d] = total_r / total_w
    return out

def sharpe(rets):
    if len(rets) < 10: return 0
    m = sum(rets)/len(rets)
    v = sum((r-m)**2 for r in rets)/(len(rets)-1) if len(rets) > 1 else 0
    s = math.sqrt(v)
    return (m/s)*math.sqrt(365) if s > 0 else 0

def corr(a, b, dates):
    if len(dates) < CONFIG["min_overlap_days"]: return 1.0
    va = [a[d] for d in dates if d in a]
    vb = [b[d] for d in dates if d in b]
    n = min(len(va), len(vb))
    if n < CONFIG["min_overlap_days"]: return 1.0
    ma = sum(va[:n])/n; mb = sum(vb[:n])/n
    ca = sum((va[i]-ma)*(vb[i]-mb) for i in range(n))
    sa = math.sqrt(sum((v-ma)**2 for v in va[:n]))
    sb = math.sqrt(sum((v-mb)**2 for v in vb[:n]))
    return ca/(sa*sb) if sa>0 and sb>0 else 1.0

def max_dd(rets):
    eq = 1.0; peak = 1.0; dd = 0
    for r in rets:
        eq *= (1 + r)
        peak = max(peak, eq)
        dd = max(dd, (peak-eq)/peak)
    return dd

def greedy_build(base_name, base_rets, candidates_dict, initial_weights=None):
    """Greedy: add candidates one by one if they improve and corr<max."""
    selected = [(base_name, base_rets)]
    weights = [initial_weights.get(base_name, 1.0)] if initial_weights else [1.0]
    dates = set(base_rets.keys())
    current_sr = sharpe(list(base_rets.values()))
    history = [{"step": "base", "name": base_name, "sharpe": round(current_sr,3)}]

    while len(selected) < CONFIG["max_components"]:
        best = None; best_sr = current_sr
        for name, rets in candidates_dict.items():
            if any(n == name for n,_ in selected): continue
            common = dates & set(rets.keys())
            if len(common) < CONFIG["min_overlap_days"]: continue
            # Corr with all selected
            max_c = max(corr(rets, s_rets, sorted(common)) for _, s_rets in selected)
            if max_c > CONFIG["max_corr"]: continue
            # Test combination
            test_comps = [r for _, r in selected] + [rets]
            test_w = weights + [weights[0]]  # new component same weight as base
            combined = weighted_returns(test_comps, test_w)
            new_sr = sharpe(list(combined.values()))
            if new_sr > best_sr * CONFIG["min_improvement"]:
                best_sr = new_sr; best = (name, rets)
        if not best: break
        selected.append(best)
        weights.append(weights[0])
        dates &= set(best[1].keys())
        current_sr = best_sr
        history.append({"step": len(selected)-1, "name": best[0],
                        "sharpe": round(current_sr,3), "n_days": len(dates)})
    return selected, history

def compose_regime(regime, exchange, state, m31_rets_full):
    """Build Route A (M31+) and Route B (free) for one regime."""
    cands = filter_candidates(state, regime, exchange)
    if not cands:
        return {"route_a": None, "route_b": None, "candidates": [], "reason": "no_candidates"}

    # D-400b: filter returns by regime
    reg_by_date = regime_by_date(exchange)
    m31_rets = filter_by_regime(m31_rets_full, reg_by_date, regime)

    cand_rets = {}
    for c in cands:
        rets_full = load_returns(exchange, c["strategy"], c["hash"], c["symbol"])
        rets = filter_by_regime(rets_full, reg_by_date, regime)
        if len(rets) >= 5:
            name = f"{c['strategy']}_{c['symbol']}"
            cand_rets[name] = rets

    if not cand_rets:
        return {"route_a": None, "route_b": None, "candidates": cands,
                "reason": f"no_data_after_regime_filter (regime_days={len(m31_rets)})"}

    # Route A: M31 as base
    m31_cap = CONFIG["m31_cap"][exchange]
    if m31_cap > 0 and m31_rets:
        sel_a, hist_a = greedy_build("M31", m31_rets, cand_rets,
                                       initial_weights={"M31": m31_cap})
        base_sr = sharpe(list(m31_rets.values()))
        combined_a = weighted_returns([r for _,r in sel_a], [1.0]*len(sel_a))
        sr_a = sharpe(list(combined_a.values()))
        route_a = {
            "components": [{"name": n, "family": FAMILY.get(n.split("_")[0],"OTHER")}
                           for n,_ in sel_a],
            "n_days": len(combined_a),
            "sharpe_ann": round(sr_a,3),
            "max_dd": round(max_dd(list(combined_a.values()))*100,2),
            "history": hist_a,
            "improvement_vs_m31": round(sr_a/base_sr if base_sr>0 else 0, 2),
        }
    else:
        route_a = None

    # Route B: free discovery (best single + greedy)
    best_single = None; best_sr = 0
    for name, rets in cand_rets.items():
        sr = sharpe(list(rets.values()))
        if sr > best_sr: best_sr = sr; best_single = name
    if best_single:
        sel_b, hist_b = greedy_build(best_single, cand_rets[best_single],
                                       {k:v for k,v in cand_rets.items() if k!=best_single})
        combined_b = weighted_returns([r for _,r in sel_b], [1.0]*len(sel_b))
        sr_b = sharpe(list(combined_b.values()))
        route_b = {
            "components": [{"name": n, "family": FAMILY.get(n.split("_")[0],"OTHER")}
                           for n,_ in sel_b],
            "n_days": len(combined_b),
            "sharpe_ann": round(sr_b,3),
            "max_dd": round(max_dd(list(combined_b.values()))*100,2),
            "history": hist_b,
        }
    else:
        route_b = None

    # D-400c: reject noisy winners (insufficient days)
    MIN_DAYS = CONFIG["min_overlap_days"]

    def is_noisy(route):
        if not route: return True
        return route.get("n_days", 0) < MIN_DAYS

    # Winner selection with noise guard AND Route B must beat M31
    m31_sr = sharpe(list(m31_rets.values())) if m31_rets else 0
    m31_sr_adj = m31_sr * CONFIG["min_improvement"] if m31_sr > 0 else 0

    cand_a = route_a if route_a and not is_noisy(route_a) and \
              route_a["improvement_vs_m31"] >= CONFIG["min_improvement"] else None
    cand_b = route_b if route_b and not is_noisy(route_b) and \
              route_b["sharpe_ann"] > m31_sr_adj else None

    if cand_a and (not cand_b or cand_a["sharpe_ann"] >= cand_b["sharpe_ann"]):
        winner = {"route": "A", **cand_a}
    elif cand_b:
        winner = {"route": "B", **cand_b, "needs_manual_approval": True}
    elif m31_cap > 0 and m31_rets and len(m31_rets) >= MIN_DAYS:
        winner = {"route": "M31_ONLY",
                  "sharpe_ann": round(sharpe(list(m31_rets.values())),3),
                  "n_days": len(m31_rets)}
    elif m31_cap > 0 and m31_rets:
        # M31 alone but insufficient days
        winner = {"route": "M31_ONLY_INSUFFICIENT",
                  "sharpe_ann": round(sharpe(list(m31_rets.values())),3),
                  "n_days": len(m31_rets)}
    else:
        winner = None

    return {"route_a": route_a, "route_b": route_b,
            "winner": winner, "candidates": cands, "reason": None}

def main():
    print("="*70)
    print("  COMPOSER — Portfolio by Regime (D-400)")
    print("="*70)

    state = load_state()
    portfolio = {}
    report_lines = ["# Composer Report\n"]

    for exchange, symbols in EXCHANGES.items():
        print(f"\n═══ {exchange.upper()} ═══")
        m31_daily = portfolio_daily_returns(exchange, symbols)
        m31_rets = {d: r for d, r in m31_daily}
        if m31_rets:
            print(f"  M31 baseline: n={len(m31_rets)} Sharpe={sharpe(list(m31_rets.values())):.3f}")

        portfolio[exchange] = {}
        report_lines.append(f"\n## {exchange.upper()}\n")
        report_lines.append(f"- M31 baseline: n={len(m31_rets)}, SR={sharpe(list(m31_rets.values())):.3f}")

        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            res = compose_regime(regime, exchange, state, m31_rets)
            if res["reason"]:
                print(f"  [{regime}] {res['reason']}")
                portfolio[exchange][regime] = {"M31": CONFIG["m31_cap"][exchange] or 0.0,
                                                "CASH": 1.0 - (CONFIG["m31_cap"][exchange] or 0.0)}
                report_lines.append(f"\n### {regime}\n- {res['reason']} → M31-only")
                continue

            w = res["winner"]
            if w is None:
                print(f"  [{regime}] no winner — M31 only")
                portfolio[exchange][regime] = {"M31": CONFIG["m31_cap"][exchange] or 0.0,
                                                "CASH": 1.0 - (CONFIG["m31_cap"][exchange] or 0.0)}
                report_lines.append(f"\n### {regime}\n- no winner")
                continue

            # Build weights
            route = w.get("route", "?")
            comps = w.get("components", [])
            if route in ("M31_ONLY", "M31_ONLY_INSUFFICIENT"):
                weights = {"M31": CONFIG["m31_cap"][exchange] or 0.0}
            elif route == "A":
                weights = {"M31": CONFIG["m31_cap"][exchange]}
                per = (1.0 - CONFIG["m31_cap"][exchange]) / max(len(comps), 1)
                for c in comps:
                    weights[c["name"]] = per
            else:  # route == "B"
                weights = {}
                per = 1.0 / max(len(comps), 1)
                for c in comps:
                    weights[c["name"]] = per
            weights["CASH"] = max(0, 1.0 - sum(v for k,v in weights.items() if k != "CASH"))
            portfolio[exchange][regime] = weights

            n_d = w.get('n_days', 0)
            noise_flag = " ⚠️ NOISE" if n_d and n_d < CONFIG["min_overlap_days"] else ""
            _ra = res.get("route_a")
            if _ra and _ra.get("components"):
                _ra_n = _ra.get("n_days", 0)
                if _ra_n < CONFIG["min_overlap_days"]:
                    noise_flag += f" [RouteA rejected: n_days={_ra_n}<{CONFIG['min_overlap_days']}]"
            print(f"  [{regime}] route={route} SR={w.get('sharpe_ann','?')} "
                  f"n_days={n_d} components={[c['name'] for c in comps]}{noise_flag}")
            report_lines.append(f"\n### {regime}\n- route={route}, SR={w.get('sharpe_ann')}, "
                                f"n_days={w.get('n_days')}\n- components: "
                                f"{[c['name'] for c in comps]}\n- weights: {weights}")

    # D-406: Complement search per exchange/regime
    print("\n" + "="*70)
    print("  COMPLEMENTARY STRATEGIES (corr<0.3 with M31)")
    print("="*70)
    for exchange, symbols in EXCHANGES.items():
        m31_daily = portfolio_daily_returns(exchange, symbols)
        m31_rets = dict(m31_daily)
        if not m31_rets: continue
        print(f"\n─── {exchange.upper()} ───")
        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            reg_by_date = regime_by_date(exchange)
            m31_reg = {d: r for d, r in m31_rets.items() if reg_by_date.get(d) == regime}
            if len(m31_reg) < 20: continue
            comps = find_complements(state, regime, exchange, m31_reg)
            if comps:
                print(f"  [{regime}] {len(comps)} complements found:")
                for comp in comps[:5]:
                    print(f"    {comp['strategy']:20s} [{comp['family']:10s}] "
                          f"SR_val={comp['ann_sr_validation']:5.2f} "
                          f"corr={comp['corr_m31']:+.2f} q={comp['quartiles_pass']}/4")
                
                # D-407: Try to BUILD a real combination
                comps_with_rets = []
                for comp in comps:
                    rets_path = os.path.join(RETURNS_DIR, exchange,
                                             f"{comp['strategy']}_{comp['hash']}_{comp['symbol']}.json") \
                                if 'hash' in comp else None
                    # find via state
                    for k, v in state["done"].items():
                        if isinstance(v, dict) and v["strategy"] == comp["strategy"] \
                           and v["symbol"] == comp["symbol"] and v["exchange"] == exchange:
                            try:
                                h = k.split(":")[2]
                                rp = os.path.join(RETURNS_DIR, exchange, f"{comp['strategy']}_{h}_{comp['symbol']}.json")
                                if os.path.exists(rp):
                                    r = json.load(open(rp))
                                    reg_filtered = {d: x for d, x in r.items() if reg_by_date.get(d) == regime}
                                    if len(reg_filtered) >= 30:
                                        comps_with_rets.append({**comp, "rets": reg_filtered})
                            except: pass
                            break
                
                if comps_with_rets:
                    combo = build_combination(m31_reg, comps_with_rets)
                    if combo:
                        verdict = "✅ PASS GATE" if combo["passes_gate"] else "❌ below M31×1.1"
                        print(f"    → COMBO: SR={combo['combined_sharpe']} vs M31={combo['m31_only_sharpe']} "
                              f"(Δ={combo['improvement']}x) DD={combo['max_dd_pct']}% {verdict}")
                        print(f"    → Weights: {[c['name']+':'+str(c['weight']) for c in combo['components']]}")
                        if combo["passes_gate"]:
                            portfolio[exchange][regime] = {
                                c["name"]: c["weight"] for c in combo["components"]
                            }
                            portfolio[exchange][regime]["CASH"] = 0.0
                report_lines.append(f"\n### {exchange.upper()}/{regime} complements:\n" +
                    "\n".join(f"- {c['strategy']} corr={c['corr_m31']} SR={c['ann_sr_validation']}" for c in comps[:5]))

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)
    print(f"\n[SAVE] {OUT_FILE}")

    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(report_lines))
    print(f"[SAVE] {REPORT_FILE}")

    print("\n" + "="*70)
    print("  COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
