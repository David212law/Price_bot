import json
import os
import math
import random

# ─── Configuration (Exir Fees & Advanced Timing) ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0009  # 0.09% Exir Maker
TAKER_FEE = 0.0012  # 0.12% Exir Taker
DATA_DIR = "data_exir"
SYMBOLS = ["BTCUSDT", "ETHUSDT"] # فقط ارزهای با داده کافی در اکسیر
COOLDOWN_CANDLES = 6

# ─── Pre-calculators ───
def pre_calc_ema(closes, period):
    ema = [None] * len(closes)
    if len(closes) < period: return ema
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

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

def pre_calc_adx(candles, period=14):
    adx = [0.0] * len(candles)
    if len(candles) < period * 2: return adx
    trs, plus_dms, minus_dms = [0], [0], [0]
    for i in range(1, len(candles)):
        h, l, prev_h, prev_l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        up = h - prev_h
        down = prev_l - l
        plus_dms.append(up if (up > down and up > 0) else 0)
        minus_dms.append(down if (down > up and down > 0) else 0)
    smooth_tr = sum(trs[1:period+1])
    smooth_plus = sum(plus_dms[1:period+1])
    smooth_minus = sum(minus_dms[1:period+1])
    dxs = []
    for i in range(period, len(candles)):
        if i > period:
            smooth_tr = smooth_tr - (smooth_tr / period) + trs[i]
            smooth_plus = smooth_plus - (smooth_plus / period) + plus_dms[i]
            smooth_minus = smooth_minus - (smooth_minus / period) + minus_dms[i]
        if smooth_tr == 0: dx = 0
        else:
            di_plus = 100 * smooth_plus / smooth_tr
            di_minus = 100 * smooth_minus / smooth_tr
            if (di_plus + di_minus) == 0: dx = 0
            else: dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
        dxs.append(dx)
    first_adx = sum(dxs[:period]) / period
    adx[period * 2 - 1] = first_adx
    for i in range(period * 2, len(candles)):
        adx[i] = (adx[i-1] * (period - 1) + dxs[i - period]) / period
    return adx

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
def load_exir_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None, None
    with open(path, 'r') as f:
        candles_4h = json.load(f)
        
    # Aggregate to 1D (6 * 4H)
    candles_1d = []
    for i in range(0, len(candles_4h), 6):
        chunk = candles_4h[i:i+6]
        if not chunk: continue
        candles_1d.append({"t": chunk[0]["t"], "c": chunk[-1]["c"]})
    return candles_4h, candles_1d

