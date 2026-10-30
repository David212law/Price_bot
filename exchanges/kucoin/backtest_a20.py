import json
import os
import math
import random
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]

INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0006 # 0.06% (KuCoin Futures)
MAKER_FEE = 0.0002 # 0.02%

# A20 Params (SuperTrend)
ST_PERIOD = 10
ST_MULT = 3.0
ATR_PERIOD = 14
RISK_PER_TRADE = 0.01
MAX_ALLOC_PCT = 0.10
MAX_CONCURRENT = 3

def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: 
        data = json.load(f)
        return data.get("candles", [])

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

def calc_supertrend(candles, period=10, multiplier=3.0):
    atr = calc_atr(candles, period)
    st = [None] * len(candles)
    direction = [1] * len(candles)
    for i in range(period, len(candles)):
        if atr[i] is None: continue
        hl2 = (candles[i]["h"] + candles[i]["l"]) / 2
        upperband = hl2 + (multiplier * atr[i])
        lowerband = hl2 - (multiplier * atr[i])
        if i == period:
            st[i] = upperband
            direction[i] = 1
            continue
        if candles[i]["c"] > st[i-1]:
            direction[i] = 1
            st[i] = max(lowerband, st[i-1]) if direction[i-1] == 1 else lowerband
        else:
            direction[i] = -1
            st[i] = min(upperband, st[i-1]) if direction[i-1] == -1 else upperband
    return st, direction

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

def block_bootstrap_p_value(equity_curve, block_size=6, iterations=500):
    if len(equity_curve) < block_size * 2: return 1.0
    rets = [(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1] for i in range(1, len(equity_curve)) if equity_curve[i-1] > 0]
    actual_final = equity_curve[-1] / equity_curve[0]
    n_blocks = len(rets) // block_size
    better = 0
    for _ in range(iterations):
        sampled = []
        for _ in range(n_blocks):
            start_idx = random.randint(0, len(rets) - block_size)
            sampled.extend(rets[start_idx:start_idx+block_size])
        sim_eq = 1.0
        for r in sampled: sim_eq *= (1 + r)
        if sim_eq >= actual_final: better += 1
    return better / iterations

def run_backtest(data_dict):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve = []
    
    ind = {}
    for sym in SYMBOLS:
        st, direction = calc_supertrend(data_dict[sym], ST_PERIOD, ST_MULT)
        ind[sym] = {"st": st, "direction": direction}

    min_len = min(len(data_dict[s]) for s in SYMBOLS)
    
    for i in range(ST_PERIOD + 2, min_len):
        current_equity = cash
        
        for sym in list(positions.keys()):
            pos = positions[sym]
            c = data_dict[sym][i]
            exit_triggered = False
            exit_price = c["c"]
            reason = ""
            
            if pos["side"] == "LONG":
                if c["l"] <= pos["sl"]:
                    exit_triggered, exit_price, reason = True, pos["sl"], "SL_HIT"
                elif ind[sym]["direction"][i] == -1:
                    exit_triggered, reason = True, "ST_FLIP"
            elif pos["side"] == "SHORT":
                if c["h"] >= pos["sl"]:
                    exit_triggered, exit_price, reason = True, pos["sl"], "SL_HIT"
                elif ind[sym]["direction"][i] == 1:
                    exit_triggered, reason = True, "ST_FLIP"
                        
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
            _c = data_dict[_sym][i]
            _pos = positions[_sym]
            if _pos["side"] == "LONG":
                current_equity += _pos["units"] * _c["c"]
            else:
                pnl_pct = (_pos["entry_price"] - _c["c"]) / _pos["entry_price"]
                current_equity += _pos["invested"] + (_pos["invested"] * pnl_pct)
                
        equity_curve.append(current_equity)
        
        for sym in SYMBOLS:
            if sym in positions or len(positions) >= MAX_CONCURRENT: continue
            
            c = data_dict[sym][i]
            st = ind[sym]["st"][i-1]
            direction = ind[sym]["direction"][i]
            prev_direction = ind[sym]["direction"][i-1]
            
            if st is None: continue
            
            side = None
            if direction == 1 and prev_direction == -1:
                side = "LONG"
                sl = st
            elif direction == -1 and prev_direction == 1:
                side = "SHORT"
                sl = st
                    
            if side:
                risk_amount = current_equity * RISK_PER_TRADE
                risk_per_unit = abs(c["c"] - sl)
                if risk_per_unit <= 0: continue
                
                calc_alloc = (risk_amount / risk_per_unit) * c["c"]
                max_alloc = current_equity * MAX_ALLOC_PCT
                alloc = min(calc_alloc, max_alloc)
                
                if alloc > cash or alloc < 10: continue
                
                cash -= alloc
                units = alloc / c["c"]
                positions[sym] = {
                    "side": side, "entry_price": c["c"], 
                    "units": units, "invested": alloc, "sl": sl
                }

    return equity_curve, trades

def main():
    print(f"=== A20 SuperTrend Backtest on KuCoin Data ===")
    data_dict = {}
    for sym in SYMBOLS:
        d = load_data(sym)
        if d: data_dict[sym] = d
        
    if len(data_dict) < len(SYMBOLS):
        print("Missing data.")
        return
        
    eq, trades = run_backtest(data_dict)
    
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
        pval = block_bootstrap_p_value(eq)
        
        reason_counts = {}
        for t in trades:
            r = t.get("reason", "UNKNOWN")
            reason_counts[r] = reason_counts.get(r, 0) + 1
        
        print(f"Total Return: {ret:.2f}%")
        print(f"MaxDD: {max_dd*100:.2f}%")
        print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}%")
        print(f"Profit Factor: {pf:.2f}")
        print(f"Wilson LB: {wilson:.2f}% | P-Value: {pval:.4f}")
        print(f"\nExit Reasons: {reason_counts}")
        
        passed = (n >= 30 and ret > 0 and max_dd < 0.15 and pf > 1.2 and wilson > 36 and pval < 0.05)
        print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")
    else:
        print("No trades generated.")

if __name__ == "__main__":
    main()
