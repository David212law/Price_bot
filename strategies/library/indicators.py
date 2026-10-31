"""Shared indicator helpers for strategy library."""
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
