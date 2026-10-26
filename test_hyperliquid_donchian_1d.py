import json
import os
import math
import random
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (Hyperliquid Donchian 1D) ───
INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0005  # 0.05%
DATA_DIR = "data_hyperliquid_1d"
SYMBOLS = ["BTC", "ETH", "SOL"]
DAYS = 730 # 2 years
INTERVAL = "1d"

# ─── Data Fetching (Hyperliquid 1D) ───
def fetch_hyperliquid_1d(symbol):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = f"{DATA_DIR}/{symbol}_1d.json"
    
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
            
    print(f"[{symbol}] Fetching 1D data from Hyperliquid...")
    all_candles = []
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (DAYS * 24 * 3600 * 1000)
    
    current_end = end_ms
    while current_end > start_ms:
        current_start = max(start_ms, current_end - (60 * 24 * 3600 * 1000)) # 60 days chunk
        url = "https://api.hyperliquid.xyz/info"
        payload = {
            "type": "candleSnapshot",
            "req": {"coin": symbol, "interval": INTERVAL, "startTime": current_start, "endTime": current_end}
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                raw_data = r.json()
                for c in raw_data:
                    all_candles.append({
                        "t": int(c["t"]),
                        "o": float(c["o"]),
                        "h": float(c["h"]),
                        "l": float(c["l"]),
                        "c": float(c["c"]),
                        "v": float(c["v"])
                    })
        except Exception as e:
            print(f"Error fetching chunk: {e}")
            break
        current_end = current_start
        time.sleep(0.5)
        
    unique = {c['t']: c for c in all_candles}
    sorted_candles = sorted(list(unique.values()), key=lambda x: x['t'])
    
    with open(filepath, 'w') as f:
        json.dump(sorted_candles, f)
        
    print(f"[{symbol}] Saved {len(sorted_candles)} candles.")
    return sorted_candles

# ─── Pre-calculators ───
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

def pre_calc_ll10(candles):
    ll10 = [None] * len(candles)
    for i in range(10, len(candles)):
        ll10[i] = min(x["l"] for x in candles[i-10:i])
    return ll10

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

def block_bootstrap_p_value(equity_curve, block_size=5, iterations=500):
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

# ─── Backtest Engine ───
def run_backtest(data):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve = []
    
    min_len = min(len(data[s]) for s in SYMBOLS)
    for sym in SYMBOLS:
        data[sym] = data[sym][-min_len:]
        
    ind = {}
    for sym in SYMBOLS:
        ind[sym] = {
            "atr": pre_calc_atr(data[sym]),
            "hh20": pre_calc_hh20(data[sym]),
            "ll10": pre_calc_ll10(data[sym])
        }
        
    for i in range(50, min_len): 
        current_equity = cash
        
        # 1. Manage Active Positions
        for sym in list(positions.keys()):
            c = data[sym][i]
            pos = positions[sym]
            current_equity += pos["units"] * c["c"]
            
            exit_triggered = False
            exit_price = c["c"]
            
            # Trailing Stop Logic
            if c["h"] > pos["highest"]:
                pos["highest"] = c["h"]
                atr_val = ind[sym]["atr"][i]
                if atr_val:
                    new_stop = pos["highest"] - (2.0 * atr_val)
                    if new_stop > pos["trailing_stop"]:
                        pos["trailing_stop"] = new_stop
                        
            # Check Exits: Trailing Stop or Close < LL10
            if c["l"] <= pos["trailing_stop"]:
                exit_triggered = True
                exit_price = pos["trailing_stop"]
            elif c["c"] < ind[sym]["ll10"][i]:
                exit_triggered = True
                exit_price = c["c"]
                
            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - TAKER_FEE)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1})
                del positions[sym]
                
        equity_curve.append(current_equity)
        
        # 2. Entry Logic
        for sym in SYMBOLS:
            if sym in positions: continue
            c = data[sym][i]
            
            if ind[sym]["hh20"][i] is None or ind[sym]["atr"][i] is None: continue
            
            # Donchian Breakout: Close > HH20
            if c["c"] > ind[sym]["hh20"][i]:
                alloc_amt = current_equity * 0.05
                if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                if alloc_amt < 10: continue
                
                cash -= alloc_amt
                units = (alloc_amt * (1 - TAKER_FEE)) / c["c"]
                
                positions[sym] = {
                    "units": units, "invested": alloc_amt,
                    "highest": c["c"], 
                    "trailing_stop": c["c"] - (2 * ind[sym]["atr"][i])
                }

    for sym, pos in positions.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        trades.append({"ret": (exit_val / pos["invested"]) - 1})
        
    equity_curve.append(cash)
    return equity_curve, trades

def main():
    print(f"=== M30: Hyperliquid Donchian 1D ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Taker: {TAKER_FEE*100}%\n")
    
    data = {}
    for sym in SYMBOLS:
        d1 = fetch_hyperliquid_1d(sym)
        if d1: data[sym] = d1
        else:
            print(f"Error loading data for {sym}")
            return
            
    print("Running Backtest...")
    eq_curve, trades = run_backtest(data)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = len(data["BTC"]) # 1D candles
    cagr = ((final_eq / INITIAL_CAPITAL) ** (365 / days) - 1) * 100 if days > 0 else 0
    calmar = cagr / (max_dd * 100) if max_dd > 0 else 0
    
    n = len(trades)
    if n == 0:
        print("No trades generated.")
        return
        
    wins = sum(1 for t in trades if t["ret"] > 0)
    pf = calculate_pf(trades)
    wilson = calculate_wilson_lower_bound(wins, n)
    pval = block_bootstrap_p_value(eq_curve)
    
    print("\n=== FINAL RESULTS ===")
    print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}% | Standard Calmar: {calmar:.2f}")
    print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}% | Wilson LB: {wilson:.2f}%")
    print(f"Profit Factor: {pf:.2f} | P-Value: {pval:.4f}")
    
    passed = (n >= 30 and pf > 1.2 and max_dd < 0.15 and calmar > 2.0 and pval < 0.05)
    print(f"\nFinal Status (D-68-Plus Crypto Gate): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
