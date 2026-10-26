import json
import os
import math
import random

# ─── Configuration (Exir Fees & Split Portfolios) ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0009  # 0.09% Exir Maker
TAKER_FEE = 0.0012  # 0.12% Exir Taker
DATA_DIR = "data_exir"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# ─── Pre-calculators ───
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

def pre_calc_atr(candles, period=14):
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

def pre_calc_hh20(candles):
    hh20 = [None] * len(candles)
    for i in range(20, len(candles)):
        hh20[i] = max(x["h"] for x in candles[i-20:i])
    return hh20

def pre_calc_vol_sma(candles, period=20):
    vol_sma = [None] * len(candles)
    for i in range(period, len(candles)):
        vol_sma[i] = sum(x["v"] for x in candles[i-period:i]) / period
    return vol_sma

# ─── Metrics ───
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

# ─── Data Loader ───
def load_exir_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f:
        return json.load(f)

# ─── Backtest Engine (Split Portfolios) ───
def run_split_backtest(data):
    # Separate accounts
    cash_grid = INITIAL_CAPITAL / 2
    cash_brk = INITIAL_CAPITAL / 2
    pos_grid = {}
    pos_brk = {}
    
    trades_grid = []
    trades_brk = []
    eq_curve_grid = []
    eq_curve_brk = []
    
    min_len = min(len(data[s]) for s in SYMBOLS)
    for sym in SYMBOLS:
        data[sym] = data[sym][-min_len:]
        
    ind = {}
    for sym in SYMBOLS:
        closes = [c["c"] for c in data[sym]]
        upper, lower = pre_calc_bb(closes)
        ind[sym] = {
            "rsi": pre_calc_rsi(closes),
            "lower_bb": lower,
            "atr": pre_calc_atr(data[sym]),
            "hh20": pre_calc_hh20(data[sym]),
            "vol_sma": pre_calc_vol_sma(data[sym])
        }
        
    for i in range(50, min_len): 
        # --- Manage Grid Portfolio ---
        current_eq_grid = cash_grid
        for sym in list(pos_grid.keys()):
            c = data[sym][i]
            pos = pos_grid[sym]
            current_eq_grid += pos["units"] * c["c"]
            
            if c["l"] <= pos["initial"] * 0.90:
                exit_val = pos["units"] * (pos["initial"] * 0.90) * (1 - TAKER_FEE)
                cash_grid += exit_val
                trades_grid.append({"ret": (exit_val / pos["invested"]) - 1})
                del pos_grid[sym]
            elif c["h"] >= pos["avg_entry"] * 1.02:
                exit_val = pos["units"] * (pos["avg_entry"] * 1.02) * (1 - MAKER_FEE)
                cash_grid += exit_val
                trades_grid.append({"ret": (exit_val / pos["invested"]) - 1})
                del pos_grid[sym]
            else:
                if pos["levels"] == 1 and c["l"] <= pos["initial"] * 0.97:
                    add_val = pos["initial_val"]
                    if cash_grid >= add_val:
                        pos["levels"] = 2
                        cash_grid -= add_val
                        pos["invested"] += add_val
                        pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.97)
                        pos["avg_entry"] = pos["invested"] / pos["units"]
                elif pos["levels"] == 2 and c["l"] <= pos["initial"] * 0.94:
                    add_val = pos["initial_val"]
                    if cash_grid >= add_val:
                        pos["levels"] = 3
                        cash_grid -= add_val
                        pos["invested"] += add_val
                        pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.94)
                        pos["avg_entry"] = pos["invested"] / pos["units"]
        eq_curve_grid.append(current_eq_grid)

        # --- Manage Breakout Portfolio ---
        current_eq_brk = cash_brk
        for sym in list(pos_brk.keys()):
            c = data[sym][i]
            pos = pos_brk[sym]
            current_eq_brk += pos["units"] * c["c"]
            
            if c["l"] <= pos["sl"]:
                exit_val = pos["units"] * pos["sl"] * (1 - TAKER_FEE)
                cash_brk += exit_val
                trades_brk.append({"ret": (exit_val / pos["invested"]) - 1})
                del pos_brk[sym]
            elif c["h"] >= pos["tp"]:
                exit_val = pos["units"] * pos["tp"] * (1 - TAKER_FEE)
                cash_brk += exit_val
                trades_brk.append({"ret": (exit_val / pos["invested"]) - 1})
                del pos_brk[sym]
        eq_curve_brk.append(current_eq_brk)

        # --- Entry Signals ---
        for sym in SYMBOLS:
            c = data[sym][i]
            
            # Grid Entry
            if sym not in pos_grid:
                if c["c"] <= ind[sym]["lower_bb"][i] and ind[sym]["rsi"][i] < 35:
                    alloc = current_eq_grid * 0.1 # 10% of Grid portfolio
                    if alloc <= cash_grid * 0.95 and alloc > 10:
                        cash_grid -= alloc
                        units = (alloc * (1 - MAKER_FEE)) / c["c"]
                        pos_grid[sym] = {"units": units, "invested": alloc, "levels": 1, "initial_val": alloc, "initial": c["c"], "avg_entry": c["c"]}
            
            # Breakout Entry
            if sym not in pos_brk:
                if c["c"] > ind[sym]["hh20"][i] and c["v"] > (1.5 * ind[sym]["vol_sma"][i]):
                    sl = c["c"] - (2 * ind[sym]["atr"][i])
                    tp = c["c"] + (4 * ind[sym]["atr"][i])
                    alloc = current_eq_brk * 0.1 # 10% of Breakout portfolio
                    if alloc <= cash_brk * 0.95 and alloc > 10:
                        cash_brk -= alloc
                        units = (alloc * (1 - TAKER_FEE)) / c["c"]
                        pos_brk[sym] = {"units": units, "invested": alloc, "sl": sl, "tp": tp}

    # Close remaining
    for sym, pos in pos_grid.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash_grid += exit_val
        trades_grid.append({"ret": (exit_val / pos["invested"]) - 1})
    for sym, pos in pos_brk.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash_brk += exit_val
        trades_brk.append({"ret": (exit_val / pos["invested"]) - 1})

    return eq_curve_grid, trades_grid, eq_curve_brk, trades_brk

