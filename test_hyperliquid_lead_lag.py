import json
import os
import math
import random
from datetime import datetime, timezone

# ─── Configuration (M32 Lead-Lag) ───
INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0005 # 0.05%
LEADER = "BTC"
FOLLOWERS = ["ETH", "SOL", "BNB", "XRP", "AVAX"]
DATA_DIR = "data_hyperliquid"

LEADER_RET_THRESHOLD = 0.025  # 2.5%
TP_PCT = 0.025                # 2.5%
SL_PCT = 0.015                # 1.5%
TIME_CAP_CANDLES = 3          # 12 hours
MAX_POSITIONS = 3
RISK_PER_TRADE = 0.05

# ─── Data Loading ───
def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

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

# ─── Backtest Engine (Window-based) ───
def run_window(data, start_idx, end_idx):
    cash = INITIAL_CAPITAL
    positions = {} # symbol -> dict
    trades = []
    equity_curve = []
    
    leader_candles = data[LEADER][start_idx:end_idx]
    
    for i in range(1, len(leader_candles)):
        current_equity = cash
        
        # 1. Manage Active Positions
        for sym in list(positions.keys()):
            pos = positions[sym]
            pos_idx = pos["entry_idx"]
            
            # Get follower candle at current index (relative to window)
            f_candles = data[sym][start_idx:end_idx]
            if i >= len(f_candles): continue
            c = f_candles[i]
            
            current_equity += pos["units"] * c["c"] if pos["side"] == "LONG" else pos["units"] * (2*pos["entry_price"] - c["c"])
            
            exit_triggered = False
            exit_price = c["c"]
            reason = ""
            
            # Time Cap
            if (i - pos_idx) >= TIME_CAP_CANDLES:
                exit_triggered = True
                reason = "TIME_CAP"
            
            # Long Exits
            elif pos["side"] == "LONG":
                if c["l"] <= pos["sl"]:
                    exit_triggered = True
                    exit_price = pos["sl"]
                    reason = "SL"
                elif c["h"] >= pos["tp"]:
                    exit_triggered = True
                    exit_price = pos["tp"]
                    reason = "TP"
            
            # Short Exits
            elif pos["side"] == "SHORT":
                if c["h"] >= pos["sl"]:
                    exit_triggered = True
                    exit_price = pos["sl"]
                    reason = "SL"
                elif c["l"] <= pos["tp"]:
                    exit_triggered = True
                    exit_price = pos["tp"]
                    reason = "TP"
                    
            if exit_triggered:
                if pos["side"] == "LONG":
                    ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                else: # SHORT
                    ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                    
                cash += pos["invested"] * (1 + ret)
                trades.append({"ret": ret, "side": pos["side"]})
                del positions[sym]
        
        equity_curve.append(current_equity)
        
        # 2. Signal Generation (based on PREVIOUS leader candle)
        prev_leader_c = leader_candles[i-1]
        prev_leader_c2 = leader_candles[i-2]
        
        leader_ret = (prev_leader_c["c"] - prev_leader_c2["c"]) / prev_leader_c2["c"]
        
        if abs(leader_ret) >= LEADER_RET_THRESHOLD:
            side = "LONG" if leader_ret > 0 else "SHORT"
            
            for sym in FOLLOWERS:
                if sym in positions: continue
                if len(positions) >= MAX_POSITIONS: break
                
                f_candles = data[sym][start_idx:end_idx]
                if i >= len(f_candles): continue
                
                current_c = f_candles[i] # Entry at current Open
                entry_price = current_c["o"]
                
                alloc_amt = current_equity * RISK_PER_TRADE
                if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                if alloc_amt < 10: continue
                
                if side == "LONG":
                    tp = entry_price * (1 + TP_PCT)
                    sl = entry_price * (1 - SL_PCT)
                else:
                    tp = entry_price * (1 - TP_PCT)
                    sl = entry_price * (1 + SL_PCT)
                    
                cash -= alloc_amt
                units = alloc_amt / entry_price # 1x leverage effectively (simplification)
                
                positions[sym] = {
                    "side": side, "entry_price": entry_price, "units": units,
                    "invested": alloc_amt, "sl": sl, "tp": tp, "entry_idx": i
                }
                
    # Force close
    for sym, pos in positions.items():
        f_candles = data[sym][start_idx:end_idx]
        exit_price = f_candles[-1]["c"]
        if pos["side"] == "LONG":
            ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
        else:
            ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
        cash += pos["invested"] * (1 + ret)
        trades.append({"ret": ret, "side": pos["side"]})
        
    equity_curve.append(cash)
    return equity_curve, trades

def main():
    print(f"=== M32: Hyperliquid Lead-Lag ===")
    print(f"Leader: {LEADER} | Followers: {FOLLOWERS}")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Fee: {TAKER_FEE*100}%\n")
    
    data = {}
    for sym in [LEADER] + FOLLOWERS:
        d = load_data(sym)
        if d: 
            data[sym] = d
        else:
            print(f"Missing data for {sym}")
            return
            
    # Align data lengths (trim to shortest)
    min_len = min(len(data[s]) for s in data)
    for s in data: data[s] = data[s][-min_len:]
    
    print("Running Full Backtest...")
    eq_curve, trades = run_window(data, 0, min_len)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = min_len * 4 / 24
    cagr = ((final_eq / INITIAL_CAPITAL) ** (365 / days) - 1) * 100 if days > 0 else 0
    calmar = cagr / (max_dd * 100) if max_dd > 0 else 0
    
    n = len(trades)
    if n > 0:
        wins = sum(1 for t in trades if t["ret"] > 0)
        pf = calculate_pf(trades)
        wilson = calculate_wilson_lower_bound(wins, n)
        pval = block_bootstrap_p_value(eq_curve)
        
        print("\n=== FULL RESULTS ===")
        print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
        print(f"MaxDD: {max_dd*100:.2f}% | Calmar: {calmar:.2f}")
        print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}% | Wilson LB: {wilson:.2f}%")
        print(f"Profit Factor: {pf:.2f} | P-Value: {pval:.4f}")
    else:
        print("\nNo trades generated in full window.")

    # Walk-Forward
    print("\nRunning Walk-Forward (4 Windows)...")
    window_size = min_len // 4
    profitable = 0
    for w in range(4):
        start = w * window_size
        end = start + window_size if w < 3 else min_len
        sub_eq, sub_trades = run_window(data, start, end)
        w_ret = ((sub_eq[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
        if w_ret > 0: profitable += 1
        print(f"  Window {w+1}: Return={w_ret:.2f}% | Trades={len(sub_trades)}")
        
    passed = (n >= 30 and ret > 0 and max_dd < 0.15 and calmar > 2.0 and profitable >= 3)
    print(f"\nFinal Status (D-68-Plus + WF 3/4): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
