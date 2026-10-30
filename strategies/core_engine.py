import json
import os
import math
from datetime import datetime, timezone
from strategies.indicators import calc_ema, calc_atr

# ─── اندیکاتورها ───
def calc_bb(closes, period, std_mult):
    upper, lower = [None]*len(closes), [None]*len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i-period+1:i+1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = variance ** 0.5
        upper[i] = sma + (std_mult * std)
        lower[i] = sma - (std_mult * std)
    return upper, lower

def calc_rsi(closes, period=14):
    rsi = [None] * len(closes)
    if len(closes) < period + 1: return rsi
    gains, losses = 0, 0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain, avg_loss = gains / period, losses / period
    rsi[period] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain, loss = (change if change > 0 else 0), (abs(change) if change < 0 else 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi[i] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    return rsi

def calc_supertrend(candles, period=10, multiplier=3.0):
    atr = calc_atr(candles, period)
    st, direction = [None]*len(candles), [1]*len(candles)
    for i in range(period, len(candles)):
        if atr[i] is None: continue
        hl2 = (candles[i]["h"] + candles[i]["l"]) / 2
        upperband, lowerband = hl2 + (multiplier * atr[i]), hl2 - (multiplier * atr[i])
        if i == period: st[i], direction[i] = upperband, 1; continue
        if candles[i]["c"] > st[i-1]:
            direction[i] = 1
            st[i] = max(lowerband, st[i-1]) if direction[i-1] == 1 else lowerband
        else:
            direction[i] = -1
            st[i] = min(upperband, st[i-1]) if direction[i-1] == -1 else upperband
    return st, direction

def load_data(exchange, symbol):
    if exchange == "kucoin": path = f"exchanges/kucoin/data/{symbol}_4h.json"
    elif exchange == "aster": path = f"data/aster/{symbol}_4h.json"
    elif exchange == "hyperliquid": path = f"data/hyperliquid/{symbol}_4h.json"
    else: return None
    if not os.path.exists(path): return None
    with open(path, 'r') as f: 
        data = json.load(f)
        return data.get("candles", data) if isinstance(data, dict) else data

# ─── استراتژی‌ها (با ثبت زمان) ───
def strategy_m35(candles, fast=50, slow=200, fee_multiplier=1.0):
    closes = [c["c"] for c in candles]
    ema_f, ema_s = calc_ema(closes, fast), calc_ema(closes, slow)
    atr = calc_atr(candles, 14)
    trades, in_pos = [], None
    base_fee = 0.0006 * fee_multiplier 
    for i in range(slow, len(candles)):
        if None in [ema_f[i], ema_s[i], atr[i-1]]: continue
        if not in_pos:
            if ema_f[i] > ema_s[i] and ema_f[i-1] <= ema_s[i-1]:
                in_pos = {"side": "LONG", "entry": candles[i]["c"], "sl": candles[i]["c"] - (3*atr[i-1])}
            elif ema_f[i] < ema_s[i] and ema_f[i-1] >= ema_s[i-1]:
                in_pos = {"side": "SHORT", "entry": candles[i]["c"], "sl": candles[i]["c"] + (3*atr[i-1])}
        else:
            exit_price = None
            if in_pos["side"] == "LONG":
                if candles[i]["l"] <= in_pos["sl"]: exit_price = in_pos["sl"]
                elif ema_f[i] < ema_s[i]: exit_price = candles[i]["c"]
            else:
                if candles[i]["h"] >= in_pos["sl"]: exit_price = in_pos["sl"]
                elif ema_f[i] > ema_s[i]: exit_price = candles[i]["c"]
            if exit_price:
                gross_ret = (exit_price - in_pos["entry"]) / in_pos["entry"] if in_pos["side"] == "LONG" else (in_pos["entry"] - exit_price) / in_pos["entry"]
                trades.append({"t": candles[i]["t"], "ret": gross_ret - (base_fee * 2)})
                in_pos = None
    return trades

def strategy_a8(candles, fee_multiplier=1.0):
    closes = [c["c"] for c in candles]
    bb_u, bb_l = calc_bb(closes, 20, 2.0)
    rsi = calc_rsi(closes, 14)
    ema_200 = calc_ema(closes, 200)
    trades, in_pos = [], None
    base_fee = 0.0002 * fee_multiplier
    for i in range(200, len(candles)):
        if None in [bb_l[i], rsi[i], ema_200[i]]: continue
        if not in_pos:
            if candles[i]["c"] > ema_200[i] and candles[i]["c"] <= bb_l[i] and rsi[i] < 35:
                in_pos = {"entry": candles[i]["c"], "sl": candles[i]["c"] * 0.90, "tp": candles[i]["c"] * 1.02}
        else:
            if candles[i]["l"] <= in_pos["sl"]: trades.append({"t": candles[i]["t"], "ret": -0.10 - (base_fee*2)}); in_pos = None
            elif candles[i]["h"] >= in_pos["tp"]: trades.append({"t": candles[i]["t"], "ret": 0.02 - (base_fee*2)}); in_pos = None
    return trades

def strategy_a20(candles, fee_multiplier=1.0):
    st, direction = calc_supertrend(candles, 10, 3.0)
    trades, in_pos = [], None
    base_fee = 0.0006 * fee_multiplier
    for i in range(14, len(candles)):
        if st[i-1] is None: continue
        if not in_pos:
            if direction[i] == 1 and direction[i-1] == -1:
                in_pos = {"side": "LONG", "entry": candles[i]["c"], "sl": st[i-1]}
            elif direction[i] == -1 and direction[i-1] == 1:
                in_pos = {"side": "SHORT", "entry": candles[i]["c"], "sl": st[i-1]}
        else:
            exit_price = None
            if in_pos["side"] == "LONG":
                if candles[i]["l"] <= in_pos["sl"] or direction[i] == -1: exit_price = candles[i]["c"]
            else:
                if candles[i]["h"] >= in_pos["sl"] or direction[i] == 1: exit_price = candles[i]["c"]
            if exit_price:
                gross_ret = (exit_price - in_pos["entry"]) / in_pos["entry"] if in_pos["side"] == "LONG" else (in_pos["entry"] - exit_price) / in_pos["entry"]
                trades.append({"t": candles[i]["t"], "ret": gross_ret - (base_fee*2)})
                in_pos = None
    return trades

def strategy_m40(candles, fee_multiplier=1.0):
    closes = [c["c"] for c in candles]
    ema_200 = calc_ema(closes, 200)
    rsi = calc_rsi(closes, 14)
    atr = calc_atr(candles, 14)
    trades, in_pos = [], None
    base_fee = 0.0006 * fee_multiplier
    for i in range(200, len(candles)):
        if None in [ema_200[i], rsi[i], atr[i-1]]: continue
        if not in_pos:
            if candles[i]["c"] > ema_200[i] and rsi[i] < 40 and candles[i]["c"] > candles[i]["o"]:
                in_pos = {"side": "LONG", "entry": candles[i]["c"], "sl": candles[i]["c"] - (1.5*atr[i-1]), "tp": candles[i]["c"] + (3*atr[i-1])}
            elif candles[i]["c"] < ema_200[i] and rsi[i] > 60 and candles[i]["c"] < candles[i]["o"]:
                in_pos = {"side": "SHORT", "entry": candles[i]["c"], "sl": candles[i]["c"] + (1.5*atr[i-1]), "tp": candles[i]["c"] - (3*atr[i-1])}
        else:
            exit_price = None
            if in_pos["side"] == "LONG":
                if candles[i]["l"] <= in_pos["sl"]: exit_price = in_pos["sl"]
                elif candles[i]["h"] >= in_pos["tp"]: exit_price = in_pos["tp"]
            else:
                if candles[i]["h"] >= in_pos["sl"]: exit_price = in_pos["sl"]
                elif candles[i]["l"] <= in_pos["tp"]: exit_price = in_pos["tp"]
            if exit_price:
                gross_ret = (exit_price - in_pos["entry"]) / in_pos["entry"] if in_pos["side"] == "LONG" else (in_pos["entry"] - exit_price) / in_pos["entry"]
                trades.append({"t": candles[i]["t"], "ret": gross_ret - (base_fee*2)})
                in_pos = None
    return trades

# ─── محاسبه متریک‌ها ───
def calculate_metrics(trades, initial_capital=10000):
    if not trades: return {"status": "NO_TRADES", "n": 0}
    n = len(trades)
    wins = sum(1 for t in trades if t["ret"] > 0)
    gross_profit = sum(t["ret"] for t in trades if t["ret"] > 0)
    gross_loss = abs(sum(t["ret"] for t in trades if t["ret"] <= 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else 99.99
    
    equity, peak, max_dd = initial_capital, initial_capital, 0
    for t in trades:
        equity += equity * t["ret"] * 0.01
        if equity > peak: peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd: max_dd = dd
    return {"status": "OK", "n": n, "win_rate": round((wins/n)*100, 2), "pf": round(pf, 2), "max_dd": round(max_dd*100, 2)}

def log_trial(exchange, strategy, metrics, fee_multiplier, phase="IS"):
    ledger_path = "research_lab/logs/trial_ledger.json"
    os.makedirs("research_lab/logs", exist_ok=True)
    ledger = []
    if os.path.exists(ledger_path):
        with open(ledger_path, "r") as f:
            try: ledger = json.load(f)
            except: ledger = []
    ledger.append({"timestamp": datetime.now(timezone.utc).isoformat(), "exchange": exchange, "strategy": strategy, "phase": phase, "fee_multiplier": fee_multiplier, "metrics": metrics})
    with open(ledger_path, "w") as f:
        json.dump(ledger, f, indent=2)

# ═══════════ استراتژی‌های جدید (D-290) ═══════════

def strategy_m50_regime_bh(candles, fee_multiplier=1.0):
    """Regime-Filtered Buy & Hold: فقط در روند صعودی"""
    closes = [c["c"] for c in candles]
    ema_200 = calc_ema(closes, 200)
    if len(candles) < 250: return []
    
    trades, in_pos = [], None
    base_fee = 0.0006 * fee_multiplier
    
    for i in range(200, len(candles)):
        if ema_200[i] is None: continue
        uptrend = closes[i] > ema_200[i]
        
        if in_pos and not uptrend:
            ret = (candles[i]["c"] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
            trades.append({"t": candles[i]["t"], "ret": ret})
            in_pos = None
        elif not in_pos and uptrend:
            in_pos = {"entry": candles[i]["c"]}
    
    if in_pos:
        ret = (candles[-1]["c"] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
        trades.append({"t": candles[-1]["t"], "ret": ret})
    return trades

def strategy_m51_extreme_rev(candles, fee_multiplier=1.0):
    """Extreme Mean Reversion: RSI(2)<5 + Bollinger پایین، نگه‌داری ۵ کندل"""
    closes = [c["c"] for c in candles]
    bb_l = calc_bb(closes, 20, 2.0)[1]
    rsi2 = calc_rsi(closes, 2)
    if len(candles) < 30: return []
    
    trades, in_pos, entry_idx = [], None, 0
    base_fee = 0.0006 * fee_multiplier
    
    for i in range(20, len(candles)):
        if None in [bb_l[i], rsi2[i]]: continue
        
        if in_pos:
            if (i - entry_idx) >= 5:  # خروج پس از ۵ کندل
                ret = (candles[i]["c"] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
                trades.append({"t": candles[i]["t"], "ret": ret})
                in_pos = None
        elif closes[i] <= bb_l[i] and rsi2[i] < 5:
            in_pos = {"entry": closes[i]}
            entry_idx = i
    
    if in_pos:
        ret = (candles[-1]["c"] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
        trades.append({"t": candles[-1]["t"], "ret": ret})
    return trades

def strategy_m52_xsect_momentum(candles, fee_multiplier=1.0):
    """Cross-Sectional Momentum: نسخه تک‌دارایی (لانگ برندگان ۳۰ روزه)"""
    closes = [c["c"] for c in candles]
    if len(candles) < 35: return []
    
    trades, in_pos = [], None
    base_fee = 0.0006 * fee_multiplier
    
    for i in range(30, len(candles)):
        past_ret = (closes[i-1] - closes[i-30]) / closes[i-30]
        
        if in_pos:
            if (i - in_pos["idx"]) >= 10:  # نگه‌داری ۱۰ کندل
                ret = (closes[i] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
                trades.append({"t": candles[i]["t"], "ret": ret})
                in_pos = None
        elif past_ret > 0.05:  # ۵٪ رشد در ۳۰ روز اخیر
            in_pos = {"entry": closes[i], "idx": i}
    
    if in_pos:
        ret = (closes[-1] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
        trades.append({"t": candles[-1]["t"], "ret": ret})
    return trades

def strategy_m53_vol_breakout(candles, fee_multiplier=1.0):
    """Volume Breakout: شکست با حجم ۳ برابر میانگین"""
    closes = [c["c"] for c in candles]
    vols = [c["v"] for c in candles]
    vol_sma = calc_sma_vol(vols, 20)
    if len(candles) < 25: return []
    
    trades, in_pos = [], None
    base_fee = 0.0006 * fee_multiplier
    
    for i in range(20, len(candles)):
        if vol_sma[i] is None: continue
        
        if in_pos:
            # خروج: SL 2% یا TP 5%
            if candles[i]["l"] <= in_pos["entry"] * 0.98:
                trades.append({"t": candles[i]["t"], "ret": -0.02 - 2*base_fee})
                in_pos = None
            elif candles[i]["h"] >= in_pos["entry"] * 1.05:
                trades.append({"t": candles[i]["t"], "ret": 0.05 - 2*base_fee})
                in_pos = None
            elif (i - in_pos["idx"]) >= 15:
                ret = (closes[i] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
                trades.append({"t": candles[i]["t"], "ret": ret})
                in_pos = None
        elif candles[i]["v"] > 3 * vol_sma[i] and closes[i] > closes[i-1]:
            in_pos = {"entry": closes[i], "idx": i}
    
    if in_pos:
        ret = (closes[-1] - in_pos["entry"]) / in_pos["entry"] - 2*base_fee
        trades.append({"t": candles[-1]["t"], "ret": ret})
    return trades

def calc_sma_vol(vols, period):
    sma = [None] * len(vols)
    s = 0
    for i in range(len(vols)):
        s += vols[i]
        if i >= period: s -= vols[i - period]
        if i >= period - 1: sma[i] = s / period
    return sma