def main():
    print(f"=== M25: Split Portfolios (Grid + Breakout) on EXIR ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT (Split 50/50) | Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}%\n")
    
    data = {}
    for sym in SYMBOLS:
        d4 = load_exir_data(sym)
        if d4: data[sym] = d4
        else:
            print(f"Error loading data for {sym}")
            return
            
    print("Running Split Backtest...")
    eq_g, tr_g, eq_b, tr_b = run_split_backtest(data)
    
    # Combine equity curves
    total_eq = [eq_g[i] + eq_b[i] for i in range(len(eq_g))]
    final_eq = total_eq[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = total_eq[0]
    max_dd = 0.0
    for val in total_eq:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    all_trades = tr_g + tr_b
    n = len(all_trades)
    wins = sum(1 for t in all_trades if t["ret"] > 0)
    
    print("\n=== FINAL RESULTS (Combined) ===")
    print(f"Total Return: {ret:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}%")
    print(f"Total Trades: {n} | Win Rate: {(wins/n)*100:.2f}%")
    print(f"Profit Factor: {calculate_pf(all_trades):.2f}")
    
    print("\n--- Strategy Breakdown ---")
    if tr_g:
        print(f"Grid Portfolio Return: {((eq_g[-1] - 5000)/5000)*100:.2f}% | PF: {calculate_pf(tr_g):.2f} | Trades: {len(tr_g)}")
    if tr_b:
        print(f"Breakout Portfolio Return: {((eq_b[-1] - 5000)/5000)*100:.2f}% | PF: {calculate_pf(tr_b):.2f} | Trades: {len(tr_b)}")

if __name__ == "__main__":
    main()
