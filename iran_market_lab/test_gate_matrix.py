import json
import os
import math
import random

# ─── Configuration ───
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"
ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", 
    "DOGEUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"
]

def load_candles(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

def sma(values, period):
    if len(values) < period: return None
    return sum(values[-period:]) / period

def std_dev(values, period, mean):
    if len(values) < period: return None
    window = values[-period:]
    variance = sum((x - mean) ** 2 for x in window) / period
    return variance ** 0.5

def rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100.0
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def atr(candles, period=14):
    if len(candles) < period + 1: return None
    trs = []
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs[-period:]) / period

def calculate_wilson_lower_bound(wins, total, z=1.96):
    if total == 0: return 0.0
    p = wins / total
    numerator = p + (z**2) / (2 * total) - z * math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2)))
    denominator = 1 + (z**2) / total
    return (numerator / denominator) * 100

def calculate_monte_carlo_p_value(trade_returns, iterations=500):
    if not trade_returns: return 1.0
    actual_final = 1.0
    for r in trade_returns: actual_final *= (1 + r)
    
    better_than_actual = 0
    for _ in range(iterations):
        shuffled = trade_returns[:]
        random.shuffle(shuffled)
        sim_final = 1.0
        for r in shuffled: sim_final *= (1 + r)
        if sim_final >= actual_final:
            better_than_actual += 1
            
    return better_than_actual / iterations

