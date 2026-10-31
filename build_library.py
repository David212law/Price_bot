"""Build 40-strategy library. One-shot script."""
import os

os.makedirs('strategies/library', exist_ok=True)

# ═══════════════════════════════════════
# __init__.py
# ═══════════════════════════════════════
open('strategies/library/__init__.py', 'w').write('"""Strategy Library — 40 strategies."""\n')

# ═══════════════════════════════════════
# indicators.py — shared helpers
# ═══════════════════════════════════════
open('strategies/library/indicators.py', 'w').write('''"""Shared indicator helpers for strategy library."""
import math

def ema(values, period):
    out = [None] * len(values)
    if len(values) < period: return out
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    out[period - 1] = e
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out

def sma(values, period):
    out = [None] * len(values)
    if len(values) < period: return out
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i-period+1:i+1]) / period
    return out

def atr(candles, period=14):
    out = [None] * len(candles)
    if len(candles) < period + 1: return out
    trs = [0] * len(candles)
    for i in range(1, len(candles)):
        trs[i] = max(candles[i]["h"] - candles[i]["l"],
                     abs(candles[i]["h"] - candles[i-1]["c"]),
                     abs(candles[i]["l"] - candles[i-1]["c"]))
    out[period] = sum(trs[1:period+1]) / period
    for i in range(period + 1, len(candles)):
        out[i] = (out[i-1] * (period - 1) + trs[i]) / period
    return out

def rsi(values, period=14):
    out = [None] * len(values)
    if len(values) < period + 1: return out
    gains = losses = 0
    for i in range(1, period + 1):
        ch = values[i] - values[i-1]
        if ch > 0: gains += ch
        else: losses += abs(ch)
    ag, al = gains / period, losses / period
    out[period] = 100 - 100/(1 + ag/al) if al else 100
    for i in range(period + 1, len(values)):
        ch = values[i] - values[i-1]
        ag = (ag * (period-1) + max(ch, 0)) / period
        al = (al * (period-1) + max(-ch, 0)) / period
        out[i] = 100 - 100/(1 + ag/al) if al else 100
    return out

def bollinger(values, period=20, mult=2.0):
    mid = sma(values, period)
    upper = [None] * len(values)
    lower = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i-period+1:i+1]
        m = mid[i]
        var = sum((x - m) ** 2 for x in window) / period
        std = math.sqrt(var)
        upper[i] = m + mult * std
        lower[i] = m - mult * std
    return upper, mid, lower

def macd(values, fast=12, slow=26, signal=9):
    ema_f = ema(values, fast)
    ema_s = ema(values, slow)
    macd_line = [None] * len(values)
    for i in range(len(values)):
        if ema_f[i] is not None and ema_s[i] is not None:
            macd_line[i] = ema_f[i] - ema_s[i]
    valid = [m for m in macd_line if m is not None]
    sig = ema(valid, signal) if len(valid) >= signal else [None]*len(valid)
    # align
    aligned = [None] * len(values)
    offset = len(values) - len(valid)
    for i, s in enumerate(sig):
        if s is not None: aligned[offset + i] = s
    return macd_line, aligned

def adx(candles, period=14):
    if len(candles) < period * 2: return [None] * len(candles)
    trs, pdms, mdms = [], [], []
    for i in range(1, len(candles)):
        h, l = candles[i]["h"], candles[i]["l"]
        ph, pl, pc = candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
        up, dn = h-ph, pl-l
        pdms.append(up if (up > dn and up > 0) else 0)
        mdms.append(dn if (dn > up and dn > 0) else 0)
    if len(trs) < period: return [None]*len(candles)
    atr_v = sum(trs[:period])/period
    ps, ms = sum(pdms[:period]), sum(mdms[:period])
    dxs = []
    for i in range(period, len(trs)):
        atr_v = (atr_v*(period-1)+trs[i])/period
        ps = ps - ps/period + pdms[i]
        ms = ms - ms/period + mdms[i]
        pdi = 100*ps/(atr_v*period) if atr_v else 0
        mdi = 100*ms/(atr_v*period) if atr_v else 0
        dx = 100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi) > 0 else 0
        dxs.append(dx)
    if len(dxs) < period: return [None]*len(candles)
    adx_v = sum(dxs[:period])/period
    adx_out = [None] * (period + 1)
    adx_out.append(adx_v)
    for i in range(period, len(dxs)):
        adx_v = (adx_v*(period-1)+dxs[i])/period
        adx_out.append(adx_v)
    return adx_out[:len(candles)]

def supertrend(candles, period=10, mult=3.0):
    atr_v = atr(candles, period)
    st = [None]*len(candles)
    dirs = [1]*len(candles)
    for i in range(period, len(candles)):
        if atr_v[i] is None: continue
        hl2 = (candles[i]["h"]+candles[i]["l"])/2
        ub, lb = hl2+mult*atr_v[i], hl2-mult*atr_v[i]
        if i == period:
            st[i], dirs[i] = ub, 1
            continue
        if candles[i]["c"] > st[i-1]:
            dirs[i] = 1
            st[i] = max(lb, st[i-1]) if dirs[i-1]==1 else lb
        else:
            dirs[i] = -1
            st[i] = min(ub, st[i-1]) if dirs[i-1]==-1 else ub
    return st, dirs

def donchian(candles, period=20):
    upper = [None]*len(candles)
    lower = [None]*len(candles)
    for i in range(period-1, len(candles)):
        window = candles[i-period+1:i+1]
        upper[i] = max(c["h"] for c in window)
        lower[i] = min(c["l"] for c in window)
    return upper, lower
''')

