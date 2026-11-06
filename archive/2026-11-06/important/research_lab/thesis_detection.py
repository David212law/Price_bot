"""D-526: Thesis Detection — automatic economic-thesis evidence gathering.

For each strategy, collects 5 independent pieces of evidence:
  1. Correlation with known edges (M31, Keltner)
  2. Regime-dependent SR pattern
  3. Vol-dependent SR pattern
  4. Crisis behavior (2024-12-23, 2025-03-15)
  5. Correlation with funding / BTC momentum

Output: per-strategy "thesis signature" for human review.
NOT a decision — evidence for judgment.
"""
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

CRISIS_DATES = [
    "2024-12-23",  # funding flip
    "2025-03-15",  # volatility spike
    "2025-08-05",  # liquidation cascade
]

def load_returns(exchange, strategy, hash_val, symbol):
    p = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}/{strategy}_{hash_val}_{symbol}.json")
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except: return {}

def sharpe(vals):  # delegate_to_utils
    from research_lab.utils import sharpe as _u
    return _u(vals)

def corr(a, b, dates):
    if len(dates) < 10: return 0.0
    va = [a.get(d, 0.0) for d in dates]
    vb = [b.get(d, 0.0) for d in dates]
    ma = sum(va) / len(va); mb = sum(vb) / len(vb)
    cov = sum((va[i] - ma) * (vb[i] - mb) for i in range(len(va)))
    sa = sum((x - ma) ** 2 for x in va) ** 0.5
    sb = sum((x - mb) ** 2 for x in vb) ** 0.5
    return round(cov / (sa * sb), 3) if sa * sb > 0 else 0.0

