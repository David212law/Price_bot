"""Volume-based strategies (4)."""
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
    "VOLUME_BREAKOUT": (strat_volume_breakout, {"vol_period":[20], "mult":[1.5,2.0,3.0]}),
}
