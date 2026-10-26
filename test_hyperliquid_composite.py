import json
import os
import math
import random
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (Hyperliquid) ───
INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0005  # 0.05%
MAKER_FEE = 0.0002  # 0.02%
DATA_DIR = "data_hyperliquid"
SYMBOLS = ["BTC", "ETH", "SOL"]
DAYS = 730 # 2 years
INTERVAL = "4h"

# ─── Data Fetching (Hyperliquid) ───
def fetch_hyperliquid_data(symbol):
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = f"{DATA_DIR}/{symbol}.json"
    
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
            
    print(f"[{symbol}] Fetching 4H data from Hyperliquid...")
    all_candles = []
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (DAYS * 24 * 3600 * 1000)
    
    # Hyperliquid API may limit maximum lookback per request. We fetch in chunks.
    current_end = end_ms
    while current_end > start_ms:
        current_start = max(start_ms, current_end - (30 * 24 * 3600 * 1000)) # 30 days chunk
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
        time.sleep(0.5) # Rate limit
        
    # Sort and deduplicate
    unique = {c['t']: c for c in all_candles}
    sorted_candles = sorted(list(unique.values()), key=lambda x: x['t'])
    
    with open(filepath, 'w') as f:
        json.dump(sorted_candles, f)
        
    print(f"[{symbol}] Saved {len(sorted_candles)} candles.")
    return sorted_candles

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

# ─── Composite Engine ───
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
        closes = [c["c"] for c in data[sym]]
        upper, lower = pre_calc_bb(closes)
        ind[sym] = {
            "rsi": pre_calc_rsi(closes),
            "lower_bb": lower,
            "atr": pre_calc_atr(data[sym]),
            "adx": pre_calc_adx(data[sym]),
            "hh20": pre_calc_hh20(data[sym])
        }
        
    for i in range(50, min_len): 
        current_equity = cash
        
        # 1. Manage Active Positions
        for sym in list(positions.keys()):
            c = data[sym][i]
            pos = positions[sym]
            current_equity += pos["units"] * c["c"]
            
            exit_triggered = False
            exit_fee = TAKER_FEE
            exit_price = c["c"]
            
            if pos["strat"] == "M9":
                if c["l"] <= pos["sl"]:
                    exit_triggered = True
                    exit_price = pos["sl"]
                elif c["h"] >= pos["tp"]:
                    exit_triggered = True
                    exit_price = pos["tp"]
                    exit_fee = MAKER_FEE # TP is Limit
            elif pos["strat"] == "Donchian":
                # Trailing Stop Logic
                if c["h"] > pos["highest"]:
                    pos["highest"] = c["h"]
                    atr_val = ind[sym]["atr"][i]
                    if atr_val:
                        new_stop = pos["highest"] - (2.0 * atr_val)
                        if new_stop > pos["trailing_stop"]:
                            pos["trailing_stop"] = new_stop
                            
                if c["l"] <= pos["trailing_stop"]:
                    exit_triggered = True
                    exit_price = pos["trailing_stop"]

            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - exit_fee)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1, "strat": pos["strat"]})
                del positions[sym]
                
        equity_curve.append(current_equity)
        
        # 2. Entry Logic
        btc_adx = ind["BTC"]["adx"][i]
        
        for sym in SYMBOLS:
            if sym in positions: continue
            c = data[sym][i]
            
            alloc_amt = current_equity * 0.05
            if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
            if alloc_amt < 10: continue
            
            # RANGE REGIME -> M9 (Mean Reversion)
            if btc_adx < 20:
                if c["c"] <= ind[sym]["lower_bb"][i] and ind[sym]["rsi"][i] < 35:
                    sl = c["c"] - (2 * ind[sym]["atr"][i])
                    tp = c["c"] + (4 * ind[sym]["atr"][i])
                    cash -= alloc_amt
                    units = (alloc_amt * (1 - TAKER_FEE)) / c["c"]
                    positions[sym] = {"strat": "M9", "units": units, "invested": alloc_amt, "sl": sl, "tp": tp}
                    
            # TREND REGIME -> Donchian Breakout
            elif btc_adx > 25:
                if c["c"] > ind[sym]["hh20"][i]:
                    atr_val = ind[sym]["atr"][i]
                    if atr_val:
                        cash -= alloc_amt
                        units = (alloc_amt * (1 - TAKER_FEE)) / c["c"]
                        positions[sym] = {
                            "strat": "Donchian", "units": units, "invested": alloc_amt,
                            "highest": c["c"], "trailing_stop": c["c"] - (2 * atr_val)
                        }

    # Close remaining
    for sym, pos in positions.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        trades.append({"ret": (exit_val / pos["invested"]) - 1, "strat": pos["strat"]})
        
    equity_curve.append(cash)
    return equity_curve, trades

def main():
    print(f"=== M29: Hyperliquid Composite (Trend + Reversion) ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}%\n")
    
    data = {}
    for sym in SYMBOLS:
        d4 = fetch_hyperliquid_data(sym)
        if d4: data[sym] = d4
        else:
            print(f"Error loading data for {sym}")
            return
            
    print("Running Composite Backtest...")
    eq_curve, trades = run_backtest(data)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = len(data["BTC"]) * 4 / 24
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
    
    # Strategy Breakdown
    m9_trades = [t for t in trades if t["strat"] == "M9"]
    don_trades = [t for t in trades if t["strat"] == "Donchian"]
    
    print("\n=== FINAL RESULTS ===")
    print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}% | Standard Calmar: {calmar:.2f}")
    print(f"Total Trades: {n} | Win Rate: {(wins/n)*100:.2f}% | Wilson LB: {wilson:.2f}%")
    print(f"Profit Factor: {pf:.2f} | P-Value: {pval:.4f}")
    
    print("\n--- Strategy Breakdown ---")
    if m9_trades:
        g_wins = sum(1 for t in m9_trades if t["ret"] > 0)
        print(f"M9 (Range): {len(m9_trades)} trades | WR: {(g_wins/len(m9_trades))*100:.1f}% | PF: {calculate_pf(m9_trades):.2f}")
    if don_trades:
        b_wins = sum(1 for t in don_trades if t["ret"] > 0)
        print(f"Donchian (Trend): {len(don_trades)} trades | WR: {(b_wins/len(don_trades))*100:.1f}% | PF: {calculate_pf(don_trades):.2f}")
    
    passed = (n >= 30 and pf > 1.2 and max_dd < 0.15 and calmar > 2.0 and pval < 0.05)
    print(f"\nFinal Status (D-68-Plus Crypto Gate): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