print("[1/8] indicators.py")

# ═══════════════════════════════════════
# trend.py — 10 strategies
# ═══════════════════════════════════════
open('strategies/library/trend.py', 'w').write('''"""Trend strategies (10)."""
from strategies.library.indicators import ema, sma, atr, macd, adx, supertrend, donchian

def _make_trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}

def strat_ema_cross(candles, fast=20, slow=50, fee_multiplier=1.0):
    if len(candles) < slow + 5: return []
    closes = [c["c"] for c in candles]
    ef, es = ema(closes, fast), ema(closes, slow)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(slow, len(candles)):
        if None in (ef[i], es[i], at[i-1]): continue
        if not pos:
            if ef[i] > es[i] and ef[i-1] <= es[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1]}
            elif ef[i] < es[i] and ef[i-1] >= es[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+3*at[i-1]}
        else:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif ef[i]<es[i]: ex=candles[i]["c"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif ef[i]>es[i]: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_macd(candles, fast=12, slow=26, signal=9, fee_multiplier=1.0):
    if len(candles) < slow + signal + 5: return []
    closes = [c["c"] for c in candles]
    ml, sg = macd(closes, fast, slow, signal)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(slow + signal, len(candles)):
        if None in (ml[i], sg[i], ml[i-1], sg[i-1], at[i-1]): continue
        if not pos:
            if ml[i] > sg[i] and ml[i-1] <= sg[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1]}
            elif ml[i] < sg[i] and ml[i-1] >= sg[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+3*at[i-1]}
        else:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif ml[i]<sg[i]: ex=candles[i]["c"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif ml[i]>sg[i]: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_adx_trend(candles, period=14, threshold=25, fee_multiplier=1.0):
    if len(candles) < period * 2 + 5: return []
    adx_vals = adx(candles, period)
    ef, es = ema([c["c"] for c in candles], 20), ema([c["c"] for c in candles], 50)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period*2, len(candles)):
        if None in (adx_vals[i], ef[i], es[i], at[i-1]): continue
        if not pos and adx_vals[i] > threshold:
            if ef[i] > es[i]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1]}
            elif ef[i] < es[i]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+3*at[i-1]}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif adx_vals[i] < threshold: ex=candles[i]["c"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif adx_vals[i] < threshold: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_supertrend(candles, period=10, mult=3.0, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    st, dirs = supertrend(candles, period, mult)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period+1, len(candles)):
        if None in (st[i], st[i-1], at[i-1]): continue
        if not pos and dirs[i] != dirs[i-1]:
            side = "LONG" if dirs[i]==1 else "SHORT"
            pos = {"side":side,"entry":candles[i]["c"],"sl":st[i-1]}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif dirs[i]==-1: ex=candles[i]["c"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif dirs[i]==1: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_donchian(candles, period=20, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    up, lo = donchian(candles, period)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if None in (up[i], lo[i], up[i-1], lo[i-1]): continue
        if not pos:
            if candles[i]["c"] > up[i-1]: pos = {"side":"LONG","entry":candles[i]["c"],"sl":lo[i]}
            elif candles[i]["c"] < lo[i-1]: pos = {"side":"SHORT","entry":candles[i]["c"],"sl":up[i]}
        else:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif candles[i]["c"] < lo[i-1]: ex=candles[i]["c"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif candles[i]["c"] > up[i-1]: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_ichimoku(candles, tenkan=9, kijun=26, fee_multiplier=1.0):
    if len(candles) < kijun + 10: return []
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    ten = [None]*len(candles)
    kij = [None]*len(candles)
    for i in range(tenkan-1, len(candles)):
        ten[i] = (max(highs[i-tenkan+1:i+1]) + min(lows[i-tenkan+1:i+1]))/2
    for i in range(kijun-1, len(candles)):
        kij[i] = (max(highs[i-kijun+1:i+1]) + min(lows[i-kijun+1:i+1]))/2
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(kijun, len(candles)):
        if ten[i] is None or kij[i] is None: continue
        if not pos:
            if ten[i] > kij[i] and ten[i-1] <= kij[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":kij[i]}
            elif ten[i] < kij[i] and ten[i-1] >= kij[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":kij[i]}
        elif pos:
            ex = None
            if pos["side"]=="LONG":
                if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
                elif ten[i] < kij[i]: ex=candles[i]["c"]
            else:
                if candles[i]["h"]>=pos["sl"]: ex=pos["sl"]
                elif ten[i] > kij[i]: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_price_sma(candles, period=50, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    sma_v = sma(closes, period)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if sma_v[i] is None: continue
        if not pos:
            if candles[i]["c"] > sma_v[i] and candles[i-1]["c"] <= sma_v[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"]}
            elif candles[i]["c"] < sma_v[i] and candles[i-1]["c"] >= sma_v[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"]}
        elif pos:
            ex = None
            if pos["side"]=="LONG" and candles[i]["c"] < sma_v[i]: ex=candles[i]["c"]
            elif pos["side"]=="SHORT" and candles[i]["c"] > sma_v[i]: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_dual_momentum(candles, fast=20, slow=50, fee_multiplier=1.0):
    if len(candles) < slow + 5: return []
    closes = [c["c"] for c in candles]
    ef, es = ema(closes, fast), ema(closes, slow)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(slow, len(candles)):
        if None in (ef[i], es[i], es[i-1]): continue
        if not pos:
            if ef[i] > es[i] and ef[i] > es[i-1] and es[i] > es[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"]}
            elif ef[i] < es[i] and ef[i] < es[i-1] and es[i] < es[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"]}
        elif pos:
            ex = None
            if pos["side"]=="LONG" and ef[i] < es[i]: ex=candles[i]["c"]
            elif pos["side"]=="SHORT" and ef[i] > es[i]: ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_triple_ema(candles, p1=10, p2=20, p3=50, fee_multiplier=1.0):
    if len(candles) < p3 + 5: return []
    closes = [c["c"] for c in candles]
    e1, e2, e3 = ema(closes, p1), ema(closes, p2), ema(closes, p3)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(p3, len(candles)):
        if None in (e1[i], e2[i], e3[i]): continue
        if not pos:
            if e1[i] > e2[i] > e3[i]:
                pos = {"side":"LONG","entry":candles[i]["c"]}
            elif e1[i] < e2[i] < e3[i]:
                pos = {"side":"SHORT","entry":candles[i]["c"]}
        elif pos:
            ex = None
            if pos["side"]=="LONG" and (e1[i] < e2[i] or candles[i]["c"] < e3[i]): ex=candles[i]["c"]
            elif pos["side"]=="SHORT" and (e1[i] > e2[i] or candles[i]["c"] > e3[i]): ex=candles[i]["c"]
            if ex:
                trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

def strat_parabolic_sar(candles, step=0.02, max_step=0.2, fee_multiplier=1.0):
    if len(candles) < 20: return []
    trades, pos = [], None
    sar = candles[0]["l"]
    ep = candles[0]["h"]
    af = step
    trending_up = True
    fee = 0.0006 * fee_multiplier
    for i in range(1, len(candles)):
        sar = sar + af * (ep - sar)
        if trending_up:
            if candles[i]["l"] < sar:
                trending_up = False
                sar = ep
                ep = candles[i]["l"]
                af = step
            elif candles[i]["h"] > ep:
                ep = candles[i]["h"]
                af = min(af + step, max_step)
        else:
            if candles[i]["h"] > sar:
                trending_up = True
                sar = ep
                ep = candles[i]["h"]
                af = step
            elif candles[i]["l"] < ep:
                ep = candles[i]["l"]
                af = min(af + step, max_step)
        new_side = "LONG" if trending_up else "SHORT"
        if pos and pos["side"] != new_side:
            trades.append(_make_trade(candles[i], pos["side"], pos["entry"], candles[i]["c"], fee))
            pos = None
        if not pos:
            pos = {"side": new_side, "entry": candles[i]["c"]}
    return trades

TREND_STRATEGIES = {
    "EMA_CROSS": (strat_ema_cross, {"fast":[10,20,50], "slow":[50,100,200]}),
    "MACD": (strat_macd, {"fast":[12], "slow":[26], "signal":[9]}),
    "ADX_TREND": (strat_adx_trend, {"period":[14,20], "threshold":[20,25,30]}),
    "SUPERTREND": (strat_supertrend, {"period":[10,14,20], "mult":[2.0,3.0,4.0]}),
    "DONCHIAN": (strat_donchian, {"period":[10,20,40]}),
    "ICHIMOKU": (strat_ichimoku, {"tenkan":[9], "kijun":[26]}),
    "PRICE_SMA": (strat_price_sma, {"period":[20,50,100,200]}),
    "DUAL_MOMENTUM": (strat_dual_momentum, {"fast":[10,20], "slow":[50,100]}),
    "TRIPLE_EMA": (strat_triple_ema, {"p1":[5,10], "p2":[20], "p3":[50]}),
    "PSAR": (strat_parabolic_sar, {"step":[0.01,0.02], "max_step":[0.1,0.2]}),
}
''')
print("[2/8] trend.py (10 strategies)")

print("\\nTrend+Indicators done. Next: mean_reversion, momentum, volatility, volume, funding, structural, registry")
