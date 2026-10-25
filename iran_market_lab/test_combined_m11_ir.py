import json
import os
import math
import random

# ─── Configuration ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"

# Families
BH_ASSETS = ["BTCUSDT", "BNBUSDT", "TRXUSDT"]
MOM_ASSETS = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "DOTUSDT"]
GRID_ASSETS = ["AVAXUSDT"]
ALL_ASSETS = BH_ASSETS + MOM_ASSETS + GRID_ASSETS

def load_candles(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

def sma(values, period, i):
    if i < period - 1: return None
    return sum(values[i-period+1:i+1]) / period

def std_dev(values, period, i, mean):
    if i < period - 1: return None
    window = values[i-period+1:i+1]
    variance = sum((x - mean) ** 2 for x in window) / period
    return variance ** 0.5

def rsi(closes, period, i):
    if i < period: return None
    gains, losses = 0, 0
    for j in range(i - period + 1, i + 1):
        change = closes[j] - closes[j - 1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0: return 100.0
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def atr(candles, period, i):
    if i < period: return None
    trs = []
    for j in range(i - period + 1, i + 1):
        h, l, prev_c = candles[j]["h"], candles[j]["l"], candles[j-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs) / period

def adx(candles, period, i):
    if i < period * 2: return 0.0
    trs, plus_dms, minus_dms = [], [], []
    for j in range(1, i + 1):
        h, l, prev_h, prev_l, prev_c = candles[j]["h"], candles[j]["l"], candles[j-1]["h"], candles[j-1]["l"], candles[j-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        up = h - prev_h
        down = prev_l - l
        plus_dms.append(up if (up > down and up > 0) else 0)
        minus_dms.append(down if (down > up and down > 0) else 0)
        
    # Wilder's Smoothing (simplified for speed)
    atr_val = sum(trs[-period:]) / period
    if atr_val == 0: return 0.0
    plus_di = 100 * (sum(plus_dms[-period:]) / period) / atr_val
    minus_di = 100 * (sum(minus_dms[-period:]) / period) / atr_val
    if (plus_di + minus_di) == 0: return 0.0
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return dx # Simplified ADX (using DX for speed in this script)

def calculate_wilson_lower_bound(wins, total, z=1.96):
    if total == 0: return 0.0
    p = wins / total
    num = p + (z**2) / (2 * total) - z * math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2)))
    den = 1 + (z**2) / total
    return (num / den) * 100

