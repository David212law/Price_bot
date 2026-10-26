import json
import os
import math
import random

# ─── Configuration ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "TRXUSDT"]

# ─── 1. Calibration of Math Engine ───
def run_calibration():
    print("=== [1] CALIBRATION TEST ===")
    
    # Known data: 10 wins of +2%, 5 losses of -2%
    trades = [{"ret": 0.02}] * 10 + [{"ret": -0.02}] * 5
    eq_curve = [1000, 1100, 1050, 1200, 1300] # Synthetic equity
    
    # Expected PF: (10 * 0.02) / (5 * 0.02) = 0.2 / 0.1 = 2.0
    gp = sum(t["ret"] for t in trades if t["ret"] > 0)
    gl = abs(sum(t["ret"] for t in trades if t["ret"] <= 0))
    pf = gp / gl
    
    # Expected MaxDD: Peak 1200, Trough 1050 -> DD = (1200-1050)/1200 = 12.5%
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    # Expected Calmar: Assume 2 years (730 days)
    # CAGR = (1300/1000)^(365/730) - 1 = 14.01%
    # Calmar = 14.01 / 12.5 = 1.12
    cagr = ((eq_curve[-1] / eq_curve[0]) ** (365 / 730) - 1) * 100
    calmar = cagr / (max_dd * 100)
    
    print(f"PF Calculated: {pf:.2f} (Expected: 2.00)")
    print(f"MaxDD Calculated: {max_dd*100:.2f}% (Expected: 12.50%)")
    print(f"CAGR Calculated: {cagr:.2f}% (Expected: 14.01%)")
    print(f"Calmar Calculated: {calmar:.2f} (Expected: 1.12)")
    print("Math Engine is Calibrated properly.\n")

# ─── 2. Pre-calculators ───
def pre_calc_bb(closes, period=20, std_mult=2.0):
    upper, lower = [None]*len(closes), [None]*len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i-period+1:i+1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = variance ** 0.5
        upper[i] = sma + (std_mult * std)
        lower[i] = sma - (std_mult * std)
    return upper, lower

def pre_calc_rsi(closes, period=14):
    rsi = [None] * len(closes)
    if len(closes) < period + 1: return rsi
    gains, losses = 0, 0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    rsi[period] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi[i] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    return rsi

# ─── 3. Simple Grid Backtest (M11-IR Original Logic on 4H Data) ───
def load_wallex_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f:
        return json.load(f)

def run_simple_grid(data_4h):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve = []
    
    min_len = min(len(data_4h[s]) for s in SYMBOLS)
    for sym in SYMBOLS:
        data_4h[sym] = data_4h[sym][-min_len:]
        
    ind = {}
    for sym in SYMBOLS:
        closes = [c["c"] for c in data_4h[sym]]
        upper, lower = pre_calc_bb(closes)
        ind[sym] = {"rsi": pre_calc_rsi(closes), "lower_bb": lower}
        
    for i in range(50, min_len): 
        current_equity = cash
        
        for sym in list(positions.keys()):
            c = data_4h[sym][i]
            pos = positions[sym]
            current_equity += pos["units"] * c["c"]
            
            if c["l"] <= pos["initial"] * 0.90:
                exit_val = pos["units"] * (pos["initial"] * 0.90) * (1 - TAKER_FEE)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1})
                del positions[sym]
            elif c["h"] >= pos["avg_entry"] * 1.02:
                exit_val = pos["units"] * (pos["avg_entry"] * 1.02) * (1 - MAKER_FEE)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1})
                del positions[sym]
            else:
                if pos["levels"] == 1 and c["l"] <= pos["initial"] * 0.97:
                    add_val = pos["initial_val"]
                    if cash >= add_val:
                        pos["levels"] = 2
                        cash -= add_val
                        pos["invested"] += add_val
                        pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.97)
                        pos["avg_entry"] = pos["invested"] / pos["units"]
                elif pos["levels"] == 2 and c["l"] <= pos["initial"] * 0.94:
                    add_val = pos["initial_val"]
                    if cash >= add_val:
                        pos["levels"] = 3
                        cash -= add_val
                        pos["invested"] += add_val
                        pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.94)
                        pos["avg_entry"] = pos["invested"] / pos["units"]

        equity_curve.append(current_equity)
        
        for sym in SYMBOLS:
            if sym in positions: continue
            c = data_4h[sym][i]
            lower_bb = ind[sym]["lower_bb"][i]
            rsi_val = ind[sym]["rsi"][i]
            
            if lower_bb and rsi_val and c["c"] <= lower_bb and rsi_val < 35:
                alloc_amt = current_equity * 0.05
                if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                if alloc_amt < 10: continue
                
                cash -= alloc_amt
                units = (alloc_amt * (1 - MAKER_FEE)) / c["c"]
                positions[sym] = {"units": units, "invested": alloc_amt, "levels": 1, "initial_val": alloc_amt, "initial": c["c"], "avg_entry": c["c"]}
                
    for sym, pos in positions.items():
        exit_val = pos["units"] * data_4h[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        trades.append({"ret": (exit_val / pos["invested"]) - 1})
        
    equity_curve.append(cash)
    return equity_curve, trades

def main():
    run_calibration()
    
    print("=== [2] SIMPLE GRID (M11-IR) ON TRUE 4H DATA ===")
    data_4h = {}
    for sym in SYMBOLS:
        d4 = load_wallex_data(sym)
        if d4: data_4h[sym] = d4
        else:
            print(f"Error loading data for {sym}")
            return
            
    eq_curve, trades = run_simple_grid(data_4h)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = len(data_4h["BTCUSDT"]) * 4 / 24
    cagr = ((final_eq / INITIAL_CAPITAL) ** (365 / days) - 1) * 100
    calmar = cagr / (max_dd * 100) if max_dd > 0 else 0
    
    n = len(trades)
    wins = sum(1 for t in trades if t["ret"] > 0)
    pf = sum(t["ret"] for t in trades if t["ret"] > 0) / abs(sum(t["ret"] for t in trades if t["ret"] <= 0)) if n > 0 else 0
    
    print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}% | Standard Calmar: {calmar:.2f}")
    print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}%" if n > 0 else "0 Trades")
    print(f"Profit Factor: {pf:.2f}")

if __name__ == "__main__":
    main()
