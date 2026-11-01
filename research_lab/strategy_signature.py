"""D-441: Strategy Signature — comprehensive profile for each strategy.
Extracts best regime, vol bias, tail behavior, skew, etc."""
import os, json, math
from collections import defaultdict
from datetime import datetime, timezone

RETURNS_DIR = "research_lab/logs/profiles/returns_matrices"

_vol_cache = {}

def market_vol_by_date(exchange):
    """Classify each day as 'low'/'high' vol based on BTC daily returns."""
    if exchange in _vol_cache:
        return _vol_cache[exchange]
    from strategies.core_engine import load_data
    btc_sym = {"hyperliquid": "BTC", "aster": "BTCUSDT", "kucoin": "XBTUSDTM"}.get(exchange)
    btc = load_data(exchange, btc_sym) if btc_sym else None
    if not btc or len(btc) < 100:
        _vol_cache[exchange] = {}
        return {}

    daily = defaultdict(list)
    for i in range(1, len(btc)):
        ret = btc[i]["c"] / btc[i-1]["c"] - 1
        day = datetime.fromtimestamp(btc[i]["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        daily[day].append(ret)
    daily_avg = {d: sum(v)/len(v) for d, v in daily.items()}
    days = sorted(daily_avg.keys())

    vol_by_date = {}
    window = 20
    vols = []
    for i in range(window, len(days)):
        recent = [daily_avg[days[j]] for j in range(i-window, i)]
        m = sum(recent) / len(recent)
        v = sum((x-m)**2 for x in recent) / (len(recent)-1)
        sigma = math.sqrt(v) if v > 0 else 0
        vol_by_date[days[i]] = sigma
        vols.append(sigma)

    if not vols:
        _vol_cache[exchange] = {}
        return {}
    median_vol = sorted(vols)[len(vols)//2]

    result = {d: ("high" if s > median_vol else "low") for d, s in vol_by_date.items()}
    _vol_cache[exchange] = result
    return result


def compute_signature(entry, returns_dict):
    """Compute strategy signature from profiler entry + returns."""
    sig = {
        "strategy": entry["strategy"],
        "symbol": entry["symbol"],
        "exchange": entry["exchange"],
        "n_total": entry.get("n_total", 0),
    }

    # Regime performance
    rm = entry.get("metrics_by_regime", {})
    sharpe_regime = {}
    for r in ["TREND", "RANGE", "NEUTRAL"]:
        m = rm.get(r, {})
        if m.get("sufficient"):
            # Accept either sharpe_ann or sharpe_daily (convert to ann)
            if "sharpe_ann" in m:
                sharpe_regime[r] = m["sharpe_ann"]
            else:
                sharpe_regime[r] = m.get("sharpe_daily", 0) * math.sqrt(365)
    sig["sharpe_by_regime"] = sharpe_regime
    if sharpe_regime:
        sig["best_regime"] = max(sharpe_regime, key=sharpe_regime.get)
        sig["worst_regime"] = min(sharpe_regime, key=sharpe_regime.get)
    else:
        sig["best_regime"] = "UNKNOWN"
        sig["worst_regime"] = "UNKNOWN"

    # Returns stats
    if returns_dict and len(returns_dict) >= 20:
        vals = list(returns_dict.values())
        m = sum(vals) / len(vals)
        v = sum((x-m)**2 for x in vals) / (len(vals)-1)
        std = math.sqrt(v) if v > 0 else 0
        sig["mean_daily"] = round(m, 6)
        sig["std_daily"] = round(std, 6)
        sig["sharpe_ann"] = round((m/std * math.sqrt(365)) if std > 0 else 0, 3)

        sorted_vals = sorted(vals)
        worst_idx = max(0, int(len(vals) * 0.05))
        best_idx = min(len(vals)-1, int(len(vals) * 0.95))
        sig["worst_5pct_day"] = round(sorted_vals[worst_idx], 6)
        sig["best_5pct_day"] = round(sorted_vals[best_idx], 6)

        if std > 0:
            skew = sum((x-m)**3 for x in vals) / (len(vals) * std**3)
            sig["skew"] = round(skew, 3)
        else:
            sig["skew"] = 0

        # Vol conditional
        vol_regime = market_vol_by_date(entry["exchange"])
        low_vol_rets = [r for d, r in returns_dict.items() if vol_regime.get(d) == "low"]
        high_vol_rets = [r for d, r in returns_dict.items() if vol_regime.get(d) == "high"]

        def _sharpe_arr(arr):
            if len(arr) < 10: return None
            mu = sum(arr) / len(arr)
            var = sum((x-mu)**2 for x in arr) / (len(arr)-1)
            s = math.sqrt(var) if var > 0 else 0
            return round(mu/s * math.sqrt(365), 3) if s > 0 else 0

        sig["sharpe_low_vol"] = _sharpe_arr(low_vol_rets)
        sig["sharpe_high_vol"] = _sharpe_arr(high_vol_rets)

        if sig["sharpe_low_vol"] is not None and sig["sharpe_high_vol"] is not None:
            sig["vol_bias"] = ("low_vol" if sig["sharpe_low_vol"] > sig["sharpe_high_vol"]
                               else "high_vol")

    return sig


def signature_for_entry(entry):
    """Load returns matrix and compute signature."""
    exchange = entry["exchange"]
    strategy = entry["strategy"]
    symbol = entry["symbol"]
    # find hash from key? — return matrix files are named strategy_hash_symbol
    # We'll iterate
    folder = os.path.join(RETURNS_DIR, exchange)
    if not os.path.isdir(folder):
        return compute_signature(entry, {})
    prefix = f"{strategy}_"
    suffix = f"_{symbol}.json"
    rets_path = None
    for f in os.listdir(folder):
        if f.startswith(prefix) and f.endswith(suffix):
            rets_path = os.path.join(folder, f)
            break
    if not rets_path:
        return compute_signature(entry, {})
    try:
        rets = json.load(open(rets_path))
        return compute_signature(entry, rets)
    except Exception:
        return compute_signature(entry, {})


def signature_for_m31(exchange, m31_rets):
    """D-441b: M31 signature with regime-conditional sharpe computed."""
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.getcwd())
    from research_lab.composer import regime_by_date

    # Compute sharpe per regime
    reg_map = regime_by_date(exchange)
    by_regime = {"TREND": [], "RANGE": [], "NEUTRAL": []}
    for d, r in m31_rets.items():
        reg = reg_map.get(d)
        if reg in by_regime:
            by_regime[reg].append(r)

    metrics_by_regime = {}
    for reg, rets in by_regime.items():
        if len(rets) >= 10:
            m = sum(rets) / len(rets)
            v = sum((x-m)**2 for x in rets) / (len(rets)-1)
            s = math.sqrt(v) if v > 0 else 0
            sharpe_ann = (m/s) * math.sqrt(365) if s > 0 else 0
            wins = sum(1 for x in rets if x > 0)
            losses_sum = abs(sum(x for x in rets if x < 0))
            wins_sum = sum(x for x in rets if x > 0)
            pf = wins_sum / losses_sum if losses_sum > 0 else 99.99
            metrics_by_regime[reg] = {
                "n": len(rets),
                "pf": round(pf, 2),
                "wr": round(wins/len(rets)*100, 1),
                "mean_pct": round(m*100, 4),
                "sharpe_ann": round(sharpe_ann, 3),  # annualized
                "sufficient": True,
            }

    entry = {
        "strategy": "M31",
        "symbol": "ALL",
        "exchange": exchange,
        "n_total": len(m31_rets),
        "metrics_by_regime": metrics_by_regime,
    }
    return compute_signature(entry, m31_rets)


def find_m31_weaknesses(m31_sig):
    """D-441c: All thresholds are ANNUALIZED. Weak = Sharpe<2. Underperform = <50% of best."""
    weaknesses = []

    # Regime: absolute weak (ann sharpe < 2)
    for r, sr in m31_sig.get("sharpe_by_regime", {}).items():
        if sr < 2.0:
            weaknesses.append(f"weak_in_{r}")

    # Regime: relative underperform (< 50% of best)
    regime_sh = m31_sig.get("sharpe_by_regime", {})
    if regime_sh:
        best = max(regime_sh.values())
        for r, sr in regime_sh.items():
            if sr < 0.5 * best and sr >= 2.0:  # not double-flag
                weaknesses.append(f"underperform_in_{r}")

    # Vol: absolute
    low_sr = m31_sig.get("sharpe_low_vol")
    high_sr = m31_sig.get("sharpe_high_vol")
    if low_sr is not None and high_sr is not None:
        if low_sr < 2.0: weaknesses.append("weak_in_low_vol")
        if high_sr < 2.0: weaknesses.append("weak_in_high_vol")
        if low_sr < 0.5 * high_sr and low_sr >= 2.0:
            weaknesses.append("underperform_in_low_vol")
        if high_sr < 0.5 * low_sr and high_sr >= 2.0:
            weaknesses.append("underperform_in_high_vol")

    return weaknesses


def covers_weakness(candidate_sig, m31_sig, weakness):
    """D-441c: Candidate must BEAT M31 in the weak condition, not just be >2.0.
    Keltner high_vol=6.50 vs M31 high_vol=8.01 → does NOT cover."""
    floor = 2.0  # must be decent in absolute terms too

    if "low_vol" in weakness:
        c = candidate_sig.get("sharpe_low_vol")
        m = m31_sig.get("sharpe_low_vol")
        if c is None or m is None: return False
        return c > m and c > floor
    if "high_vol" in weakness:
        c = candidate_sig.get("sharpe_high_vol")
        m = m31_sig.get("sharpe_high_vol")
        if c is None or m is None: return False
        return c > m and c > floor
    if weakness.startswith(("weak_in_", "underperform_in_")):
        regime = weakness.replace("weak_in_", "").replace("underperform_in_", "")
        c = candidate_sig.get("sharpe_by_regime", {}).get(regime)
        m = m31_sig.get("sharpe_by_regime", {}).get(regime)
        if c is None or m is None: return False
        return c > m and c > floor
    return False
