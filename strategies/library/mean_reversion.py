"""Mean reversion strategies (8)."""
from strategies.library.indicators import ema, sma, atr, rsi, bollinger

def _trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}

def strat_bollinger(candles, period=20, mult=2.0, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    up, mid, lo = bollinger(closes, period, mult)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if None in (up[i], lo[i], mid[i], at[i-1]): continue
        if not pos:
            if candles[i]["c"] < lo[i]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":mid[i]}
            elif candles[i]["c"] > up[i]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":mid[i]}
        else:
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

def strat_rsi_reversal(candles, period=14, low=30, high=70, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    rv = rsi(closes, period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period+1, len(candles)):
        if None in (rv[i], rv[i-1], at[i-1]): continue
        if not pos:
            if rv[i-1] < low and rv[i] >= low:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+3*at[i-1]}
            elif rv[i-1] > high and rv[i] <= high:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":candles[i]["c"]-3*at[i-1]}
        else:
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

def strat_zscore(candles, period=20, threshold=2.0, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    mv, sv = sma(closes, period), sma([x*x for x in closes], period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if None in (mv[i], sv[i], at[i-1]): continue
        std = max(sv[i] - mv[i]*mv[i], 0) ** 0.5
        if std == 0: continue
        z = (closes[i] - mv[i]) / std
        if not pos:
            if z < -threshold:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":mv[i]}
            elif z > threshold:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":mv[i]}
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

def strat_keltner_reversion(candles, period=20, mult=2.0, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    m = ema(closes, period)
    at = atr(candles, period)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period+1, len(candles)):
        if None in (m[i], at[i]): continue
        up = m[i] + mult * at[i]
        lo = m[i] - mult * at[i]
        if not pos:
            if candles[i]["c"] < lo:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":lo-at[i],"tp":m[i]}
            elif candles[i]["c"] > up:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":up+at[i],"tp":m[i]}
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

def strat_rsi_divergence(candles, period=14, lookback=10, fee_multiplier=1.0):
    if len(candles) < period + lookback + 5: return []
    closes = [c["c"] for c in candles]
    rv = rsi(closes, period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period + lookback, len(candles)):
        if rv[i] is None or rv[i-lookback] is None or at[i-1] is None: continue
        if not pos:
            price_low_now = min(c["l"] for c in candles[i-lookback:i+1])
            price_low_prev = min(c["l"] for c in candles[i-2*lookback:i-lookback+1])
            if candles[i]["l"] <= price_low_now and candles[i]["l"] < price_low_prev and rv[i] > rv[i-lookback]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+3*at[i-1]}
            price_high_now = max(c["h"] for c in candles[i-lookback:i+1])
            price_high_prev = max(c["h"] for c in candles[i-2*lookback:i-lookback+1])
            if candles[i]["h"] >= price_high_now and candles[i]["h"] > price_high_prev and rv[i] < rv[i-lookback]:
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

def strat_mean_rev_sma(candles, period=50, deviation=0.02, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    sv = sma(closes, period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if None in (sv[i], at[i-1]): continue
        if not pos:
            if candles[i]["c"] < sv[i] * (1 - deviation):
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":sv[i]}
            elif candles[i]["c"] > sv[i] * (1 + deviation):
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":sv[i]}
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

def strat_connors_rsi(candles, rsi_period=3, sma_period=200, fee_multiplier=1.0):
    if len(candles) < sma_period + 10: return []
    closes = [c["c"] for c in candles]
    rv = rsi(closes, rsi_period)
    sv = sma(closes, sma_period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(sma_period, len(candles)):
        if None in (rv[i], sv[i], at[i-1]): continue
        if not pos:
            if candles[i]["c"] > sv[i] and rv[i] < 10:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+3*at[i-1]}
        elif pos:
            ex = None
            if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
            elif candles[i]["h"]>=pos["tp"]: ex=pos["tp"]
            if ex:
                trades.append(_trade(candles[i], "LONG", pos["entry"], ex, fee))
                pos = None
    return trades

def strat_rsi_mean(candles, period=14, low=40, high=60, fee_multiplier=1.0):
    if len(candles) < period + 10: return []
    closes = [c["c"] for c in candles]
    rv = rsi(closes, period)
    ef = ema(closes, 50)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period+1, len(candles)):
        if None in (rv[i], ef[i]): continue
        if not pos:
            if rv[i-1] < low and rv[i] >= low and candles[i]["c"] > ef[i]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]*0.98,"tp":candles[i]["c"]*1.04}
        elif pos:
            ex = None
            if candles[i]["l"]<=pos["sl"]: ex=pos["sl"]
            elif candles[i]["h"]>=pos["tp"]: ex=pos["tp"]
            if ex:
                trades.append(_trade(candles[i], "LONG", pos["entry"], ex, fee))
                pos = None
    return trades

MR_STRATEGIES = {
    "BOLLINGER": (strat_bollinger, {"period":[20,30], "mult":[2.0,2.5]}),
    "RSI_REVERSAL": (strat_rsi_reversal, {"period":[14], "low":[25,30], "high":[70,75]}),
    "ZSCORE": (strat_zscore, {"period":[20,30], "threshold":[1.5,2.0,2.5]}),
    "KELTNER_REV": (strat_keltner_reversion, {"period":[20], "mult":[1.5,2.0]}),
    "RSI_DIVERGENCE": (strat_rsi_divergence, {"period":[14], "lookback":[10,20]}),
    "MEAN_REV_SMA": (strat_mean_rev_sma, {"period":[50,100], "deviation":[0.015,0.02,0.03]}),
    "CONNORS_RSI": (strat_connors_rsi, {"rsi_period":[2,3], "sma_period":[200]}),
    "RSI_MEAN": (strat_rsi_mean, {"period":[14], "low":[35,40], "high":[60,65]}),
}
