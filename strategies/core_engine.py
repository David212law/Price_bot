import json
import os
import math
import random
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

# ─── استراتژی‌ها ───
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
                trades.append({"ret": gross_ret - (base_fee * 2)})
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
            if candles[i]["l"] <= in_pos["sl"]: trades.append({"ret": -0.10 - (base_fee*2)}); in_pos = None
            elif candles[i]["h"] >= in_pos["tp"]: trades.append({"ret": 0.02 - (base_fee*2)}); in_pos = None
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
                trades.append({"ret": gross_ret - (base_fee*2)})
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
    
    # CVaR (میانگین ۵٪ بدترین معاملات)
    sorted_rets = sorted([t["ret"] for t in trades])
    cvar_5_idx = max(1, int(len(sorted_rets) * 0.05))
    cvar = sum(sorted_rets[:cvar_5_idx]) / cvar_5_idx
    
    equity, peak, max_dd = initial_capital, initial_capital, 0
    tuw = 0
    max_tuw = 0
    for t in trades:
        equity += equity * t["ret"] * 0.01
        if equity > peak: 
            peak = equity
            tuw = 0
        else:
            tuw += 1
            max_tuw = max(max_tuw, tuw)
        dd = (peak - equity) / peak
        if dd > max_dd: max_dd = dd

    return {
        "status": "OK", "n": n, "win_rate": round((wins/n)*100, 2),
        "pf": round(pf, 2), "max_dd": round(max_dd*100, 2),
        "cvar_5": round(cvar * 100, 2), "max_tuw_trades": max_tuw
    }

def log_trial(exchange, strategy, metrics, fee_multiplier, phase="IS"):
    ledger_path = "research_lab/logs/trial_ledger.json"
    os.makedirs("research_lab/logs", exist_ok=True)
    
    ledger = []
    if os.path.exists(ledger_path):
        with open(ledger_path, "r") as f:
            try: ledger = json.load(f)
            except: ledger = []
            
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exchange": exchange, "strategy": strategy, "phase": phase,
        "fee_multiplier": fee_multiplier, "metrics": metrics
    }
    ledger.append(record)
    
    with open(ledger_path, "w") as f:
        json.dump(ledger, f, indent=2)
