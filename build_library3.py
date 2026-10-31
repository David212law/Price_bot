"""Build final library files: volume, funding, structural, registry."""
import os

# ═══════════════════════════════════════
# volume.py — 4 (using candle v field)
# ═══════════════════════════════════════
open('strategies/library/volume.py', 'w').write('''"""Volume-based strategies (4)."""
from strategies.library.indicators import ema, sma, atr

def _trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}

def strat_obv(candles, period=20, fee_multiplier=1.0):
    if len(candles) < period + 10: return []
    obv = [0.0]
    for i in range(1, len(candles)):
        if candles[i]["c"] > candles[i-1]["c"]:
            obv.append(obv[-1] + candles[i].get("v", 1))
        elif candles[i]["c"] < candles[i-1]["c"]:
            obv.append(obv[-1] - candles[i].get("v", 1))
        else:
            obv.append(obv[-1])
    obv_ema = ema(obv, period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period + 1, len(candles)):
        if None in (obv_ema[i], obv_ema[i-1], at[i-1]): continue
        if not pos:
            if obv[i] > obv_ema[i] and obv[i-1] <= obv_ema[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1],"tp":candles[i]["c"]+6*at[i-1]}
            elif obv[i] < obv_ema[i] and obv[i-1] >= obv_ema[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+3*at[i-1],"tp":candles[i]["c"]-6*at[i-1]}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif candles[i]["h"]>=pos["tp"]: ex=pos["tp"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif candles[i]["l"]<=pos["tp"]: ex=pos["tp"]
            if ex:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_vwap(candles, period=20, deviation=0.01, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if at[i-1] is None: continue
        window = candles[i-period+1:i+1]
        total_v = sum(c.get("v", 1) for c in window)
        if total_v == 0: continue
        vwap = sum(((c["h"]+c["l"]+c["c"])/3) * c.get("v", 1) for c in window) / total_v
        if not pos:
            if candles[i]["c"] < vwap * (1 - deviation):
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":vwap}
            elif candles[i]["c"] > vwap * (1 + deviation):
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":vwap}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif candles[i]["h"]>=pos["tp"]: ex=pos["tp"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif candles[i]["l"]<=pos["tp"]: ex=pos["tp"]
            if ex:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_mfi(candles, period=14, low=20, high=80, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    tp = [(c["h"]+c["l"]+c["c"])/3 for c in candles]
    mf = [tp[i] * candles[i].get("v", 1) for i in range(len(candles))]
    mfi_vals = [None]*len(candles)
    for i in range(period, len(candles)):
        pos_mf = sum(mf[j] for j in range(i-period+1, i+1) if tp[j] > tp[j-1])
        neg_mf = sum(mf[j] for j in range(i-period+1, i+1) if tp[j] < tp[j-1])
        mfi_vals[i] = 100 - 100/(1 + pos_mf/neg_mf) if neg_mf > 0 else 100
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period+1, len(candles)):
        if None in (mfi_vals[i], mfi_vals[i-1], at[i-1]): continue
        if not pos:
            if mfi_vals[i-1] < low and mfi_vals[i] >= low:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+3*at[i-1]}
            elif mfi_vals[i-1] > high and mfi_vals[i] <= high:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":candles[i]["c"]-3*at[i-1]}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif candles[i]["h"]>=pos["tp"]: ex=pos["tp"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif candles[i]["l"]<=pos["tp"]: ex=pos["tp"]
            if ex:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_volume_breakout(candles, vol_period=20, mult=2.0, fee_multiplier=1.0):
    if len(candles) < vol_period + 5: return []
    vols = [c.get("v", 1) for c in candles]
    vma = sma(vols, vol_period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(vol_period+1, len(candles)):
        if None in (vma[i], vma[i-1], at[i-1]): continue
        high_vol = candles[i].get("v", 1) > mult * vma[i]
        if not pos and high_vol:
            body = candles[i]["c"] - candles[i]["o"]
            if body > 0:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1],"tp":candles[i]["c"]+5*at[i-1]}
            else:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+3*at[i-1],"tp":candles[i]["c"]-5*at[i-1]}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif candles[i]["h"]>=pos["tp"]: ex=pos["tp"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif candles[i]["l"]<=pos["tp"]: ex=pos["tp"]
            if ex:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

VOLUME_STRATEGIES = {
    "OBV": (strat_obv, {"period":[20,50]}),
    "VWAP": (strat_vwap, {"period":[20,50], "deviation":[0.005,0.01,0.02]}),
    "MFI": (strat_mfi, {"period":[14], "low":[15,20,25], "high":[75,80,85]}),
    "VOLUME_BREAKOUT": (strat_vol_breakout, {"vol_period":[20], "mult":[1.5,2.0,3.0]}),
}
''')
print("[6/8] volume.py (4)")