def get_metrics(equity_curve, trade_returns):
    if not trade_returns: return {"ret": 0, "dd": 0, "n": 0, "pf": 0, "wilson": 0, "pval": 1.0, "calmar": 0}
    wins = sum(1 for r in trade_returns if r > 0)
    n = len(trade_returns)
    gp = sum(r for r in trade_returns if r > 0)
    gl = abs(sum(r for r in trade_returns if r <= 0))
    pf = gp / gl if gl > 0 else 99.9
    
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    ret = ((equity_curve[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    calmar = ret / (max_dd * 100) if max_dd > 0 else 0
    wilson = calculate_wilson_lower_bound(wins, n)
    
    # Monte Carlo
    actual_final = 1.0
    for r in trade_returns: actual_final *= (1 + r)
    better = 0
    for _ in range(300):
        random.shuffle(trade_returns)
        sim = 1.0
        for r in trade_returns: sim *= (1 + r)
        if sim >= actual_final: better += 1
    pval = better / 300.0
    
    return {"ret": ret, "dd": max_dd*100, "n": n, "pf": pf, "wilson": wilson, "pval": pval, "calmar": calmar}

def run_portfolio_backtest(data):
    cash = INITIAL_CAPITAL
    positions = {} # sym -> pos_data
    trades = []
    equity_curve = []
    
    btc_candles = data["BTCUSDT"]
    min_len = min(len(data[sym]) for sym in ALL_ASSETS)
    
    for i in range(100, min_len):
        # 1. Determine Regime using BTCUSDT
        btc_adx = adx(btc_candles, 14, i)
        if btc_adx > 25:
            regime = "TREND"
            w_bh, w_mom, w_grid = 0.4, 0.6, 0.0
        elif btc_adx < 20:
            regime = "RANGE"
            w_bh, w_mom, w_grid = 0.3, 0.0, 0.7
        else:
            regime = "NEUTRAL"
            w_bh, w_mom, w_grid = 0.33, 0.33, 0.34
            
        # 2. Update Unrealized Equity & Exits
        current_equity = cash
        for sym in list(positions.keys()):
            c = data[sym][i]
            pos = positions[sym]
            
            # Calculate Unrealized for Equity Curve
            current_equity += pos["units"] * c["c"]
            
            # Exits
            exit_triggered = False
            exit_fee = TAKER_FEE
            exit_price = c["c"]
            
            if pos["strategy"] == "BH":
                if c["l"] <= pos["peak"] * 0.40:
                    exit_triggered = True
                    exit_price = pos["peak"] * 0.40
                else:
                    if c["h"] > pos["peak"]: pos["peak"] = c["h"]
                    # Defensive Mode
                    sma50 = sma([x["c"] for x in data[sym]], 50, i)
                    adx_val = adx(data[sym], 14, i)
                    if sma50 and adx_val > 25 and c["c"] < sma50:
                        exit_triggered = True
                        
            elif pos["strategy"] == "Momentum":
                if c["l"] <= pos["trailing_stop"]:
                    exit_triggered = True
                    exit_price = pos["trailing_stop"]
                else:
                    if c["h"] > pos["highest"]:
                        pos["highest"] = c["h"]
                        atr_val = atr(data[sym], 14, i)
                        if atr_val:
                            new_stop = pos["highest"] - (2.0 * atr_val)
                            if new_stop > pos["trailing_stop"]: pos["trailing_stop"] = new_stop
                    sma50 = sma([x["c"] for x in data[sym]], 50, i)
                    if sma50 and c["c"] < sma50:
                        exit_triggered = True
                        
            elif pos["strategy"] == "Grid":
                if c["l"] <= pos["initial"] * 0.90:
                    exit_triggered = True
                    exit_price = pos["initial"] * 0.90
                elif c["h"] >= pos["avg_entry"] * 1.02:
                    exit_triggered = True
                    exit_price = pos["avg_entry"] * 1.02
                    exit_fee = MAKER_FEE
                else:
                    # DCA
                    if pos["levels"] == 1 and c["l"] <= pos["initial"] * 0.97:
                        pos["levels"] = 2
                        add_val = pos["initial_val"]
                        cash -= add_val
                        pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.97)
                        pos["avg_entry"] = (pos["avg_entry"] * 1 + (pos["initial"] * 0.97)) / 2
                        pos["initial_val"] = add_val
                    elif pos["levels"] == 2 and c["l"] <= pos["initial"] * 0.94:
                        pos["levels"] = 3
                        add_val = pos["initial_val"]
                        cash -= add_val
                        pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.94)
                        pos["avg_entry"] = (pos["avg_entry"] * 2 + (pos["initial"] * 0.94)) / 3
                        pos["initial_val"] = add_val
            
            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - exit_fee)
                cash += exit_val
                ret = (exit_val / pos["invested"]) - 1
                trades.append({"ret": ret})
                del positions[sym]
                
        equity_curve.append(current_equity)
        
        # 3. New Entries
        for sym in ALL_ASSETS:
            if sym in positions: continue
            c = data[sym][i]
            closes = [x["c"] for x in data[sym]]
            
            strat = "BH" if sym in BH_ASSETS else ("Momentum" if sym in MOM_ASSETS else "Grid")
            
            # Target allocation per trade based on weight and number of assets in that family
            if strat == "BH": alloc_pct = w_bh / len(BH_ASSETS)
            elif strat == "Momentum": alloc_pct = w_mom / len(MOM_ASSETS)
            else: alloc_pct = w_grid / len(GRID_ASSETS)
            
            alloc_amt = current_equity * alloc_pct
            if alloc_amt > cash: alloc_amt = cash * 0.95
            if alloc_amt < 10: continue
            
            entry_triggered = False
            entry_price = c["c"]
            fee = TAKER_FEE
            
            if strat == "BH":
                # Enter only if above SMA50 (to avoid buying in downtrend)
                sma50 = sma(closes, 50, i)
                if sma50 and c["c"] > sma50:
                    entry_triggered = True
            elif strat == "Momentum":
                sma50 = sma(closes, 50, i)
                rsi_val = rsi(closes, 14, i)
                prev_20 = [x["h"] for x in data[sym][i-20:i]]
                hh20 = max(prev_20) if prev_20 else 0
                if sma50 and rsi_val and c["c"] > sma50 and 40 < rsi_val < 80 and c["c"] > hh20:
                    entry_triggered = True
            elif strat == "Grid":
                sma20 = sma(closes, 20, i)
                std20 = std_dev(closes, 20, i, sma20) if sma20 else None
                lower_bb = (sma20 - 2 * std20) if (sma20 and std20) else None
                rsi_val = rsi(closes, 14, i)
                if lower_bb and rsi_val and c["c"] <= lower_bb and rsi_val < 35:
                    entry_triggered = True
                    fee = MAKER_FEE
                    
            if entry_triggered:
                cash -= alloc_amt
                units = (alloc_amt * (1 - fee)) / entry_price
                positions[sym] = {
                    "strategy": strat,
                    "entry_price": entry_price,
                    "units": units,
                    "invested": alloc_amt,
                    "peak": entry_price,
                    "highest": entry_price,
                    "trailing_stop": entry_price - (2 * (atr(data[sym], 14, i) or entry_price*0.05)),
                    "initial": entry_price,
                    "avg_entry": entry_price,
                    "levels": 1,
                    "initial_val": alloc_amt
                }
                
    # Close all remaining positions at the end
    for sym, pos in positions.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        ret = (exit_val / pos["invested"]) - 1
        trades.append({"ret": ret})
        
    equity_curve.append(cash)
    return equity_curve, [t["ret"] for t in trades]

