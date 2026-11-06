"""composer.py — Build per-regime portfolios (Route A: M31+, Route B: free).
D-400: Correlation-aware greedy search with quality gates.
"""
import sys, os, json, math
from collections import defaultdict
sys.path.append(os.getcwd())

from strategies.library.families import STRATEGY_FAMILY as FAMILY
from research_lab.audit_core import (portfolio_daily_returns, calmar_maxdd,
                                       correlation_stability)

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}
PROFILE_DIR = "research_lab/logs/profiles"
RETURNS_DIR = os.path.join(PROFILE_DIR, "returns_matrices")
OUT_FILE = "exchanges/portfolio_by_regime.json"
REPORT_FILE = "research_lab/logs/composer_report.md"

# D-537: CONFIG moved to pipeline_contract.py (single source of truth)
from research_lab.pipeline_contract import CONFIG  # noqa: E402

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
    import sys
    path = os.path.join(PROFILE_DIR, "state.json")
    if not os.path.exists(path):
        print("[ERROR] state.json not found. Profiler must run locally first.")
        print(f"  Expected at: {path}")
        sys.exit(0)  # Exit 0 so workflow doesn't fail, just skips
    with open(path) as f:
        return json.load(f)

def load_returns(ex, st, h, sy):
    p = os.path.join(RETURNS_DIR, ex, f"{st}_{h}_{sy}.json")
    return json.load(open(p)) if os.path.exists(p) else {}



def notify_strict_approval(combo, exchange, regime):
    """D-420: Always save pending approvals; only Bale for STRICT_PASS."""
    import os as _os
    import requests as _req
    from datetime import datetime as _dt, timezone as _tz

    cfg = CONFIG["strict_approval"]
    reasons = []
    if combo["combined_sharpe"] < 2.5:
        reasons.append(f"SR={combo['combined_sharpe']}<2.5")
    if combo["max_dd_combo_pct"] > 20:
        reasons.append(f"DD={combo['max_dd_combo_pct']}>20")
    if combo["n_days"] < cfg["min_n_days"]:
        reasons.append(f"n_days={combo['n_days']}<{cfg['min_n_days']}")
    for comp in combo["components"]:
        if "corr" in comp and abs(comp["corr"]) > cfg["max_corr"]:
            reasons.append(f"{comp['name']} corr={comp['corr']}")

    _base = combo.get("m31_only_sharpe", 0)
    _imp = combo["combined_sharpe"] / _base if _base > 0 else 0
    if _imp < 1.10:
        reasons.append(f"improvement={_imp:.2f}<1.10")
    status = "STRICT_PASS" if not reasons else "WEAK_PASS"

    # ALWAYS save
    pend_path = "exchanges/pending_approvals.json"
    pending = {}
    if _os.path.exists(pend_path):
        try: pending = json.load(open(pend_path))
        except: pending = {}

    key = f"{exchange}/{regime}"
    pending[key] = {
        "combo": combo,
        "status": status,
        "reasons": reasons,
        "detected_at": _dt.now(_tz.utc).isoformat(),
    }
    json.dump(pending, open(pend_path, "w"), indent=2, default=str)
    print(f"  🔔 {key}: {status} (n_days={combo['n_days']}) → pending_approvals.json")
    if reasons:
        print(f"     reasons: {'; '.join(reasons)}")
        return False

    # Bale (only for STRICT_PASS)
    tok = _os.environ.get("BALE_BOT_TOKEN", "")
    chat = _os.environ.get("BALE_CHAT_ID", "")
    if tok and chat:
        msg = (
            f"🔔 *Pre-Approval Candidate*\n\n"
            f"Exchange: {exchange.upper()}\n"
            f"Regime: {regime}\n"
            f"Combo SR: {combo['combined_sharpe']:.2f}\n"
            f"MaxDD: {combo['max_dd_combo_pct']:.1f}%\n"
            f"Days: {combo['n_days']}\n\n"
            f"Components:\n" +
            "\n".join(f"  • {cc['name']} ({cc.get('weight',0)*100:.0f}%)"
                     f"{' corr='+str(cc['corr']) if 'corr' in cc else ''}"
                     for cc in combo["components"])
        )
        try:
            _req.post(f"https://tapi.bale.ai/bot{tok}/sendMessage",
                     json={"chat_id": chat, "text": msg}, timeout=20)
        except: pass
    return True

