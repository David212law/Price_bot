"""Build remaining library files: MR, momentum, vol, volume, funding, structural, registry."""
import os

# ═══════════════════════════════════════
# mean_reversion.py — 8
# ═══════════════════════════════════════
open('strategies/library/mean_reversion.py', 'w').write('''"""Mean reversion strategies (8)."""
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
''')
print("[3/8] mean_reversion.py (8)")

# ═══════════════════════════════════════
# momentum.py — 6
# ═══════════════════════════════════════
open('strategies/library/momentum.py', 'w').write('''"""Momentum strategies (6)."""
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
''')
print("[4/8] momentum.py (6)")

# ═══════════════════════════════════════
# volatility.py — 5
# ═══════════════════════════════════════
open('strategies/library/volatility.py', 'w').write('''"""Volatility strategies (5)."""
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
        if not pos and is_nr:
            if candles[i+1]["c"] > up[i-1] if i+1 < len(candles) else False:
                pos = {"side":"LONG","entry":candles[i+1]["c"],"sl":lo[i-1],"tp":up[i-1]+3*at[i-1]}
            elif i+1 < len(candles) and candles[i+1]["c"] < lo[i-1]:
                pos = {"side":"SHORT","entry":candles[i+1]["c"],"sl":up[i-1],"tp":lo[i-1]-3*at[i-1]}
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
''')
print("[5/8] volatility.py (5)")

print("\\nDone. Next: volume, funding, structural, registry.")