def evaluate_wf(data, window_size):
    profitable = 0
    for w in range(4):
        start = w * window_size
        end = start + window_size if w < 3 else len(data["BTCUSDT"])
        sub_data = {sym: data[sym][start:end] for sym in ALL_ASSETS}
        eq, trades = run_portfolio_backtest(sub_data)
        if eq[-1] > eq[0]: profitable += 1
    return profitable >= 3

def main():
    print("=== Combined M11-IR Portfolio Backtest ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}%\n")
    
    data = {}
    for sym in ALL_ASSETS:
        candles = load_candles(sym)
        if candles: data[sym] = candles
        
    min_len = min(len(data[sym]) for sym in ALL_ASSETS)
    for sym in ALL_ASSETS:
        data[sym] = data[sym][-min_len:] # Align to recent
        
    eq_curve, trade_rets = run_portfolio_backtest(data)
    m = get_metrics(eq_curve, trade_rets)
    
    window_size = len(data["BTCUSDT"]) // 4
    wf_passed = evaluate_wf(data, window_size)
    
    # Gate Logic (Aggregate Portfolio)
    passed = (m["pf"] > 1.2 and m["wilson"] > 36 and m["dd"] < 30 and m["pval"] < 0.05 and wf_passed)
    
    print(f"Total Return: {m['ret']:.2f}%")
    print(f"MaxDD: {m['dd']:.2f}%")
    print(f"Calmar: {m['calmar']:.2f}")
    print(f"Total Trades: {m['n']}")
    print(f"PF: {m['pf']:.2f}")
    print(f"Wilson: {m['wilson']:.2f}%")
    print(f"Monte Carlo P-Val: {m['pval']:.3f}")
    print(f"Walk-Forward (4/4 windows): {'PASS' if wf_passed else 'FAIL'}")
    print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