def load_context():
    """Load M31 plain, Keltner, BTC daily, regime map."""
    from research_lab.composer import load_state, regime_by_date, portfolio_daily_returns, apply_m31_fees
    from strategies.core_engine import load_data

    state = load_state()
    m31_rets = apply_m31_fees(dict(portfolio_daily_returns("hyperliquid", ["BTC","ETH","SOL","BNB","XRP","AVAX"])))
    regime_map = regime_by_date("hyperliquid")

    # BTC daily returns
    btc = load_data("hyperliquid", "BTC")
    prices = defaultdict(list)
    for c in btc:
        if not isinstance(c, dict): continue
        t, close = c.get("t"), c.get("c")
        if t and close:
            day = datetime.fromtimestamp(int(t)/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[day].append(float(close))
    sorted_days = sorted(prices.keys())
    btc_daily = {}
    for i in range(1, len(sorted_days)):
        p = prices[sorted_days[i-1]][-1]
        c = prices[sorted_days[i]][-1]
        if p > 0: btc_daily[sorted_days[i]] = (c - p) / p

    # Keltner baseline (from state)
    keltner_rets = {}
    for k, v in state.get("done", {}).items():
        if isinstance(v, dict) and v.get("strategy") == "KELTNER_REV":
            if v.get("exchange") == "hyperliquid" and v.get("symbol") == "ETH":
                val = v.get("validation", {})
                if val and val.get("sharpe_ann", 0) > 4:
                    try: h = k.split(":")[2]
                    except: continue
                    keltner_rets = load_returns("hyperliquid", "KELTNER_REV", h, "ETH")
                    break

    return m31_rets, keltner_rets, btc_daily, regime_map

def gather_evidence(strategy_rets, m31_rets, keltner_rets, btc_daily, regime_map):
    """Collect 5 pieces of evidence."""
    dates = sorted(strategy_rets.keys())
    ev = {}

    # Evidence 1 — corr with known edges
    common_m31 = sorted(set(dates) & set(m31_rets.keys()))
    ev["corr_m31"] = corr(strategy_rets, m31_rets, common_m31) if len(common_m31) >= 20 else None

    common_kelt = sorted(set(dates) & set(keltner_rets.keys()))
    ev["corr_keltner"] = corr(strategy_rets, keltner_rets, common_kelt) if len(common_kelt) >= 20 else None

    # Evidence 2 — regime pattern
    regime_sr = {}
    for reg in ["TREND", "RANGE", "NEUTRAL"]:
        sub = [strategy_rets[d] for d in dates if regime_map.get(d) == reg]
        if len(sub) >= 10:
            regime_sr[reg] = round(sharpe(sub), 2)
    ev["regime_sr"] = regime_sr

    # Evidence 3 — vol pattern
    abs_btc = sorted(abs(v) for v in btc_daily.values())
    threshold = abs_btc[len(abs_btc)//2] * 1.5 if abs_btc else 0
    low_vol = [strategy_rets[d] for d in dates if abs(btc_daily.get(d, 0)) <= threshold]
    high_vol = [strategy_rets[d] for d in dates if abs(btc_daily.get(d, 0)) > threshold]
    ev["vol_sr"] = {
        "low": round(sharpe(low_vol), 2) if len(low_vol) >= 10 else None,
        "high": round(sharpe(high_vol), 2) if len(high_vol) >= 10 else None,
    }

    # Evidence 4 — crisis behavior
    crisis_sr = {}
    for c_date in CRISIS_DATES:
        # ±5 days window
        c_dt = datetime.strptime(c_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        window = [(c_dt + timedelta(days=k)).strftime("%Y-%m-%d") for k in range(-5, 6)]
        vals = [strategy_rets[d] for d in window if d in strategy_rets]
        if vals:
            crisis_sr[c_date] = round(sum(vals) * 100, 3)
    ev["crisis_pct"] = crisis_sr

    # Evidence 5 — corr with funding / BTC momentum
    # corr with BTC daily (directional)
    common_btc = sorted(set(dates) & set(btc_daily.keys()))
    ev["corr_btc"] = corr(strategy_rets, btc_daily, common_btc) if len(common_btc) >= 20 else None

    return ev

def interpret(ev, baseline_sr):
    """Turn 5 evidences into a 'thesis hint' (not a decision)."""
    hints = []

    # Independent from known edges?
    c_m31 = ev.get("corr_m31")
    c_kelt = ev.get("corr_keltner")
    if c_m31 is not None and abs(c_m31) < 0.3 and (c_kelt is None or abs(c_kelt) < 0.4):
        hints.append("INDEPENDENT")
    if c_m31 is not None and abs(c_m31) > 0.7:
        hints.append("M31_CLONE")
    if c_kelt is not None and abs(c_kelt) > 0.5:
        hints.append("KELTNER_CLONE")

    # Regime pattern
    rsr = ev.get("regime_sr", {})
    if rsr:
        t = rsr.get("TREND", 0); r = rsr.get("RANGE", 0); n = rsr.get("NEUTRAL", 0)
        if t > max(r, n) * 1.5 and t > 1.0:
            hints.append("TREND_FOLLOWING")
        elif r > max(t, n) * 1.5 and r > 1.0:
            hints.append("MEAN_REVERSION")
        elif all(abs(x) > 0.5 for x in [t, r, n]):
            hints.append("REGIME_AGNOSTIC")

    # Vol pattern
    vsr = ev.get("vol_sr", {})
    if vsr.get("low") is not None and vsr.get("high") is not None:
        if vsr["low"] > vsr["high"] * 1.5:
            hints.append("CALM_MARKET")
        elif vsr["high"] > vsr["low"] * 1.5:
            hints.append("VOLATILITY_THESIS")

    # Crisis behavior
    crisis = ev.get("crisis_pct", {})
    if crisis:
        all_positive = all(v > 0 for v in crisis.values())
        any_negative = any(v < -0.5 for v in crisis.values())
        if all_positive:
            hints.append("CRISIS_ROBUST")
        elif any_negative:
            hints.append("CRISIS_FRAGILE")

    # Directional or not?
    c_btc = ev.get("corr_btc")
    if c_btc is not None:
        if abs(c_btc) > 0.5:
            hints.append("DIRECTIONAL")
        elif abs(c_btc) < 0.2:
            hints.append("MARKET_NEUTRAL")

    if not hints:
        hints.append("THESIS_UNCLEAR")

    # Combine
    primary = hints[0] if hints else "UNCLEAR"
    return {"hints": hints, "primary": primary}

def main():
    print("=" * 78)
    print(" Thesis Detection — D-526")
    print("=" * 78)

    m31_rets, keltner_rets, btc_daily, regime_map = load_context()
    print(f"[PREP] M31={len(m31_rets)}d, Keltner={len(keltner_rets)}d, BTC={len(btc_daily)}d\n")

    # Scan all entries
    state = json.loads(Path("research_lab/logs/profiles/state.json").read_text())
    done = state.get("done", {})

    results = []
    seen = set()
    for key, v in done.items():
        if not isinstance(v, dict): continue
        val = v.get("validation")
        if not val or val.get("sharpe_ann", 0) < 1.5: continue
        if val.get("quartiles_pass", 0) < 3: continue
        st = v.get("strategy", "")
        exch = v.get("exchange", "")
        sym = v.get("symbol", "")
        try: h = key.split(":")[2]
        except: continue
        dedupe_key = (st, h, sym, exch)
        if dedupe_key in seen: continue
        seen.add(dedupe_key)

        rets = load_returns(exch, st, h, sym)
        if len(rets) < 60: continue

        ev = gather_evidence(rets, m31_rets, keltner_rets, btc_daily, regime_map)
        interp = interpret(ev, val.get("sharpe_ann", 0))

        results.append({
            "strategy": st, "symbol": sym, "exchange": exch, "hash": h,
            "baseline_sr": round(val.get("sharpe_ann", 0), 2),
            "evidence": ev,
            "interpretation": interp,
        })

    # Sort by primary hint, then by SR
    results.sort(key=lambda x: (x["interpretation"]["primary"], -x["baseline_sr"]))

    print(f"[ANALYZED] {len(results)} strategies with sufficient data\n")

    # Group by primary hint
    by_hint = defaultdict(list)
    for r in results:
        by_hint[r["interpretation"]["primary"]].append(r)

    print("=" * 78)
    print(" BY THESIS HINT")
    print("=" * 78)
    for hint, rs in sorted(by_hint.items(), key=lambda x: -len(x[1])):
        print(f"\n{hint} ({len(rs)} strategies):")
        for r in rs[:5]:
            print(f"  {r['strategy']:25s} {r['exchange']:10s} {r['symbol']:10s} SR={r['baseline_sr']:5.2f}")
            print(f"    corr_m31={r['evidence'].get('corr_m31')} "
                  f"corr_btc={r['evidence'].get('corr_btc')} "
                  f"regime={r['evidence'].get('regime_sr')}")

    # Save
    out = Path("research_lab/logs/thesis_evidence.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "5-evidence thesis detection for human judgment",
        "n_analyzed": len(results),
        "by_hint": {h: len(rs) for h, rs in by_hint.items()},
        "results": results,
    }, indent=2))
    print(f"\n[SAVE] {out}")
    print(f"\n{'='*78}")
    print(f" Total: {len(results)} strategies analyzed")
    print(f" Hint distribution: {dict(by_hint)}")
    print(f"{'='*78}")

if __name__ == "__main__":
    main()
