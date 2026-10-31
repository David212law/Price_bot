"""Trend strategies (10)."""
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