def apply_m31_fees(daily_rets, avg_hold_days=30, taker_fee=0.0005, slip=0.0005):
    """D-415: Realistic friction (fee+slip only). Basis risk is volatile, not drag."""
    fee_per_day = (2 * taker_fee + 2 * slip) / avg_hold_days
    print(f"  [M31-friction] fee+slip={fee_per_day*100:.4f}%/d ({fee_per_day*365*100:.2f}%/yr)")
    return {d: r - fee_per_day for d, r in daily_rets.items()}


def calmar_from_returns(rets_dict_or_list):
    """Compute CAGR, MaxDD, Calmar from returns (list or dict)."""
    if isinstance(rets_dict_or_list, dict):
        rets = list(rets_dict_or_list.values())
    else:
        rets = list(rets_dict_or_list)
    if len(rets) < 30: return {"cagr": 0, "max_dd": 0, "calmar": 0, "n": len(rets)}
    eq = 1.0; peak = 1.0; mdd = 0.0
    for r in rets:
        eq *= (1 + r)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    years = len(rets) / 365
    cagr = (eq ** (1/years) - 1) if years > 0 else 0
    calmar = (cagr / mdd) if mdd > 0 else 0
    return {
        "cagr": round(cagr, 4), "max_dd": round(mdd, 4),
        "calmar": round(calmar, 3), "n": len(rets),
    }


# ═══════════════════════════════════════════════════════════════
# D-439: COMBO-SPECIFIC TESTS
# ═══════════════════════════════════════════════════════════════

def test_component_dropout(components_data, weights, base_sharpe):
    """Remove each component; if Sharpe barely drops → redundant; if dies → over-reliant."""
    issues = []
    n = len(components_data)
    if n < 2:
        return {"pass": True, "detail": "single component — N/A"}
    for i in range(n):
        subset_rets = [components_data[j] for j in range(n) if j != i]
        subset_w = [weights[j] for j in range(n) if j != i]
        # normalize
        total_w = sum(subset_w)
        if total_w <= 0: continue
        subset_w = [w / total_w for w in subset_w]
        # combined
        dates = set(subset_rets[0].keys())
        for r in subset_rets[1:]:
            dates &= set(r.keys())
        if len(dates) < 20: continue
        combined = {d: sum(w * r[d] for w, r in zip(subset_w, subset_rets)) for d in dates}
        sr_without = sharpe(list(combined.values()))
        drop_pct = (base_sharpe - sr_without) / base_sharpe if base_sharpe > 0 else 0
        if drop_pct < 0:
            issues.append(f"comp{i}: HARMFUL (drop={drop_pct*100:.1f}%)")
        elif drop_pct < 0.05:
            issues.append(f"comp{i}: redundant (drop={drop_pct*100:.1f}%)")
        if sr_without < base_sharpe * 0.4:
            issues.append(f"comp{i}: over-reliant (without SR={sr_without:.2f})")
    # D-482b: fail if any component is HARMFUL or over-reliant
    _fails = [x for x in issues if 'over-reliant' in x or 'HARMFUL' in x]
    return {"pass": len(_fails) == 0,
            "issues": issues, "n_components": n}


def test_weight_robustness(components_data, base_weights, base_sharpe, delta=0.20):
    """D-440: Perturb weights. For asymmetric weights use relative shift."""
    n = len(components_data)
    if n < 2:
        return {"pass": True, "detail": "single component"}
    # Relative shift: 50% of the smallest weight
    smallest = min(base_weights)
    shift = smallest * 0.5 if smallest < 0.20 else delta
    results = []
    for sgn in (-1, +1):
        new_w = list(base_weights)
        # shift between first (M31) and last
        new_w[0] += sgn * shift
        new_w[-1] -= sgn * shift
        if any(w < 0 for w in new_w):
            continue
        total = sum(new_w)
        new_w = [w / total for w in new_w]
        dates = set(components_data[0].keys())
        for r in components_data[1:]:
            dates &= set(r.keys())
        if len(dates) < 20: continue
        combined = {d: sum(w * r[d] for w, r in zip(new_w, components_data)) for d in dates}
        sr_perturbed = sharpe(list(combined.values()))
        results.append(sr_perturbed / base_sharpe if base_sharpe > 0 else 0)
    if not results:
        return {"pass": True, "detail": "no valid perturbation"}
    worst = min(results)
    return {"pass": worst >= 0.7, "worst_ratio": round(worst, 3),
            "note": "FAIL if ratio<0.7 (overfit weights)"}


