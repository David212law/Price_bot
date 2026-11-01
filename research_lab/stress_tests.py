"""D-404: Stress tests — Fee 2x, Slippage 1.5x, Parameter Robustness.
Used by composer to reject fragile candidates before portfolio inclusion.
"""
import sys, os, math
from collections import defaultdict
sys.path.insert(0, os.getcwd())

from strategies.library.registry import get_strategy
from strategies.core_engine import load_data
from research_lab.audit_core import load_funding

def _sharpe_ann(rets):
    n = len(rets)
    if n < 20: return 0
    m = sum(rets)/n
    v = sum((r-m)**2 for r in rets)/(n-1)
    s = math.sqrt(v)
    return (m/s)*math.sqrt(365) if s > 0 else 0

def _pfs(rets):
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    pf = sum(wins)/abs(sum(losses)) if losses else (99.99 if wins else 0)
    return round(pf, 3), len(rets)

def _load_candles(ex, sym):
    return load_data(ex, sym) or []

def _run_candle(func, params, candles, fee_mult=1.0):
    if not candles or len(candles) < 200: return []
    p = dict(params); p["fee_multiplier"] = fee_mult
    try: return func(candles, **p) or []
    except: return []

# ═══════ ۱. Fee Stress 2x ═══════
def fee_stress(name, params, exchange, symbols, fee_mult=2.0):
    """Re-run with fee ×2. If Sharpe drops >60% → fragile."""
    func, _, kind = get_strategy(name)
    if kind != "candle":
        return {"skip": "funding-based (fee already in returns)"}
    all_rets = []
    for sym in symbols:
        cd = _load_candles(exchange, sym)
        trades = _run_candle(func, params, cd, fee_mult=fee_mult)
        all_rets.extend([t["ret"] for t in trades])
    if len(all_rets) < 20:
        return {"skip": f"n={len(all_rets)}<20"}
    pf, n = _pfs(all_rets)
    sr = _sharpe_ann(all_rets)
    return {"fee_mult": fee_mult, "n": n, "pf": pf, "sharpe_ann": round(sr, 3)}

# ═══════ ۲. Slippage 1.5x ═══════
def slippage_stress(name, params, exchange, symbols, slip_pct=0.0015):
    """Subtract 2*slip_pct per trade (entry+exit). Realistic for 4h bars."""
    func, _, kind = get_strategy(name)
    if kind != "candle":
        return {"skip": "funding-based"}
    all_rets = []
    for sym in symbols:
        cd = _load_candles(exchange, sym)
        trades = _run_candle(func, params, cd, fee_mult=1.0)
        all_rets.extend([t["ret"] - 2*slip_pct for t in trades])
    if len(all_rets) < 20:
        return {"skip": f"n={len(all_rets)}<20"}
    pf, n = _pfs(all_rets)
    sr = _sharpe_ann(all_rets)
    return {"slip_pct": slip_pct*100, "n": n, "pf": pf, "sharpe_ann": round(sr, 3)}

# ═══════ ۳. Parameter Robustness ±۱۰٪ ═══════
def param_robustness(name, params, exchange, symbols, baseline_sharpe, delta=0.10):
    """Vary numeric params ±10%. If best variant Sharpe < baseline×0.7 → overfit."""
    func, _, kind = get_strategy(name)
    numeric = {k: v for k, v in params.items() if isinstance(v, (int, float))}
    if not numeric:
        return {"skip": "no numeric params"}
    results = []
    for key, val in numeric.items():
        for mult in (1-delta, 1+delta):
            new_val = int(val*mult) if isinstance(val, int) else round(val*mult, 2)
            if new_val <= 0: continue
            test_params = dict(params); test_params[key] = new_val
            all_rets = []
            for sym in symbols:
                cd = _load_candles(exchange, sym)
                trades = _run_candle(func, test_params, cd)
                all_rets.extend([t["ret"] for t in trades])
            if len(all_rets) >= 20:
                sr = _sharpe_ann(all_rets)
                results.append({"param": key, "val": new_val, "sharpe_ann": round(sr, 3)})
    if not results:
        return {"skip": "no valid variants"}
    best_sharpe = max(r["sharpe_ann"] for r in results)
    ratio = best_sharpe / baseline_sharpe if baseline_sharpe > 0 else 0
    return {"baseline_sharpe": round(baseline_sharpe, 3),
            "best_variant_sharpe": best_sharpe,
            "ratio": round(ratio, 3),
            "verdict": "ROBUST" if ratio >= 0.7 else "FRAGILE",
            "variants": results}

# ═══════ Main ═══════
def run_all(name, params, exchange, symbols, baseline_sharpe_ann):
    print(f"  [stress] {name} on {exchange}...")
    fee = fee_stress(name, params, exchange, symbols)
    slip = slippage_stress(name, params, exchange, symbols)
    rob = param_robustness(name, params, exchange, symbols, baseline_sharpe_ann)
    return {"fee_2x": fee, "slippage_1.5x": slip, "param_robustness": rob}

if __name__ == "__main__":
    tests = [
        ("KELTNER_REV", {"period": 20, "mult": 2.0}, "aster", ["AVAXUSDT"], 5.5),
        ("KELTNER_REV", {"period": 20, "mult": 2.0}, "aster", ["ETHUSDT"], 5.5),
    ]
    for name, params, ex, syms, sr in tests:
        print(f"\n════ {name} {params} on {ex}/{syms[0]} ════")
        r = run_all(name, params, ex, syms, sr)
        print(f"  Fee 2x: PF={r['fee_2x'].get('pf','?')} SR={r['fee_2x'].get('sharpe_ann','?')}")
        print(f"  Slip 1.5x: PF={r['slippage_1.5x'].get('pf','?')} SR={r['slippage_1.5x'].get('sharpe_ann','?')}")
        print(f"  Param: {r['param_robustness'].get('verdict','?')} (ratio={r['param_robustness'].get('ratio','?')})")
