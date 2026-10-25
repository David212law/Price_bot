import json
import os
import math
import random

# ─── Configuration ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"
GRID_ASSETS = ["BTCUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"]
ALL_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"]

def load_candles(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

# ─── Indicators ───
def calc_sma(closes, period):
    sma = [None] * len(closes)
    s = 0
    for i in range(len(closes)):
        s += closes[i]
        if i >= period: s -= closes[i - period]
        if i >= period - 1: sma[i] = s / period
    return sma

def calc_std(closes, period, sma):
    std = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        mean = sma[i]
        variance = sum((x - mean) ** 2 for x in closes[i - period + 1:i + 1]) / period
        std[i] = variance ** 0.5
    return std

def calc_rsi(closes, period=14):
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

def calc_adx(candles, period=14):
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

# ─── Diagnostic Engine ───

def calculate_pf(trades):
    gross_profit = sum(t["ret"] for t in trades if t["ret"] > 0)
    gross_loss = abs(sum(t["ret"] for t in trades if t["ret"] <= 0))
    if gross_loss == 0: return 99.99
    return gross_profit / gross_loss

def block_bootstrap_p_value(equity_curve, block_size=6, iterations=500):
    if len(equity_curve) < block_size * 2: return 1.0
    rets = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i-1] > 0:
            rets.append((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1])
            
    actual_final = equity_curve[-1] / equity_curve[0]
    n_blocks = len(rets) // block_size
    better_than_actual = 0
    for _ in range(iterations):
        sampled_rets = []
        for _ in range(n_blocks):
            start_idx = random.randint(0, len(rets) - block_size)
            sampled_rets.extend(rets[start_idx:start_idx+block_size])
        sim_eq = 1.0
        for r in sampled_rets: sim_eq *= (1 + r)
        if sim_eq >= actual_final: better_than_actual += 1
    return better_than_actual / iterations

def run_grid_only(data, ind):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve_periodic = []
    
    min_len = len(data["BTCUSDT"])
    
    for i in range(100, min_len):
        btc_adx = ind["BTCUSDT"]["adx"][i]
        is_range_regime = btc_adx < 20
        
        current_equity = cash
        for sym in list(positions.keys()):
            c = data[sym][i]
            pos = positions[sym]
            current_equity += pos["units"] * c["c"] # Track floating PnL
            
            exit_triggered = False
            exit_fee = TAKER_FEE
            exit_price = c["c"]
            
            # Check SL (Low) BEFORE TP (High)
            if c["l"] <= pos["initial"] * 0.90:
                exit_triggered = True
                exit_price = pos["initial"] * 0.90
            elif c["h"] >= pos["avg_entry"] * 1.02:
                exit_triggered = True
                exit_price = pos["avg_entry"] * 1.02
                exit_fee = MAKER_FEE
            else:
                # DCA Levels (Maker)
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
            
            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - exit_fee)
                cash += exit_val
                trade_ret = (exit_val / pos["invested"]) - 1
                trades.append({"ret": trade_ret})
                del positions[sym]
                
        equity_curve_periodic.append(current_equity)
        
        # Open new Grid positions ONLY in RANGE regime
        if is_range_regime:
            for sym in GRID_ASSETS:
                if sym in positions: continue
                c = data[sym][i]
                
                # We use a fixed allocation of 5% of equity per Grid trade
                alloc_amt = current_equity * 0.05
                if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                if alloc_amt < 10: continue
                
                entry_triggered = False
                entry_price = c["c"]
                
                lower_bb = ind[sym]["lower_bb"][i]
                rsi_val = ind[sym]["rsi"][i]
                
                if lower_bb and rsi_val and c["c"] <= lower_bb and rsi_val < 35:
                    entry_triggered = True
                    
                if entry_triggered:
                    cash -= alloc_amt
                    units = (alloc_amt * (1 - MAKER_FEE)) / entry_price
                    positions[sym] = {
                        "units": units, "invested": alloc_amt, 
                        "initial": entry_price, "avg_entry": entry_price, 
                        "levels": 1, "initial_val": alloc_amt
                    }
                    
    for sym, pos in positions.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        trade_ret = (exit_val / pos["invested"]) - 1
        trades.append({"ret": trade_ret})
        
    equity_curve_periodic.append(cash)
    return equity_curve_periodic, trades

def main():
    print("=== Grid-Only Comprehensive Diagnostic Engine ===")
    
    data = {}
    ind = {}
    for sym in ALL_ASSETS:
        candles = load_candles(sym)
        if not candles: continue
        data[sym] = candles[-15000:] # Align lengths roughly
        closes = [x["c"] for x in data[sym]]
        sma20 = calc_sma(closes, 20)
        std20 = calc_std(closes, 20, sma20)
        
        upper_bb, lower_bb = [None]*len(closes), [None]*len(closes)
        for i in range(len(closes)):
            if sma20[i] and std20[i]:
                upper_bb[i] = sma20[i] + (2 * std20[i])
                lower_bb[i] = sma20[i] - (2 * std20[i])
                
        ind[sym] = {"rsi": calc_rsi(closes), "adx": calc_adx(data[sym]), "upper_bb": upper_bb, "lower_bb": lower_bb}
    
    min_len = min(len(data[s]) for s in ALL_ASSETS)
    for sym in ALL_ASSETS: 
        data[sym] = data[sym][-min_len:]
        ind[sym] = {k: v[-min_len:] for k, v in ind[sym].items()}
    
    print("Running Grid-Only backtest with floating equity tracking...")
    eq_curve, trades = run_grid_only(data, ind)
    
    # ─── METRICS CALCULATION ───
    final_eq = eq_curve[-1]
    total_ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = min_len * 4 / 24 # approx 2 years
    cagr = ((final_eq / INITIAL_CAPITAL) ** (365 / days) - 1) * 100
    standard_calmar = cagr / (max_dd * 100) if max_dd > 0 else 0
    
    print(f"\n=== GRID PORTFOLIO STATS ===")
    print(f"Total Return: {total_ret:.2f}% | CAGR: {cagr:.2f}%")
    print(f"MaxDD (incl. Floating): {max_dd*100:.2f}%")
    print(f"Standard Calmar (CAGR/MaxDD): {standard_calmar:.2f}")
    
    p_val = block_bootstrap_p_value(eq_curve)
    print(f"Block Bootstrap P-Value: {p_val:.4f}")
    
    n = len(trades)
    if n == 0: 
        print("No trades generated.")
        return
        
    wins = sum(1 for t in trades if t["ret"] > 0)
    pf = calculate_pf(trades)
    wilson = (wins/n) - 1.96 * math.sqrt((wins/n)*(1 - wins/n)/n)
    
    sorted_rets = sorted([t["ret"] for t in trades], reverse=True)
    pf_no_1 = calculate_pf([{"ret": r} for r in sorted_rets[1:]])
    pf_no_2 = calculate_pf([{"ret": r} for r in sorted_rets[2:]])
    
    print(f"\n=== TRADE BREAKDOWN ===")
    print(f"n={n} | WR={wins/n*100:.1f}% | Wilson LB={wilson*100:.2f}% | PF={pf:.2f}")
    print(f"PF without Top 1: {pf_no_1:.2f} | PF without Top 2: {pf_no_2:.2f}")
    
    passed = (standard_calmar > 2.0 and max_dd < 0.30 and n >= 50 and pf > 1.2 and p_val < 0.05)
    print(f"\nFinal Grid-Only Status (D-110): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
