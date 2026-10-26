import json
import os
import math
import random
import requests
import time
import sys

# ─── Configuration (Locked Parameters from D-66) ───
INITIAL_CAPITAL = 10000.0
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "TRXUSDT"]
HEADERS = {"User-Agent": "Mozilla/5.0"}

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

# ─── Data Loaders ───
def fetch_binance_data(symbol):
    candles_4h = []
    end_time = int(time.time() * 1000)
    while len(candles_4h) < 4380:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=4h&limit=1000&endTime={end_time}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for k in data:
                    candles_4h.append({"t": int(k[0]), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])})
                end_time = data[0][0] - 1
            else: break
        except: break
        time.sleep(0.1)
        
    candles_1d = []
    end_time = int(time.time() * 1000)
    while len(candles_1d) < 730:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1d&limit=1000&endTime={end_time}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for k in data:
                    candles_1d.append({"t": int(k[0]), "c": float(k[4])})
                end_time = data[0][0] - 1
            else: break
        except: break
        time.sleep(0.1)
    return sorted(candles_4h, key=lambda x: x['t']), sorted(candles_1d, key=lambda x: x['t'])

def load_wallex_data(symbol):
    path = f"iran_market_lab/data_tetri/{symbol}_4h.json"
    if not os.path.exists(path): return None, None
    with open(path, 'r') as f:
        candles_4h = json.load(f)
        
    candles_1d = []
    for i in range(0, len(candles_4h), 6):
        chunk = candles_4h[i:i+6]
        if not chunk: continue
        candles_1d.append({"t": chunk[0]["t"], "c": chunk[-1]["c"]})
    return candles_4h, candles_1d