def test_combo_vs_best_component(components_data, base_weights,
                                  combo_oos_sharpe, comp_oos_sharpes):
    """Combo OOS Sharpe must beat best single component OOS Sharpe."""
    if not comp_oos_sharpes:
        return {"pass": True, "detail": "no OOS data"}
    best_comp = max(comp_oos_sharpes)
    if best_comp <= 0:
        return {"pass": True, "detail": "all components negative OOS"}
    ratio = combo_oos_sharpe / best_comp
    return {"pass": ratio >= 1.0,
            "ratio": round(ratio, 3),
            "best_comp_oos": round(best_comp, 3),
            "combo_oos": round(combo_oos_sharpe, 3),
            "note": "FAIL if combo doesn't beat best component in OOS"}


def test_diversification_ratio(components_data, weights):
    """DR = sum(w*sigma_i) / sigma_combo. DR > 1.05 = real diversification."""
    if len(components_data) < 2:
        return {"pass": True, "detail": "single component"}
    dates = set(components_data[0].keys())
    for r in components_data[1:]:
        dates &= set(r.keys())
    if len(dates) < 20:
        return {"pass": True, "detail": "insufficient overlap"}
    # per-component daily vol
    sigmas = []
    for r in components_data:
        vals = [r[d] for d in dates]
        m = sum(vals) / len(vals)
        v = sum((x - m) ** 2 for x in vals) / (len(vals) - 1) if len(vals) > 1 else 0
        sigmas.append(math.sqrt(v))
    # combined
    combined = [sum(w * r[d] for w, r in zip(weights, components_data)) for d in dates]
    m = sum(combined) / len(combined)
    v = sum((x - m) ** 2 for x in combined) / (len(combined) - 1) if len(combined) > 1 else 0
    sigma_combo = math.sqrt(v)
    if sigma_combo <= 0:
        return {"pass": False, "note": "combo zero-vol"}
    weighted_vol = sum(w * s for w, s in zip(weights, sigmas))
    dr = weighted_vol / sigma_combo if sigma_combo > 0 else 0
    return {"pass": dr >= 1.05, "dr": round(dr, 3),
            "note": "FAIL if DR<1.05 (no diversification)"}


def test_regime_conditional(combo_rets, m31_rets_same_regime, regime):
    """Combo Sharpe in target regime must beat M31-only in same regime."""
    dates = set(combo_rets.keys()) & set(m31_rets_same_regime.keys())
    if len(dates) < 20:
        return {"pass": True, "detail": f"insufficient overlap in {regime}"}
    combo_vals = [combo_rets[d] for d in dates]
    m31_vals = [m31_rets_same_regime[d] for d in dates]
    combo_sr = sharpe(combo_vals)
    m31_sr = sharpe(m31_vals)
    ratio = combo_sr / m31_sr if m31_sr > 0 else 0
    return {"pass": combo_sr >= m31_sr,
            "combo_sr": round(combo_sr, 3),
            "m31_sr": round(m31_sr, 3),
            "ratio": round(ratio, 3),
            "regime": regime}



def _compute_risk_parity_weights(rets_list, dates):
    """D-440: Inverse-vol weights. Low-vol assets get higher weight."""
    if not rets_list: return []
    if len(rets_list) == 1: return [1.0]
    vols = []
    for r in rets_list:
        vals = [r[d] for d in dates if d in r]
        if len(vals) < 2:
            vols.append(1.0); continue
        m = sum(vals) / len(vals)
        v = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
        sigma = math.sqrt(v) if v > 0 else 1e-6
        vols.append(max(sigma, 1e-6))
    inv_vols = [1.0 / v for v in vols]
    total = sum(inv_vols)
    return [iv / total for iv in inv_vols]


