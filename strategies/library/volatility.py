"""Volatility strategies (5)."""
from strategies.library.indicators import ema, atr, bollinger, donchian

def _trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}

def strat_bb_squeeze(candles, period=20, squeeze_window=50, fee_multiplier=1.0):
    if len(candles) < max(period, squeeze_window) + 10: return []
    closes = [c["c"] for c in candles]
    up, mid, lo = bollinger(closes, period, 2.0)
    at = atr(candles, 14)
    widths = []
    for i in range(period-1, len(candles)):
        if up[i] is not None and lo[i] is not None:
            widths.append((up[i] - lo[i]) / mid[i])
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period + squeeze_window, len(candles)):
        if None in (up[i], lo[i], at[i-1]): continue
        w_idx = i - (period - 1)
        if w_idx < squeeze_window: continue
        recent_w = widths[w_idx-squeeze_window:w_idx]
        min_w = min(recent_w) if recent_w else 0
        cur_w = widths[w_idx] if w_idx < len(widths) else 0
        if not pos and cur_w <= min_w * 1.1:
            if candles[i]["c"] > up[i]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-3*at[i-1],"tp":candles[i]["c"]+6*at[i-1]}
            elif candles[i]["c"] < lo[i]:
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

def strat_atr_breakout(candles, period=14, mult=1.5, fee_multiplier=1.0):
    if len(candles) < period + 20: return []
    at = atr(candles, period)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period + 5, len(candles)):
        if at[i-1] is None: continue
        upper = candles[i-1]["h"] + mult * at[i-1]
        lower = candles[i-1]["l"] - mult * at[i-1]
        if not pos:
            if candles[i]["c"] > upper:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-2*at[i-1],"tp":candles[i]["c"]+4*at[i-1]}
            elif candles[i]["c"] < lower:
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

def strat_keltner_squeeze(candles, period=20, mult=2.0, fee_multiplier=1.0):
    if len(candles) < period + 20: return []
    closes = [c["c"] for c in candles]
    m = ema(closes, period)
    at = atr(candles, period)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period + 10, len(candles)):
        if None in (m[i], at[i], at[i-1]): continue
        upper_now = m[i] + mult * at[i]
        lower_now = m[i] - mult * at[i]
        upper_prev = m[i-1] + mult * at[i-1]
        lower_prev = m[i-1] - mult * at[i-1]
        width_now = (upper_now - lower_now) / m[i] if m[i] else 0
        width_prev = (upper_prev - lower_prev) / m[i-1] if m[i-1] else 0
        if not pos and width_now < width_prev * 0.7:
            if candles[i]["c"] > upper_now:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":m[i],"tp":candles[i]["c"]+4*at[i]}
            elif candles[i]["c"] < lower_now:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":m[i],"tp":candles[i]["c"]-4*at[i]}
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

def strat_vol_breakout_donchian(candles, period=20, atr_mult=1.0, fee_multiplier=1.0):
    if len(candles) < period + 10: return []
    up, lo = donchian(candles, period)
    at = atr(candles, 14)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(period, len(candles)):
        if None in (up[i-1], lo[i-1], at[i-1]): continue
        if not pos:
            if candles[i]["c"] > up[i-1] and (up[i-1] - lo[i-1]) > atr_mult * at[i-1]:
                pos = {"side":"LONG","entry":candles[i]["c"],"sl":lo[i-1],"tp":up[i-1]+3*at[i-1]}
            elif candles[i]["c"] < lo[i-1] and (up[i-1] - lo[i-1]) > atr_mult * at[i-1]:
                pos = {"side":"SHORT","entry":candles[i]["c"],"sl":up[i-1],"tp":lo[i-1]-3*at[i-1]}
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

def strat_nr_breakout(candles, nr_period=7, entry_period=20, fee_multiplier=1.0):
    if len(candles) < max(nr_period, entry_period) + 10: return []
    at = atr(candles, 14)
    up, lo = donchian(candles, entry_period)
    trades, pos = [], None
    fee = 0.0006 * fee_multiplier
    for i in range(max(nr_period, entry_period), len(candles)):
        if None in (up[i-1], lo[i-1], at[i-1]): continue
        ranges = [(candles[j]["h"]-candles[j]["l"]) for j in range(i-nr_period, i)]
        if not ranges: continue
        cur_range = candles[i]["h"] - candles[i]["l"]
        is_nr = cur_range == min(ranges)
        if not pos and is_nr and i+1 < len(candles):
            # D-429: Fix look-ahead — place order at close of i, fill at OPEN of i+1
            next_open = candles[i+1]["o"]
            if next_open > up[i-1]:
                pos = {"side":"LONG","entry":next_open,"sl":lo[i-1],"tp":up[i-1]+3*at[i-1]}
            elif next_open < lo[i-1]:
                pos = {"side":"SHORT","entry":next_open,"sl":up[i-1],"tp":lo[i-1]-3*at[i-1]}
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

VOL_STRATEGIES = {
    "BB_SQUEEZE": (strat_bb_squeeze, {"period":[20], "squeeze_window":[30,50]}),
    "ATR_BREAKOUT": (strat_atr_breakout, {"period":[14], "mult":[1.0,1.5,2.0]}),
    "KELTNER_SQUEEZE": (strat_keltner_squeeze, {"period":[20], "mult":[1.5,2.0,2.5]}),
    "VOL_DONCHIAN": (strat_vol_breakout_donchian, {"period":[20,40], "atr_mult":[0.5,1.0]}),
    "NR_BREAKOUT": (strat_nr_breakout, {"nr_period":[5,7], "entry_period":[10,20]}),
}
