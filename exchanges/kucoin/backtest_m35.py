import json
import os
import math
import random
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]

INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0006 # 0.06%
MAKER_FEE = 0.0002 # 0.02%

EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14
ATR_MULTIPLIER = 3.0
RISK_PER_TRADE = 0.01 # 1%

def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: 
        data = json.load(f)
        return data.get("candles", [])

def aggregate_to_1d(candles_4h):
    candles_1d = []
    for i in range(0, len(candles_4h), 6):
        chunk = candles_4h[i:i+6]
        if len(chunk) == 6:
            t = chunk[0]["t"]
            o = chunk[0]["o"]
            h = max(c["h"] for c in chunk)
            l = min(c["l"] for c in chunk)
            c = chunk[-1]["c"]
            v = sum(c["v"] for c in chunk)
            candles_1d.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
    return candles_1d

def calc_ema(closes, period):
    ema = [None] * len(closes)
    if len(closes) < period: return ema
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

def calc_atr(candles, period=14):
    atr = [None] * len(candles)
    if len(candles) < period + 1: return atr
    trs = [0] * len(candles)
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs[i] = max(h - l, abs(h - prev_c), abs(l - prev_c))
    first_atr = sum(trs[1:period+1]) / period
    atr[period] = first_atr
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i]) / period
    return atr

def calculate_wilson_lower_bound(wins, total, z=1.96):
    if total == 0: return 0.0
    p = wins / total
    num = p + (z**2) / (2 * total) - z * math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2)))
    den = 1 + (z**2) / total
    return (num / den) * 100

def calculate_pf(trades):
    gp = sum(t["ret"] for t in trades if t["ret"] > 0)
    gl = abs(sum(t["ret"] for t in trades if t["ret"] <= 0))
    return gp / gl if gl > 0 else 99.99

def run_backtest(data_dict_1d):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve = []
    
    ind = {}
    for sym in SYMBOLS:
        closes = [c["c"] for c in data_dict_1d[sym]]
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        atr = calc_atr(data_dict_1d[sym], ATR_PERIOD)
        ind[sym] = {"ema_fast": ema_fast, "ema_slow": ema_slow, "atr": atr}

    min_len = min(len(data_dict_1d[s]) for s in SYMBOLS)
    
    for i in range(EMA_SLOW + 2, min_len):
        current_equity = cash
        
        for sym in list(positions.keys()):
            pos = positions[sym]
            c = data_dict_1d[sym][i]
            exit_triggered = False
            exit_price = c["c"]
            reason = ""
            
            # بررسی خروج با SL یا تقاطع معکوس
            if pos["side"] == "LONG":
                if c["l"] <= pos["sl"]:
                    exit_triggered, exit_price, reason = True, pos["sl"], "SL_HIT"
                elif ind[sym]["ema_fast"][i] < ind[sym]["ema_slow"][i] and ind[sym]["ema_fast"][i-1] >= ind[sym]["ema_slow"][i-1]:
                    exit_triggered, reason = True, "EMA_CROSS"
            elif pos["side"] == "SHORT":
                if c["h"] >= pos["sl"]:
                    exit_triggered, exit_price, reason = True, pos["sl"], "SL_HIT"
                elif ind[sym]["ema_fast"][i] > ind[sym]["ema_slow"][i] and ind[sym]["ema_fast"][i-1] <= ind[sym]["ema_slow"][i-1]:
                    exit_triggered, reason = True, "EMA_CROSS"
                        
            if exit_triggered:
                if pos["side"] == "LONG":
                    ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                else:
                    ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                
                pnl = pos["invested"] * ret
                cash += pos["invested"] + pnl
                trades.append({"ret": ret, "reason": reason})
                del positions[sym]

        for _sym in positions:
            _c = data_dict_1d[_sym][i]
            _pos = positions[_sym]
            if _pos["side"] == "LONG":
                current_equity += _pos["units"] * _c["c"]
            else:
                pnl_pct = (_pos["entry_price"] - _c["c"]) / _pos["entry_price"]
                current_equity += _pos["invested"] + (_pos["invested"] * pnl_pct)
                
        equity_curve.append(current_equity)
        
        for sym in SYMBOLS:
            if sym in positions: continue
            
            c = data_dict_1d[sym][i]
            atr = ind[sym]["atr"][i-1]
            ema_f = ind[sym]["ema_fast"][i]
            ema_s = ind[sym]["ema_slow"][i]
            ema_f_prev = ind[sym]["ema_fast"][i-1]
            ema_s_prev = ind[sym]["ema_slow"][i-1]
            
            if None in [atr, ema_f, ema_s, ema_f_prev, ema_s_prev]: continue
            
            side = None
            if ema_f > ema_s and ema_f_prev <= ema_s_prev:
                side = "LONG"
                sl = c["c"] - (ATR_MULTIPLIER * atr)
            elif ema_f < ema_s and ema_f_prev >= ema_s_prev:
                side = "SHORT"
                sl = c["c"] + (ATR_MULTIPLIER * atr)
                    
            if side:
                risk_amount = current_equity * RISK_PER_TRADE
                risk_per_unit = abs(c["c"] - sl)
                if risk_per_unit <= 0: continue
                
                alloc = (risk_amount / risk_per_unit) * c["c"]
                if alloc > cash or alloc < 10: continue
                
                cash -= alloc
                units = alloc / c["c"]
                positions[sym] = {
                    "side": side, "entry_price": c["c"], 
                    "units": units, "invested": alloc, "sl": sl
                }

    return equity_curve, trades

def main():
    print(f"=== M35 (EMA Crossover 1D) Backtest on KuCoin Data ===")
    data_dict_1d = {}
    for sym in SYMBOLS:
        d4 = load_data(sym)
        if d4: data_dict_1d[sym] = aggregate_to_1d(d4)
        
    if len(data_dict_1d) < len(SYMBOLS):
        print("Missing data.")
        return
        
    eq, trades = run_backtest(data_dict_1d)
    
    final_eq = eq[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    peak = eq[0]
    max_dd = 0.0
    for val in eq:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    n = len(trades)
    if n > 0:
        wins = sum(1 for t in trades if t["ret"] > 0)
        pf = calculate_pf(trades)
        wilson = calculate_wilson_lower_bound(wins, n)
        
        reason_counts = {}
        for t in trades:
            r = t.get("reason", "UNKNOWN")
            reason_counts[r] = reason_counts.get(r, 0) + 1
        
        print(f"Total Return: {ret:.2f}%")
        print(f"MaxDD: {max_dd*100:.2f}%")
        print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}%")
        print(f"Profit Factor: {pf:.2f}")
        print(f"Wilson LB: {wilson:.2f}%")
        print(f"\nExit Reasons: {reason_counts}")
        
        passed = (n >= 15 and ret > 0 and max_dd < 0.15 and pf > 1.2 and wilson > 20)
        print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")
    else:
        print("No trades generated.")

if __name__ == "__main__":
    main()