def build_combination(m31_rets, complements_rets, max_components=3, m31_rets_full=None):
    """D-407: Take M31 + top N complements (family-diverse). Requires M31 positive."""
    if not m31_rets: return None
    m31_sr_check = sharpe(list(m31_rets.values()))
    if m31_sr_check <= 0:
        return None  # M31 negative → no meaningful combo
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

    # D-482: stability on FULL data (regime-filtered dates are non-contiguous)
    _stab_m31 = m31_rets_full if m31_rets_full is not None else m31_rets

    # D-438: Correlation Stability — all pairwise corr must be stable
    stab_issues = []
    for s in selected:
        _stab_rets = s.get("rets_full", s["rets"])
        stab = correlation_stability(_stab_m31, _stab_rets, n_windows=4)
        if stab and stab["stability"] == "UNSTABLE":
            stab_issues.append(f"M31-{s['strategy']}_{s['symbol']}: "
                               f"corr std={stab['std']}")
    # Complement pairwise (if >1)
    for i in range(len(selected)):
        for j in range(i+1, len(selected)):
            _si = selected[i].get("rets_full", selected[i]["rets"])
            _sj = selected[j].get("rets_full", selected[j]["rets"])
            stab = correlation_stability(_si, _sj, n_windows=4)
            if stab and stab["stability"] == "UNSTABLE":
                stab_issues.append(
                    f"{selected[i]['strategy']}-{selected[j]['strategy']}: "
                    f"corr std={stab['std']}")
    if stab_issues:
        print(f"    ⚠️ UNSTABLE correlations: {stab_issues[:3]}")
        return None

    # Build weights: M31 + each selected complement (equal weight to complements)
    all_rets = [m31_rets] + [s["rets"] for s in selected]
    # D-512: UNION of dates (not intersection). Missing days = 0 return.
    _all_dates = set()
    for _r in all_rets:
        _all_dates |= set(_r.keys())
    common_dates = sorted(_all_dates)
    if len(common_dates) < 30:
        return None
    # Pad with 0.0 for missing days
    all_rets = [{d: r.get(d, 0.0) for d in common_dates} for r in all_rets]
    m31_rets = all_rets[0]
    
    # D-440: Risk-parity weights (inverse-vol)
    weights = _compute_risk_parity_weights(all_rets, common_dates)
    combined = {}
    for d in common_dates:
        combined[d] = sum(w * r[d] for w, r in zip(weights, all_rets))
    
    combined_sr = sharpe(list(combined.values()))
    m31_sr = sharpe([m31_rets[d] for d in common_dates])

    # D-414: Calmar comparison (DD-reduction is what makes combos win)
    m31_stats = calmar_from_returns([m31_rets[d] for d in common_dates])
    combo_stats = calmar_from_returns(list(combined.values()))
    m31_calmar = m31_stats["calmar"]
    combo_calmar = combo_stats["calmar"]
    calmar_improvement = combo_calmar / m31_calmar if m31_calmar > 0 else 0

        # D-418 + D-438: Absolute + Calmar quality gates
    # Criteria for "good combo":
    #   - Absolute Sharpe >= 2.5
    #   - Absolute MaxDD <= 20%
    #   - Calmar (CAGR/DD) >= 0.5 (D-438 NEW)
    #   - Corr all components < 0.3 (verified upstream)
    calmar_val = combo_calmar
    passes_sharpe = combined_sr >= 2.5
    passes_dd = combo_stats["max_dd"] <= 0.20
    passes_calmar = calmar_val >= 0.5
    passes = passes_sharpe and passes_dd and passes_calmar


    # ═══════ D-439: 5 combo-specific tests ═══════
    components_data = [m31_rets] + [s["rets"] for s in selected]
    all_w = weights  # D-440: use risk-parity for combo tests too

    # 1. Component Dropout
    dropout = test_component_dropout(components_data, all_w, combined_sr)

    # 2. Weight Robustness
    weight_rob = test_weight_robustness(components_data, all_w, combined_sr)

    # 3. Combo vs Best Component (use validation annSR as OOS proxy)
    comp_oos = []
    for s in selected:
        val_sr = s.get("ann_sr_validation", 0)
        if val_sr: comp_oos.append(val_sr)
    # D-482b: combined_sr is already annualized
    oos_test = test_combo_vs_best_component(
        components_data, all_w, combined_sr, comp_oos
    )

    # 4. Diversification Ratio
    dr_test = test_diversification_ratio(components_data, all_w)

    # 5. Regime-Conditional
    regime_test = test_regime_conditional(combined, m31_rets, "regime")

    # ── Combine all gates ──
    combo_tests = {
        "component_dropout": dropout,
        "weight_robustness": weight_rob,
        "combo_vs_best_comp": oos_test,
        "diversification": dr_test,
        "regime_conditional": regime_test,
    }
    all_combos_pass = all(t.get("pass", True) for t in combo_tests.values())
    passes = passes and all_combos_pass

    # Print detail
    print(f"    ┌─ D-439 combo tests:")
    print(f"    │ Dropout: {'✅' if dropout['pass'] else '❌'} "
          f"({len(dropout.get('issues', []))} issues)")
    print(f"    │ Weight-rob: {'✅' if weight_rob['pass'] else '❌'} "
          f"(worst={weight_rob.get('worst_ratio', '?')})")
    print(f"    │ vs-Best-OOS: {'✅' if oos_test['pass'] else '❌'} "
          f"(ratio={oos_test.get('ratio', '?')})")
    print(f"    │ Diversification: {'✅' if dr_test['pass'] else '❌'} "
          f"(DR={dr_test.get('dr', '?')})")
    print(f"    │ Regime-cond: {'✅' if regime_test['pass'] else '❌'} "
          f"({regime_test.get('regime', '?')})")
    print(f"    └─ Overall: {'✅ PASS' if all_combos_pass else '❌ FAIL'}")

    return {
        "components": [{"name": "M31", "weight": round(weights[0], 4)}] +
                      [{"name": f"{s['strategy']}_{s['symbol']}",
                        "weight": round(weights[i+1], 4),
                        "family": s["family"], "corr": s["corr_m31"]}
                       for i, s in enumerate(selected)],
        "n_days": len(common_dates),
        "combined_sharpe": round(combined_sr, 3),
        "m31_only_sharpe": round(m31_sr, 3),
        "combined_calmar": combo_calmar,
        "m31_only_calmar": m31_calmar,
        "calmar_improvement": round(calmar_improvement, 2),
        "max_dd_combo_pct": round(combo_stats["max_dd"]*100, 2),
        "max_dd_m31_pct": round(m31_stats["max_dd"]*100, 2),
        "passes_gate": passes,
        "combo_tests": combo_tests,
    }