# ─── Advanced Composite Engine ───
def run_advanced_backtest(data_4h, data_1d):
    cash = INITIAL_CAPITAL
    positions = {} # sym -> position dict
    cooldowns = {} # sym -> next_allowed_index
    trades = []
    equity_curve = []
    
    min_len = min(len(data_4h[s]) for s in SYMBOLS)
    for sym in SYMBOLS:
        data_4h[sym] = data_4h[sym][-min_len:]
        data_1d[sym] = data_1d[sym][-(min_len//6 + 1):]
        
    ind = {}
    for sym in SYMBOLS:
        closes_4h = [c["c"] for c in data_4h[sym]]
        closes_1d = [c["c"] for c in data_1d[sym]]
        upper, lower = pre_calc_bb(closes_4h)
        ind[sym] = {
            "rsi": pre_calc_rsi(closes_4h),
            "lower_bb": lower,
            "atr": pre_calc_atr(data_4h[sym]),
            "adx": pre_calc_adx(data_4h[sym]),
            "hh20": pre_calc_hh20(data_4h[sym]),
            "vol_sma": pre_calc_vol_sma(data_4h[sym]),
            "ema200_1d": pre_calc_ema(closes_1d, 200)
        }
        
    for i in range(200, min_len):
        daily_idx = min(i // 6, len(ind["BTCUSDT"]["ema200_1d"]) - 1)
        current_equity = cash
        
        # 1. Manage Active Positions
        for sym in list(positions.keys()):
            c = data_4h[sym][i]
            pos = positions[sym]
            current_equity += pos["units"] * c["c"]
            
            exit_triggered = False
            exit_fee = TAKER_FEE
            exit_price = c["c"]
            
            if pos["strat"] == "Grid":
                if c["l"] <= pos["initial"] * 0.90:
                    exit_triggered = True
                    exit_price = pos["initial"] * 0.90
                elif c["h"] >= pos["avg_entry"] * 1.02:
                    exit_triggered = True
                    exit_price = pos["avg_entry"] * 1.02
                    exit_fee = MAKER_FEE
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

            elif pos["strat"] == "Breakout":
                if c["l"] <= pos["sl"]:
                    exit_triggered = True
                    exit_price = pos["sl"]
                elif c["h"] >= pos["tp"]:
                    exit_triggered = True
                    exit_price = pos["tp"]

            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - exit_fee)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1, "strat": pos["strat"]})
                del positions[sym]
                cooldowns[sym] = i + COOLDOWN_CANDLES # Apply Cooldown
                
        equity_curve.append(current_equity)
        
        # 2. Entry Logic (Regime Based + Trend Filter + Lockout)
        btc_adx = ind["BTCUSDT"]["adx"][i]
        
        for sym in SYMBOLS:
            if sym in positions: continue # Symbol Lockout
            if i < cooldowns.get(sym, 0): continue # Cooldown check
            
            c = data_4h[sym][i]
            
            # --- RANGE REGIME -> GRID ---
            if btc_adx < 20:
                if c["c"] <= ind[sym]["lower_bb"][i] and ind[sym]["rsi"][i] < 35:
                    alloc_amt = current_equity * 0.05
                    if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                    if alloc_amt < 10: continue
                    
                    cash -= alloc_amt
                    units = (alloc_amt * (1 - MAKER_FEE)) / c["c"]
                    positions[sym] = {"strat": "Grid", "units": units, "invested": alloc_amt, "levels": 1, "initial_val": alloc_amt, "initial": c["c"], "avg_entry": c["c"]}
                    
            # --- TREND REGIME -> BREAKOUT (with Daily Trend Filter) ---
            elif btc_adx > 25:
                ema200_1d = ind[sym]["ema200_1d"][daily_idx]
                daily_close = data_1d[sym][daily_idx]["c"]
                
                if ema200_1d and daily_close > ema200_1d: # Must be in a macro uptrend
                    if c["c"] > ind[sym]["hh20"][i] and c["v"] > (1.5 * ind[sym]["vol_sma"][i]):
                        sl = c["c"] - (2 * ind[sym]["atr"][i])
                        tp = c["c"] + (4 * ind[sym]["atr"][i])
                        
                        alloc_amt = current_equity * 0.05
                        if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                        if alloc_amt < 10: continue
                        
                        cash -= alloc_amt
                        units = (alloc_amt * (1 - TAKER_FEE)) / c["c"]
                        positions[sym] = {"strat": "Breakout", "units": units, "invested": alloc_amt, "sl": sl, "tp": tp}

    for sym, pos in positions.items():
        exit_val = pos["units"] * data_4h[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        trades.append({"ret": (exit_val / pos["invested"]) - 1, "strat": pos["strat"]})
        
    equity_curve.append(cash)
    return equity_curve, trades

def main():
    print(f"=== M26: Advanced Composite (Exir) ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}%\n")
    print("Features: Strict Regime, Daily Trend Filter, Symbol Lockout, Cooldown\n")
    
    data_4h = {}
    data_1d = {}
    for sym in SYMBOLS:
        d4, d1 = load_exir_data(sym)
        if d4 and d1:
            data_4h[sym] = d4
            data_1d[sym] = d1
        else:
            print(f"Error loading data for {sym}")
            return
            
    print("Running Advanced Composite Backtest...")
    eq_curve, trades = run_advanced_backtest(data_4h, data_1d)
    
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
    if n == 0:
        print("No trades generated.")
        return
        
    wins = sum(1 for t in trades if t["ret"] > 0)
    pf = calculate_pf(trades)
    wilson = calculate_wilson_lower_bound(wins, n)
    pval = block_bootstrap_p_value(eq_curve)
    
    # Strategy Breakdown
    grid_trades = [t for t in trades if t["strat"] == "Grid"]
    brk_trades = [t for t in trades if t["strat"] == "Breakout"]
    
    print("\n=== FINAL RESULTS ===")
    print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}% | Standard Calmar: {calmar:.2f}")
    print(f"Total Trades: {n} | Win Rate: {(wins/n)*100:.2f}% | Wilson LB: {wilson:.2f}%")
    print(f"Profit Factor: {pf:.2f} | P-Value: {pval:.4f}")
    
    print("\n--- Strategy Breakdown ---")
    if grid_trades:
        g_wins = sum(1 for t in grid_trades if t["ret"] > 0)
        print(f"Grid: {len(grid_trades)} trades | WR: {(g_wins/len(grid_trades))*100:.1f}% | PF: {calculate_pf(grid_trades):.2f}")
    if brk_trades:
        b_wins = sum(1 for t in brk_trades if t["ret"] > 0)
        print(f"Breakout: {len(brk_trades)} trades | WR: {(b_wins/len(brk_trades))*100:.1f}% | PF: {calculate_pf(brk_trades):.2f}")
    
    passed = (n >= 50 and pf > 1.2 and calmar > 2.0 and max_dd < 0.30 and pval < 0.05)
    print(f"\nFinal Status (D-110 Iran Gate): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