# ═══════════════════════════════════════
# funding.py — 5 M31 variants
# ═══════════════════════════════════════
open('strategies/library/funding.py', 'w').write('''"""Funding rate strategies (5 variants of M31)."""
import math

def _daily_returns(funding_records, entry_thr, exit_thr, cooldown_h=1, leverage=3):
    """Simulate M31 with given threshold. Returns list of daily returns."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > 12: hist.pop(0)
        avg = sum(hist) / len(hist)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            if avg < exit_thr:
                in_pos = False
                last_exit = r["t"]
            else:
                daily[day] += r["rate"] * leverage
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if avg > entry_thr and r["rate"] > 0 and hours_since >= cooldown_h:
                in_pos = True
    return dict(daily)

def m31_sma(funding_records, period=12, entry_thr=0.00001, exit_thr=0.000005, leverage=3):
    """M31 with SMA(period) entry/exit. Baseline variant."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > period: hist.pop(0)
        avg = sum(hist) / len(hist)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            if avg < exit_thr:
                in_pos = False
                last_exit = r["t"]
            else:
                daily[day] += r["rate"] * leverage
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if avg > entry_thr and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_ema(funding_records, period=12, entry_thr=0.00001, exit_thr=0.000005, leverage=3):
    """M31 with EMA entry/exit."""
    from datetime import datetime, timezone
    from collections import defaultdict
    if not funding_records: return {}
    k = 2.0 / (period + 1)
    ema_v = funding_records[0]["rate"]
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        ema_v = r["rate"] * k + ema_v * (1 - k)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            if ema_v < exit_thr:
                in_pos = False
                last_exit = r["t"]
            else:
                daily[day] += r["rate"] * leverage
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if ema_v > entry_thr and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_threshold(funding_records, entry_thr=0.00003, exit_thr=0.000005, leverage=3):
    """M31 with direct threshold (no smoothing)."""
    from datetime import datetime, timezone
    from collections import defaultdict
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            if r["rate"] < exit_thr:
                in_pos = False
                last_exit = r["t"]
            else:
                daily[day] += r["rate"] * leverage
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if r["rate"] > entry_thr and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_quantile(funding_records, window=50, quantile=0.7, leverage=3):
    """M31 with quantile-based threshold (dynamic)."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > window: hist.pop(0)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if len(hist) < window:
            continue
        sorted_h = sorted(hist)
        thr = sorted_h[int(len(sorted_h) * quantile)]
        if in_pos:
            if r["rate"] < 0:
                in_pos = False
                last_exit = r["t"]
            else:
                daily[day] += r["rate"] * leverage
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if r["rate"] > thr and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_momentum(funding_records, lookback=6, leverage=3):
    """M31 that enters when funding is trending up (recent > older)."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > lookback * 2: hist.pop(0)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if len(hist) < lookback * 2:
            continue
        recent_avg = sum(hist[-lookback:]) / lookback
        older_avg = sum(hist[:lookback]) / lookback
        if in_pos:
            if r["rate"] < 0:
                in_pos = False
                last_exit = r["t"]
            else:
                daily[day] += r["rate"] * leverage
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if recent_avg > older_avg and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

FUNDING_STRATEGIES = {
    "M31_SMA": (m31_sma, {"period":[12,24], "entry_thr":[0.00001], "exit_thr":[0.000005]}),
    "M31_EMA": (m31_ema, {"period":[12,24], "entry_thr":[0.00001], "exit_thr":[0.000005]}),
    "M31_THRESHOLD": (m31_threshold, {"entry_thr":[0.00003,0.00005], "exit_thr":[0.000005]}),
    "M31_QUANTILE": (m31_quantile, {"window":[30,50], "quantile":[0.6,0.7,0.8]}),
    "M31_MOMENTUM": (m31_momentum, {"lookback":[4,6,12]}),
}

# NOTE: These return dict of daily returns, NOT trade list like other strategies.
# Screening engine must handle them separately.
''')
print("[7/8] funding.py (5)")

# ═══════════════════════════════════════
# registry.py — unified registry
# ═══════════════════════════════════════
open('strategies/library/registry.py', 'w').write('''"""Unified strategy registry — all 40 strategies in one place."""
from strategies.library.trend import TREND_STRATEGIES
from strategies.library.mean_reversion import MR_STRATEGIES
from strategies.library.momentum import MOMENTUM_STRATEGIES
from strategies.library.volatility import VOL_STRATEGIES
from strategies.library.volume import VOLUME_STRATEGIES
from strategies.library.funding import FUNDING_STRATEGIES

# Strategies that use candles (price-based)
CANDLE_STRATEGIES = {}
CANDLE_STRATEGIES.update(TREND_STRATEGIES)
CANDLE_STRATEGIES.update(MR_STRATEGIES)
CANDLE_STRATEGIES.update(MOMENTUM_STRATEGIES)
CANDLE_STRATEGIES.update(VOL_STRATEGIES)
CANDLE_STRATEGIES.update(VOLUME_STRATEGIES)

# Strategies that use funding data
FUNDING_STRATS = dict(FUNDING_STRATEGIES)

ALL_STRATEGIES = {**CANDLE_STRATEGIES, **FUNDING_STRATS}

def get_strategy(name):
    """Return (func, param_grid) for a strategy name."""
    if name in CANDLE_STRATEGIES:
        func, grid = CANDLE_STRATEGIES[name]
        return func, grid, "candle"
    if name in FUNDING_STRATS:
        func, grid = FUNDING_STRATS[name]
        return func, grid, "funding"
    raise KeyError(f"Unknown strategy: {name}")

def list_strategies():
    """Return list of (name, kind)."""
    out = []
    for name in CANDLE_STRATEGIES:
        out.append((name, "candle"))
    for name in FUNDING_STRATS:
        out.append((name, "funding"))
    return out

def expand_param_grid(grid):
    """Expand param grid to list of dicts. E.g. {"a":[1,2], "b":[3]} -> [{a:1,b:3},{a:2,b:3}]"""
    if not grid: return [{}]
    keys = list(grid.keys())
    combos = [{}]
    for k in keys:
        new = []
        for v in grid[k]:
            for c in combos:
                nc = dict(c); nc[k] = v
                new.append(nc)
        combos = new
    return combos

print(f"[registry] {len(CANDLE_STRATEGIES)} candle strategies, {len(FUNDING_STRATS)} funding strategies")
print(f"[registry] Total: {len(ALL_STRATEGIES)} strategies")
''')
print("[8/8] registry.py")

print("\\n✅ All 8 library files built.")
print("Count: 10 trend + 8 MR + 6 momentum + 5 vol + 4 volume + 5 funding = 38 strategies")