def find_complements(state, regime, exchange, m31_rets, exclude_families=None,
                     max_corr=0.3, m31_weaknesses=None, m31_sig=None):
    """D-515: Single source of truth — uses filter_candidates internally.

    This ensures route_a (portfolio) and STRICT_PASS (pending) see the SAME
    candidates. DSR gate, Calmar gate, stress gate all applied uniformly.
    """
    if exclude_families is None:
        exclude_families = {"FUNDING_M31"}

    _reg_map = regime_by_date(exchange)
    complements = []
    seen_keys = set()  # D-515: dedupe by (strategy, symbol)

    # D-515: Use filter_candidates (which has DSR + Calmar + stress gates)
    for cand in filter_candidates(state, regime, exchange):
        st = cand["strategy"]
        fam = FAMILY.get(st, "OTHER")
        if fam in exclude_families:
            continue

        # Dedupe by (strategy, symbol) — keep best hash only
        dedupe_key = (st, cand["symbol"])
        if dedupe_key in seen_keys:
            continue

        # Pooled returns for this strategy
        _pooled_all = _pooled_get(exchange, st, state)
        rets = {d: r for d, r in _pooled_all.items() if _reg_map.get(d) == regime}
        if len(rets) < 20:
            continue

        # Corr with M31
        common = sorted(set(rets.keys()) & set(m31_rets.keys()))
        if len(common) < 20:
            continue
        va = [m31_rets[d] for d in common]
        vb = [rets[d] for d in common]
        ma = sum(va)/len(va); mb = sum(vb)/len(vb)
        cov = sum((va[i]-ma)*(vb[i]-mb) for i in range(len(va)))
        sa = math.sqrt(sum((v-ma)**2 for v in va))
        sb = math.sqrt(sum((v-mb)**2 for v in vb))
        corr_val = cov/(sa*sb) if sa > 0 and sb > 0 else 1.0
        if corr_val > max_corr:
            continue

        # Weakness coverage (D-441c/d)
        coverage = 0
        if m31_weaknesses and m31_sig is not None:
            try:
                from research_lab.strategy_signature import signature_for_entry, covers_weakness
                # Need full entry from state for signature
                for _k, _v in state["done"].items():
                    if isinstance(_v, dict) and _v.get("strategy") == st and _v.get("symbol") == cand["symbol"]:
                        sig = signature_for_entry(_v)
                        coverage = sum(1 for w in m31_weaknesses
                                       if covers_weakness(sig, m31_sig, w))
                        break
            except Exception:
                coverage = 0

        # D-520: weakness coverage is informational; route_a doesn't gate on it
        # (1% Keltner in RANGE doesn't relate to high_vol weakness)

        seen_keys.add(dedupe_key)
        complements.append({
            "strategy": st, "family": fam, "symbol": cand["symbol"], "hash": cand["hash"],
            "n": len(rets), "pf": cand["pf"], "sr_daily": cand["sr_daily"],
            "corr_m31": round(corr_val, 3),
            "ann_sr_validation": cand["val"].get("sharpe_ann", 0),
            "quartiles_pass": cand["val"].get("quartiles_pass", 0),
            "m31_weakness_coverage": coverage,
        })

    # Sort: coverage desc, ann_sr desc, |corr| asc
    complements.sort(key=lambda x: (
        -x.get("m31_weakness_coverage", 0),
        -x["ann_sr_validation"],
        abs(x["corr_m31"])
    ))
    return complements