# ─── Backtest Engine (Limit Order Simulation) ───
def run_backtest(data_4h, data_1d, maker_fee, taker_fee):
    cash = INITIAL_CAPITAL
    positions = {}
    active_orders = {} # Tracking limit orders waiting to be filled
    trades = []
    equity_curve = []
    
    min_len = min(len(data_4h[s]) for s in SYMBOLS)
    for sym in SYMBOLS:
        data_4h[sym] = data_4h[sym][-min_len:]
        data_1d[sym] = data_1d[sym][-(min_len//6 + 1):]
        
    # Pre-calculate indicators
    ind = {}
    for sym in SYMBOLS:
        closes_4h = [c["c"] for c in data_4h[sym]]
        closes_1d = [c["c"] for c in data_1d[sym]]
        upper, lower = pre_calc_bb(closes_4h)
        ind[sym] = {
            "atr": pre_calc_atr(data_4h[sym]),
            "lower_bb": lower,
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
            
            # Check SL first (Taker)
            if c["l"] <= pos["sl"]:
                exit_val = pos["units"] * pos["sl"] * (1 - taker_fee)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1})
                del positions[sym]
            # Check TP (Maker)
            elif c["h"] >= pos["tp"]:
                exit_val = pos["units"] * pos["tp"] * (1 - maker_fee)
                cash += exit_val
                trades.append({"ret": (exit_val / pos["invested"]) - 1})
                del positions[sym]
                
        # 2. Manage Active Limit Orders
        for sym in list(active_orders.keys()):
            order = active_orders[sym]
            c = data_4h[sym][i]
            
            # Fill Check (Did price drop to our limit price?)
            if c["l"] <= order["limit_price"]:
                alloc_amt = order["alloc_amt"]
                cash -= alloc_amt
                # Entry with Maker Fee
                units = (alloc_amt * (1 - maker_fee)) / order["limit_price"]
                positions[sym] = {"units": units, "invested": alloc_amt, "sl": order["sl"], "tp": order["tp"]}
                del active_orders[sym]
            else:
                # Time-in-Force (TIF) expiry
                order["tif"] -= 1
                if order["tif"] <= 0:
                    del active_orders[sym]
                    
        equity_curve.append(current_equity)
        
        # 3. Signal Generation (New Limit Orders)
        for sym in SYMBOLS:
            if sym in positions or sym in active_orders: continue
            
            c = data_4h[sym][i]
            ema200 = ind[sym]["ema200_1d"][daily_idx]
            if ema200 is None: continue
            
            # Condition 1: 1D Trend Filter
            daily_close = data_1d[sym][daily_idx]["c"]
            if daily_close <= ema200: continue
            
            # Condition 2: Signal Candle (We look at previous candle to set limit order for NEXT candles)
            prev_c = data_4h[sym][i-1]
            prev_lower_bb = ind[sym]["lower_bb"][i-1]
            prev_atr = ind[sym]["atr"][i-1]
            
            if prev_lower_bb and prev_atr:
                limit_price = prev_lower_bb
                sl = limit_price - (2 * prev_atr)
                tp = limit_price + (4 * prev_atr)
                
                alloc_amt = current_equity * 0.05
                if alloc_amt > cash * 0.95: alloc_amt = cash * 0.95
                if alloc_amt < 10: continue
                
                active_orders[sym] = {
                    "limit_price": limit_price,
                    "sl": sl,
                    "tp": tp,
                    "alloc_amt": alloc_amt,
                    "tif": 5 # 5 Candles to live
                }
                
    for sym, pos in positions.items():
        exit_val = pos["units"] * data_4h[sym][min_len-1]["c"] * (1 - maker_fee)
        cash += exit_val
        trades.append({"ret": (exit_val / pos["invested"]) - 1})
        
    equity_curve.append(cash)
    return equity_curve, trades

def evaluate_wf(data_4h, data_1d, maker_fee, taker_fee):
    window_size = len(data_4h["BTCUSDT"]) // 4
    profitable = 0
    for w in range(4):
        start = w * window_size
        end = start + window_size if w < 3 else len(data_4h["BTCUSDT"])
        sub_4h = {sym: data_4h[sym][start:end] for sym in SYMBOLS}
        sub_1d = {sym: data_1d[sym][start//6:end//6+1] for sym in SYMBOLS}
        
        eq, _ = run_backtest(sub_4h, sub_1d, maker_fee, taker_fee)
        if eq[-1] > eq[0]: profitable += 1
    return profitable >= 3

def main():
    market = sys.argv[1] if len(sys.argv) > 1 else "wallex"
    maker_fee = 0.0010
    taker_fee = 0.0013 if market == "wallex" else 0.0010
    
    print(f"=== M14: Maker Trend Pullback ({market.upper()}) ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Maker: {maker_fee*100}% | Taker: {taker_fee*100}%\n")
    
    data_4h = {}
    data_1d = {}
    
    for sym in SYMBOLS:
        print(f"Loading {sym}...")
        if market == "wallex":
            d4, d1 = load_wallex_data(sym)
        else:
            d4, d1 = fetch_binance_data(sym)
            
        if d4 and d1:
            data_4h[sym] = d4
            data_1d[sym] = d1
        else:
            print(f"Error loading data for {sym}")
            return
            
    print("Running Backtest (Limit Order Simulation)...")
    eq_curve, trades = run_backtest(data_4h, data_1d, maker_fee, taker_fee)
    
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
        print("No trades generated. Strategy conditions not met.")
        return
        
    wins = sum(1 for t in trades if t["ret"] > 0)
    pf = calculate_pf(trades)
    wilson = calculate_wilson_lower_bound(wins, n)
    pval = block_bootstrap_p_value(eq_curve)
    
    print("Running Walk-Forward...")
    wf_passed = evaluate_wf(data_4h, data_1d, maker_fee, taker_fee)
    
    print("\n=== FINAL RESULTS ===")
    print(f"Total Return: {ret:.2f}% | CAGR: {cagr:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}% | Standard Calmar: {calmar:.2f}")
    print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}% | Wilson LB: {wilson:.2f}%")
    print(f"Profit Factor: {pf:.2f} | P-Value: {pval:.4f}")
    print(f"Walk-Forward (3/4): {'PASS' if wf_passed else 'FAIL'}")
    
    if market == "wallex":
        passed = (n >= 50 and pf > 1.2 and calmar > 2.0 and max_dd < 0.30 and wf_passed)
    else:
        passed = (n >= 30 and pf > 1.2 and calmar > 2.0 and max_dd < 0.15 and pval < 0.05 and wf_passed)
        
    print(f"\nFinal Status (Gate): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
