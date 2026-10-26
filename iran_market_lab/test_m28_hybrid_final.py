import json
import os
import math
import random

# ─── Configuration (Hybrid: DCA 70% + Grid 30%) ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0009
TAKER_FEE = 0.0012
SLIPPAGE = 0.0005 # 0.05% Slippage/Spread
DATA_DIR = "data_tetri"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DCA_INTERVAL = 180 # 30 days * 6 (4h candles)

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

# ─── Data Loader ───
def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f:
        return json.load(f)

# ─── Hybrid Engine ───
def run_hybrid_backtest(data):
    # Bucket A: DCA (70%)
    cash_a = INITIAL_CAPITAL * 0.70
    holdings_a = {"BTCUSDT": 0.0, "ETHUSDT": 0.0}
    
    # Bucket B: Grid (30%)
    cash_b = INITIAL_CAPITAL * 0.30
    grid_positions = {}
    grid_loss_count = 0
    
    trades = []
    equity_curve = []
    
    min_len = min(len(data[s]) for s in SYMBOLS)
    for sym in SYMBOLS:
        data[sym] = data[sym][-min_len:]
        
    ind = {}
    for sym in SYMBOLS:
        closes = [c["c"] for c in data[sym]]
        upper, lower = pre_calc_bb(closes)
        ind[sym] = {"rsi": pre_calc_rsi(closes), "lower_bb": lower}
        
    for i in range(50, min_len): 
        # 1. Update Equity
        current_equity_a = cash_a + sum(holdings_a[s] * data[s][i]["c"] for s in SYMBOLS)
        current_equity_b = cash_b + sum(pos["units"] * data[s][i]["c"] for s, pos in grid_positions.items())
        total_equity = current_equity_a + current_equity_b
        
        # 2. Bucket A Logic: DCA every 30 days
        if i % DCA_INTERVAL == 0 and cash_a > 10:
            alloc_per_sym = cash_a / len(SYMBOLS)
            for sym in SYMBOLS:
                price = data[sym][i]["c"]
                # DCA usually uses Market/Taker
                fee = TAKER_FEE + SLIPPAGE
                units = (alloc_per_sym * (1 - fee)) / price
                holdings_a[sym] += units
            cash_a = 0.0 # Used all cash for this cycle (or keep if partial, here we use all)

        # 3. Bucket B Logic: Manage Grid Positions
        for sym in list(grid_positions.keys()):
            c = data[sym][i]
            pos = grid_positions[sym]
            
            exit_triggered = False
            exit_price = c["c"]
            exit_fee = TAKER_FEE + SLIPPAGE
            
            # Gap down over SL?
            if c["o"] <= pos["sl"]:
                exit_triggered = True
                exit_price = c["o"] # Filled at open
            elif c["l"] <= pos["sl"]:
                exit_triggered = True
                exit_price = pos["sl"]
            
            # Gap up over TP?
            elif c["o"] >= pos["tp"]:
                exit_triggered = True
                exit_price = c["o"]
                exit_fee = MAKER_FEE + SLIPPAGE # Gap up fills at open, could be Taker, but let's assume limit sell was hit
            elif c["h"] >= pos["tp"]:
                exit_triggered = True
                exit_price = pos["tp"]
                exit_fee = MAKER_FEE + SLIPPAGE
                
            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - exit_fee)
                cash_b += exit_val
                ret = (exit_val / pos["invested"]) - 1
                trades.append({"ret": ret, "strat": "Grid"})
                if ret <= 0:
                    grid_loss_count += 1
                else:
                    grid_loss_count = 0 # Reset on win
                del grid_positions[sym]

        # 4. Bucket B Logic: New Grid Entries
        for sym in SYMBOLS:
            if sym in grid_positions: continue
            c = data[sym][i]
            
            lower_bb = ind[sym]["lower_bb"][i]
            rsi_val = ind[sym]["rsi"][i]
            
            if lower_bb and rsi_val and c["c"] <= lower_bb and rsi_val < 35:
                # Dynamic Sizing based on Meta-Allocator
                if grid_loss_count >= 2:
                    alloc_pct = 0.15 # Halved risk
                else:
                    alloc_pct = 0.30 # Normal risk
                    
                alloc_amt = current_equity_b * alloc_pct
                if alloc_amt > cash_b * 0.95: alloc_amt = cash_b * 0.95
                if alloc_amt < 10: continue
                
                # Realistic Entry Execution
                entry_price = c["c"]
                entry_fee = MAKER_FEE + SLIPPAGE
                
                # If open gaps below BB, we fill at open as Taker
                if c["o"] <= lower_bb:
                    entry_price = c["o"]
                    entry_fee = TAKER_FEE + SLIPPAGE
                    
                tp = entry_price * 1.05 # +5% TP
                sl = entry_price * 0.70 # -30% SL
                
                cash_b -= alloc_amt
                units = (alloc_amt * (1 - entry_fee)) / entry_price
                grid_positions[sym] = {"units": units, "invested": alloc_amt, "tp": tp, "sl": sl}
                
        equity_curve.append(total_equity)

    # Close remaining Grid positions at the end
    for sym, pos in grid_positions.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - (TAKER_FEE + SLIPPAGE))
        cash_b += exit_val
        trades.append({"ret": (exit_val / pos["invested"]) - 1, "strat": "Grid"})
        
    final_equity = cash_a + sum(holdings_a[s] * data[s][min_len-1]["c"] for s in SYMBOLS) + cash_b
    equity_curve.append(final_equity)
    
    return equity_curve, trades, current_equity_a, cash_b

def main():
    print(f"=== M28: Hybrid DCA (70%) + Grid (30%) on EXIR/WALLEX ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}% | Slippage: {SLIPPAGE*100}%\n")
    
    data = {}
    for sym in SYMBOLS:
        d4 = load_data(sym)
        if d4: data[sym] = d4
        else:
            print(f"Error loading data for {sym}")
            return
            
    print("Running Hybrid Backtest with Realistic Execution...")
    eq_curve, trades, final_a, final_b = run_hybrid_backtest(data)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = len(data["BTCUSDT"]) * 4 / 24
    cagr = ((final_eq / INITIAL_CAPITAL) ** (365 / days) - 1) * 100
    calmar = cagr / (max_dd * 100) if max_dd > 0 else 0
    
    n = len(trades)
    if n == 0:
        print("No Grid trades generated.")
    else:
        wins = sum(1 for t in trades if t["ret"] > 0)
        pf = calculate_pf(trades)
        print("\n=== FINAL RESULTS ===")
        print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
        print(f"MaxDD: {max_dd*100:.2f}% | Standard Calmar: {calmar:.2f}")
        print(f"Grid Trades: {n} | Win Rate: {(wins/n)*100:.2f}% | PF: {pf:.2f}")
        print(f"Final Bucket A (DCA): {final_a:.2f} USDT")
        print(f"Final Bucket B (Grid): {final_b:.2f} USDT")

if __name__ == "__main__":
    main()