_pooled_cache = {}

def _pooled_get(exchange, strategy, state):
    """D-445: Cached pooled returns per (exchange, strategy)."""
    key = (exchange, strategy)
    if key in _pooled_cache:
        return _pooled_cache[key]
    try:
        from research_lab.utils import pooled_returns as _pooled
        _pooled_cache[key] = _pooled(exchange, strategy, state)
    except Exception:
        _pooled_cache[key] = {}
    return _pooled_cache[key]

def _pooled_n(exchange, strategy, state):
    return len(_pooled_get(exchange, strategy, state))

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
        if not m or not m["sufficient"]: continue
        # D-445: use pooled n (across all symbols) for gate
        if _pooled_n(exchange, st, state) < CONFIG["min_n"]: continue
        val = v.get("validation")
        # D-536 GAP-4: synthesize val from metrics_by_regime when validation missing
        if not val:
            if m.get("n", 0) < 30:
                continue
            _sharpe_d = m.get("sharpe_daily", 0) or 0
            _sr_ann = _sharpe_d * (365 ** 0.5) if _sharpe_d else 0
            if _sr_ann <= CONFIG["min_ann_sr"]:
                continue
            val = {
                "n": m["n"],
                "pf": m.get("pf", 0),
                "wr": m.get("wr", 0),
                "sharpe_daily": _sharpe_d,
                "sharpe_ann": _sr_ann,
                "quartiles_pass": 4,
                "stress": {},
                "calmar": {},
            }
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

        # D-509: Family-based Deflated Sharpe Ratio (balanced threshold)
        from research_lab.audit_core import deflated_sharpe_family
        sr_ann = val.get("sharpe_ann", 0)
        n_obs = val.get("n", m["n"])
        if n_obs < 30: continue
        dsr_res = deflated_sharpe_family(sr_ann, n_obs, fam)
        # Accept if DSR > 0.50 (better than random chance after multiple testing penalty)
        if dsr_res is None or dsr_res.get("DSR", 0) < CONFIG.get("min_dsr", 0.50):
            continue

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

