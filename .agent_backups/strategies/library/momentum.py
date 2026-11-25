"""Momentum strategies (6)."""
from strategies.library.indicators import ema, atr, rsi

def _trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}

def strat_roc(candles, period=10, threshold=0.02, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if at[i-1] is None: continue
        roc = (candles[i]["c"] - candles[i-period]["c"]) / candles[i-period]["c"]
        if not pos:
            if roc > threshold:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1],"tp":candles[i]["c"]+6*at[i-1]}
            elif roc < -threshold:
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

def strat_momentum_sma(candles, period=20, threshold=0.01, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if at[i-1] is None: continue
        mom = candles[i]["c"] / candles[i-period]["c"] - 1
        if not pos:
            if mom > threshold:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+4*at[i-1]}
            elif mom < -threshold:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":candles[i]["c"]-4*at[i-1]}
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

def strat_momentum_ema(candles, fast=10, slow=30, fee_multiplier=1.0):
    if len(candles) < slow + 5: return []
    closes = [c["c"] for c in candles]
    ef, es = ema(closes, fast), ema(closes, slow)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(slow+1, len(candles)):
        if None in (ef[i], es[i], ef[i-1], es[i-1], at[i-1]): continue
        strength = abs(ef[i] - es[i]) / es[i]
        if not pos and strength > 0.005:
            if ef[i] > es[i] and ef[i] > ef[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1],"tp":candles[i]["c"]+6*at[i-1]}
            elif ef[i] < es[i] and ef[i] < ef[i-1]:
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

def strat_elder_impulse(candles, ema_p=13, fee_multiplier=1.0):
    if len(candles) < ema_p + 5: return []
    closes = [c["c"] for c in candles]
    e = ema(closes, ema_p)
    _, sig = __import__('strategies.library.indicators', fromlist=['macd']).macd(closes, 12, 26, 9)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(ema_p, len(candles)):
        if None in (e[i], sig[i], e[i-1], at[i-1]): continue
        bull = e[i] > e[i-1] and sig[i] > 0
        bear = e[i] < e[i-1] and sig[i] < 0
        if not pos:
            if bull:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+4*at[i-1]}
            elif bear:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":candles[i]["c"]-4*at[i-1]}
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

def strat_rsi_momentum(candles, period=14, threshold=60, fee_multiplier=1.0):
    if len(candles) < period + 10: return []
    closes = [c["c"] for c in candles]
    rv = rsi(closes, period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period+1, len(candles)):
        if None in (rv[i], rv[i-1], at[i-1]): continue
        if not pos:
            if rv[i] > threshold and rv[i-1] <= threshold:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+4*at[i-1]}
            elif rv[i] < 100-threshold and rv[i-1] >= 100-threshold:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+2*at[i-1],"tp":candles[i]["c"]-4*at[i-1]}
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

def strat_price_momentum(candles, period=20, threshold=0.015, fee_multiplier=1.0):
    if len(candles) < period + 5: return []
    closes = [c["c"] for c in candles]
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if at[i-1] is None: continue
        mom = (candles[i]["c"] - candles[i-period]["c"]) / candles[i-period]["c"]
        if not pos:
            if mom > threshold:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1],"tp":candles[i]["c"]+6*at[i-1]}
            elif mom < -threshold:
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

MOMENTUM_STRATEGIES = {
    "ROC": (strat_roc, {"period":[5,10,20], "threshold":[0.01,0.02,0.03]}),
    "MOMENTUM_SMA": (strat_momentum_sma, {"period":[10,20,40], "threshold":[0.005,0.01,0.02]}),
    "MOMENTUM_EMA": (strat_momentum_ema, {"fast":[10,20], "slow":[30,50]}),
    "ELDER_IMPULSE": (strat_elder_impulse, {"ema_p":[13]}),
    "RSI_MOMENTUM": (strat_rsi_momentum, {"period":[14], "threshold":[55,60,65]}),
    "PRICE_MOMENTUM": (strat_price_momentum, {"period":[10,20,50], "threshold":[0.01,0.015,0.02]}),
}
