import json
import os
import math
import random
from datetime import datetime, timezone
from strategies.indicators import calc_ema, calc_atr

# ─── توابع کمکی (بدون تغییر) ───
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

# ─── استراتژی‌ها (با پارامترهای داینامیک) ───
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

# ... سایر استراتژی‌ها (A8, A20) و محاسبه متریک‌ها بدون تغییر ...