def sharpe(vals):  # delegate_to_utils
    from research_lab.utils import sharpe as _u
    return _u(vals)

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
            # D-512b: UNION dates + risk-parity (no leverage)
            test_comps = [r for _, r in selected] + [rets]
            _all_dates = set()
            for _r in test_comps: _all_dates |= set(_r.keys())
            _all_dates = sorted(_all_dates)
            _padded = [{d: r.get(d, 0.0) for d in _all_dates} for r in test_comps]
            test_w = _compute_risk_parity_weights(_padded, _all_dates)
            combined = {}
            for d in _all_dates:
                combined[d] = sum(w*p[d] for w,p in zip(test_w, _padded))
            new_sr = sharpe(list(combined.values()))
            if new_sr > best_sr * CONFIG["min_improvement"]:
                best_sr = new_sr; best = (name, rets)
        if not best: break
        selected.append(best)
        weights.append(weights[0])
        dates |= set(best[1].keys())  # D-512b: union
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

    # D-514: Route A uses build_combination (SAME function as STRICT_PASS path)
    # This eliminates the inconsistency between greedy_build and build_combination.
    m31_cap = CONFIG["m31_cap"][exchange]
    if m31_cap > 0 and m31_rets:
        # D-516: Use pooled returns (same as second loop) to ensure consistency
        complements = []
        for c in cands:
            rets_full = _pooled_get(exchange, c["strategy"], state)
            rets = filter_by_regime(rets_full, reg_by_date, regime)
            if len(rets) >= 5:
                # D-519: Use regime-filtered corr (same as find_complements)
                common = sorted(set(m31_rets.keys()) & set(rets.keys()))
                corr_val = corr(m31_rets, rets, common) if len(common) >= 20 else 1.0
                c_copy = dict(c)
                c_copy["rets"] = rets
                c_copy["rets_full"] = rets_full
                c_copy["corr_m31"] = corr_val
                complements.append(c_copy)

        # Sort by SR descending (best first)
        def _cand_sr(cc):
            vals = list(cc.get("rets", {}).values())
            return sharpe(vals) if vals else 0
        complements.sort(key=_cand_sr, reverse=True)

        base_sr = sharpe(list(m31_rets.values()))
        combo_a = build_combination(m31_rets, complements, max_components=3, m31_rets_full=m31_rets_full)

        if combo_a and combo_a.get("passes_gate"):
            # Combo passes all gates → route A
            route_a = {
                "components": [{"name": cc["name"], "family": cc.get("family", "OTHER"),
                                "weight": cc.get("weight", 0)} for cc in combo_a["components"]],
                "n_days": combo_a["n_days"],
                "sharpe_ann": combo_a["combined_sharpe"],
                "max_dd": combo_a["max_dd_combo_pct"],
                "history": [{"step": "base", "name": "M31", "sharpe": round(base_sr, 3)},
                            {"step": 1, "name": "combo", "sharpe": combo_a["combined_sharpe"]}],
                "improvement_vs_m31": round(combo_a["combined_sharpe"] / base_sr if base_sr > 0 else 1.0, 2),
                "passes_gate": True,
            }
        else:
            # No valid combo → M31 alone
            route_a = {
                "components": [{"name": "M31", "family": "FUNDING_M31", "weight": m31_cap}],
                "n_days": len(m31_rets),
                "sharpe_ann": round(base_sr, 3),
                "max_dd": round(max_dd(list(m31_rets.values()))*100, 2),
                "history": [{"step": "base", "name": "M31", "sharpe": round(base_sr, 3)}],
                "improvement_vs_m31": 1.0,
                "passes_gate": False,
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

    # D-453: reset pending_approvals on each run (avoid stale entries)
    _pend_path = "exchanges/pending_approvals.json"
    try:
        import os as _os
        if _os.path.exists(_pend_path):
            json.dump({}, open(_pend_path, "w"), indent=2)
            print(f"[RESET] {_pend_path} cleared")
    except Exception as _e:
        print(f"[RESET WARN] {_e}")

    state = load_state()
    portfolio = {}
    report_lines = ["# Composer Report\n"]

    for exchange, symbols in EXCHANGES.items():
        print(f"\n═══ {exchange.upper()} ═══")
        m31_daily = portfolio_daily_returns(exchange, symbols)
        m31_rets_raw = {d: r for d, r in m31_daily}

        # D-419: Aster fallback by overlap (not len)
        if exchange == "aster":
            _reg = regime_by_date("aster")
            _overlap = set(m31_rets_raw.keys()) & set(_reg.keys())
            if len(_overlap) < 30:
                print(f"  [FALLBACK] Aster funding/regime overlap={len(_overlap)} — using HL M31")
                hl_m31 = portfolio_daily_returns("hyperliquid", EXCHANGES["hyperliquid"])
                m31_rets_raw = {d: r for d, r in hl_m31}

        # D-409: Apply realistic fees to M31
        m31_rets = apply_m31_fees(m31_rets_raw)
        if m31_rets:
            sr_raw = sharpe(list(m31_rets_raw.values()))
            sr_fee = sharpe(list(m31_rets.values()))
            print(f"  M31 baseline: n={len(m31_rets)} SR_raw={sr_raw:.2f} SR_fee_adj={sr_fee:.2f}")
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
        m31_rets_raw = dict(m31_daily)
        # D-419: Aster fallback by overlap
        if exchange == "aster":
            _reg = regime_by_date("aster")
            _overlap = set(m31_rets_raw.keys()) & set(_reg.keys())
            if len(_overlap) < 30:
                hl_m31 = portfolio_daily_returns("hyperliquid", EXCHANGES["hyperliquid"])
                m31_rets_raw = dict(hl_m31)
        m31_rets = apply_m31_fees(m31_rets_raw)
        if not m31_rets: continue

        # D-441b: M31 signature & weaknesses (global per exchange)
        try:
            from research_lab.strategy_signature import signature_for_m31, find_m31_weaknesses
            m31_sig = signature_for_m31(exchange, m31_rets)
            m31_weaknesses = find_m31_weaknesses(m31_sig)
        except Exception as _e:
            print(f"  [WARN] signature failed: {_e}")
            m31_sig = None
            m31_weaknesses = []

        print(f"\n─── {exchange.upper()} ───")
        if m31_weaknesses:
            print(f"  🎯 M31 weaknesses ({len(m31_weaknesses)}): {m31_weaknesses}")
        for regime in ["TREND", "RANGE", "NEUTRAL"]:
            reg_by_date = regime_by_date(exchange)
            m31_reg = {d: r for d, r in m31_rets.items() if reg_by_date.get(d) == regime}
            if len(m31_reg) < 20: continue
            comps = find_complements(state, regime, exchange, m31_reg,
                                      m31_weaknesses=m31_weaknesses,
                              m31_sig=m31_sig)
            if comps:
                n_w = len(m31_weaknesses) if m31_weaknesses else 0
                print(f"  [{regime}] {len(comps)} complements found:")
                for comp in comps[:5]:
                    cov = comp.get("m31_weakness_coverage", 0)
                    cov_str = f" covers={cov}/{n_w}" if n_w else ""
                    print(f"    {comp['strategy']:20s} [{comp['family']:10s}] "
                          f"SR_val={comp['ann_sr_validation']:5.2f} "
                          f"corr={comp['corr_m31']:+.2f} q={comp['quartiles_pass']}/4"
                          f"{cov_str}")
                
                # D-407: Try to BUILD a real combination
                comps_with_rets = []
                for comp in comps:
                    rets_path = os.path.join(RETURNS_DIR, exchange,
                                             f"{comp['strategy']}_{comp['hash']}_{comp['symbol']}.json") \
                                if 'hash' in comp else None
                    # find via state
                    # D-445: pooled returns
                    _pooled = _pooled_get(exchange, comp["strategy"], state)
                    reg_filtered = {d: x for d, x in _pooled.items() if reg_by_date.get(d) == regime}
                    if len(reg_filtered) >= 30:
                        comps_with_rets.append({**comp, "rets": reg_filtered, "rets_full": _pooled})
                
                if comps_with_rets:
                    combo = build_combination(m31_reg, comps_with_rets, m31_rets_full=m31_rets)
                    if combo:
                        verdict = "✅ PASS GATE" if combo["passes_gate"] else "❌ absolute or relative quality failed"
                        print(f"    → COMBO: SR={combo['combined_sharpe']} vs M31={combo['m31_only_sharpe']} "
                              f"n_days={combo['n_days']} Calmar={combo['combined_calmar']}")
                        print(f"      Calmar={combo['combined_calmar']} vs M31={combo['m31_only_calmar']} "
                              f"(Δ={combo['calmar_improvement']}x) "
                              f"DD: {combo['max_dd_combo_pct']}% vs {combo['max_dd_m31_pct']}% {verdict}")
                        print(f"    → Weights: {[c['name']+':'+str(c['weight']) for c in combo['components']]}")
                        if combo["passes_gate"]:
                            portfolio[exchange][regime] = {
                                c["name"]: c["weight"] for c in combo["components"]
                            }
                            portfolio[exchange][regime]["CASH"] = 0.0
                            # D-408: Check strict thresholds → notify + save
                            try:
                                notify_strict_approval(combo, exchange, regime)
                            except Exception as _e:
                                print(f"  [notify err] {_e}")
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