def get_metrics_from_equity_curve(equity_curve, trade_returns, r_multiples):
    if not equity_curve or not trade_returns:
        return {"ret": 0, "dd": 0, "n": 0, "pf": 0, "exp": 0, "wilson": 0, "pval": 1.0, "wins": 0}
        
    wins = sum(1 for r in trade_returns if r > 0)
    n = len(trade_returns)
    
    gross_profit = sum(r for r in trade_returns if r > 0)
    gross_loss = abs(sum(r for r in trade_returns if r <= 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else 99.9
    avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
    
    # Equity Curve Max DD
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak if peak > 0 else 0
        if dd > max_dd: max_dd = dd
        
    ret = (equity_curve[-1] - 1) * 100
    wilson = calculate_wilson_lower_bound(wins, n)
    pval = calculate_monte_carlo_p_value(trade_returns, iterations=500)
    
    return {
        "ret": ret, "dd": max_dd * 100, "n": n, "pf": pf, 
        "exp": avg_r, "wilson": wilson, "pval": pval, "wins": wins
    }

# ─── Event-Driven Strategies (Checks Low before High) ───

def run_bh(candles):
    if len(candles) < 10: return [], []
    trades = []
    eq_curve = [1.0]
    
    entry_val = candles[0]["c"] * (1 + TAKER_FEE)
    peak_price = candles[0]["c"]
    capital = 1.0
    in_pos = True
    
    for c in candles[1:]:
        low, high = c["l"], c["h"]
        
        # Check Crash (Low triggers before High)
        if low <= peak_price * 0.40:
            exit_val = (peak_price * 0.40) * (1 - TAKER_FEE)
            ret = (exit_val / entry_val) - 1
            capital *= (1 + ret)
            trades.append({"ret": ret, "r": 0})
            eq_curve.append(capital)
            in_pos = False
            break
        else:
            if high > peak_price: peak_price = high
            # Unrealized equity for DD calc
            eq_curve.append(capital * ((c["c"] * (1 - TAKER_FEE)) / entry_val))
            
    if in_pos:
        exit_val = candles[-1]["c"] * (1 - TAKER_FEE)
        ret = (exit_val / entry_val) - 1
        capital *= (1 + ret)
        trades.append({"ret": ret, "r": 0})
        eq_curve.append(capital)
        
    return trades, eq_curve

def run_momentum(candles):
    if len(candles) < 60: return [], []
    trades = []
    eq_curve = [1.0]
    capital = 1.0
    pos = None
    
    for i in range(60, len(candles)):
        c = candles[i]
        window = candles[i-50:i+1]
        closes = [x["c"] for x in window]
        
        sma50 = sma(closes, 50)
        rsi_val = rsi(closes, 14)
        atr_val = atr(window, 14)
        prev_20 = candles[i-20:i]
        hh20 = max(x["h"] for x in prev_20)
        
        if pos:
            # Check SL first (Low), then TP (High)
            if c["l"] <= pos["trailing_stop"]:
                exit_val = pos["trailing_stop"] * (1 - TAKER_FEE)
                ret = (exit_val / pos["entry_val"]) - 1
                capital *= (1 + ret)
                r_mult = ret / pos["risk_pct"] if pos["risk_pct"] > 0 else 0
                trades.append({"ret": ret, "r": r_mult})
                pos = None
            elif c["h"] >= (pos["entry_price"] * 5.0): # Arbitrary huge TP just in case
                pass 
            else:
                if c["h"] > pos["highest"]:
                    pos["highest"] = c["h"]
                    new_stop = pos["highest"] - (2.0 * atr_val)
                    if new_stop > pos["trailing_stop"]: pos["trailing_stop"] = new_stop
                    
                # Check SMA50 exit on Close
                if c["c"] < sma50:
                    exit_val = c["c"] * (1 - TAKER_FEE)
                    ret = (exit_val / pos["entry_val"]) - 1
                    capital *= (1 + ret)
                    r_mult = ret / pos["risk_pct"] if pos["risk_pct"] > 0 else 0
                    trades.append({"ret": ret, "r": r_mult})
                    pos = None
        else:
            if sma50 and rsi_val and atr_val:
                # Entry triggered by High crossing HH20
                if c["h"] > hh20 and 40 < rsi_val < 80:
                    entry_price = max(c["o"], hh20) # Assume fill at HH20 if open was lower
                    risk_pct = (2 * atr_val) / entry_price
                    pos = {
                        "entry_val": entry_price * (1 + TAKER_FEE),
                        "entry_price": entry_price,
                        "highest": entry_price,
                        "trailing_stop": entry_price - (2.0 * atr_val),
                        "risk_pct": risk_pct
                    }
                    
        if pos:
            eq_curve.append(capital * ((c["c"] * (1 - TAKER_FEE)) / pos["entry_val"]))
        else:
            eq_curve.append(capital)
            
    return trades, eq_curve

def run_grid(candles):
    if len(candles) < 60: return [], []
    trades = []
    eq_curve = [1.0]
    capital = 1.0
    pos = None
    
    for i in range(60, len(candles)):
        c = candles[i]
        window = candles[i-50:i+1]
        closes = [x["c"] for x in window]
        
        mean = sma(closes, 20)
        std = std_dev(closes, 20, mean) if mean else None
        lower_bb = (mean - 2 * std) if (mean and std) else None
        rsi_val = rsi(closes, 14)
        
        if pos:
            # Check SL (Low) BEFORE TP (High)
            if c["l"] <= pos["initial"] * 0.90:
                exit_val = (pos["initial"] * 0.90) * (1 - TAKER_FEE)
                ret = (exit_val / pos["avg_entry"]) - 1
                capital *= (1 + ret)
                trades.append({"ret": ret, "r": ret/0.10})
                pos = None
            elif c["h"] >= pos["avg_entry"] * 1.02:
                exit_val = (pos["avg_entry"] * 1.02) * (1 - MAKER_FEE)
                ret = (exit_val / pos["avg_entry"]) - 1
                capital *= (1 + ret)
                trades.append({"ret": ret, "r": ret/0.10})
                pos = None
            else:
                # Check DCA (Low triggers)
                if pos["levels"] == 1 and c["l"] <= pos["initial"] * 0.97:
                    pos["levels"] = 2
                    pos["avg_entry"] = (pos["avg_entry"] + (pos["initial"] * 0.97) * (1 + MAKER_FEE)) / 2
                elif pos["levels"] == 2 and c["l"] <= pos["initial"] * 0.94:
                    pos["levels"] = 3
                    pos["avg_entry"] = (pos["avg_entry"] * 2 + (pos["initial"] * 0.94) * (1 + MAKER_FEE)) / 3
        else:
            if lower_bb and rsi_val:
                if c["l"] <= lower_bb and rsi_val < 35:
                    entry_price = min(c["o"], lower_bb)
                    pos = {
                        "initial": entry_price,
                        "avg_entry": entry_price * (1 + MAKER_FEE),
                        "levels": 1
                    }
                    
        if pos:
            eq_curve.append(capital * ((c["c"] * (1 - TAKER_FEE)) / pos["avg_entry"]))
        else:
            eq_curve.append(capital)
            
    return trades, eq_curve

def evaluate_walk_forward(candles, strategy_func):
    if len(candles) < 200: return False
    window_size = len(candles) // 4
    profitable_windows = 0
    
    for w in range(4):
        start = w * window_size
        end = start + window_size if w < 3 else len(candles)
        window_candles = candles[start:end]
        
        trades, _ = strategy_func(window_candles)
        if trades:
            w_ret = 1.0
            for t in trades: w_ret *= (1 + t["ret"])
            if w_ret > 1.0: profitable_windows += 1
            
    return profitable_windows >= 3

def main():
    print("=== Event-Driven Comprehensive Gate Test (D-68-Plus & D-110) ===")
    print(f"Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}%\n")
    
    strategies = [("B&H", run_bh), ("Momentum", run_momentum), ("Grid", run_grid)]
    
    for symbol in ASSETS:
        candles = load_candles(symbol)
        if not candles: continue
        print(f"── {symbol} ──")
        
        for strat_name, func in strategies:
            trades, eq_curve = func(candles)
            rets = [t["ret"] for t in trades]
            rs = [t["r"] for t in trades]
            
            m = get_metrics_from_equity_curve(eq_curve, rets, rs)
            wf_passed = evaluate_walk_forward(candles, func)
            
            if strat_name == "Momentum" or strat_name == "Grid":
                # D-110 Active
                passed = (m["n"] >= 50 and m["pf"] > 1.2 and m["wilson"] > 36 and m["dd"] < 30 and wf_passed and m["pval"] < 0.05)
                gate_type = "D-110 Active"
            else:
                # D-110 Inactive (B&H)
                calmar = m["ret"] / m["dd"] if m["dd"] > 0 else 0
                passed = (calmar > 3.0 and m["dd"] < 55 and wf_passed)
                gate_type = "D-110 Inactive"
            
            status = "✅ PASS" if passed else "❌ FAIL"
            
            print(f"  [{strat_name}] {status} ({gate_type})")
            print(f"    Return: {m['ret']:.2f}% | MaxDD: {m['dd']:.2f}% | Calmar: {(m['ret']/m['dd'] if m['dd']>0 else 0):.2f}")
            print(f"    Trades: {m['n']} | PF: {m['pf']:.2f} | Exp: {m['exp']:.3f}R | Wilson: {m['wilson']:.2f}% | P-Val: {m['pval']:.3f}")
            print(f"    Walk-Forward: {'PASS' if wf_passed else 'FAIL'}")
        print()

if __name__ == "__main__":
    main()
