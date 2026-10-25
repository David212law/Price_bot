import json
import os
import math
import random

# ─── Configuration ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"
COOLDOWN_PERIOD = 6 # 24 hours (6 * 4h) wait after exit

ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", 
    "DOGEUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"
]

def load_candles(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

# ─── Pre-calculation of Indicators ───

def calc_sma(closes, period):
    sma = [None] * len(closes)
    s = 0
    for i in range(len(closes)):
        s += closes[i]
        if i >= period: s -= closes[i - period]
        if i >= period - 1: sma[i] = s / period
    return sma

def calc_ema(closes, period):
    ema = [None] * len(closes)
    if len(closes) < period: return ema
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

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

def calc_atr(candles, period=14):
    atr = [None] * len(candles)
    if len(candles) < period + 1: return atr
    trs = []
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    first_atr = sum(trs[:period]) / period
    atr[period] = first_atr
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i - 1]) / period
    return atr

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

# ─── Backtest Engine ───

def calculate_wilson_lower_bound(wins, total, z=1.96):
    if total == 0: return 0.0
    p = wins / total
    num = p + (z**2) / (2 * total) - z * math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2)))
    den = 1 + (z**2) / total
    return (num / den) * 100

def calculate_bootstrap_p_value(trade_returns, iterations=500):
    if not trade_returns: return 1.0
    n = len(trade_returns)
    actual_mean = sum(trade_returns) / n
    
    # Null hypothesis: true mean is 0
    centered_rets = [r - actual_mean for r in trade_returns]
    
    better_than_actual = 0
    for _ in range(iterations):
        # Bootstrap sample (with replacement)
        sample = [random.choice(centered_rets) for _ in range(n)]
        sim_mean = sum(sample) / n
        
        # We check how often the simulated mean (under null) is >= actual_mean
        if sim_mean >= actual_mean:
            better_than_actual += 1
            
    return better_than_actual / iterations

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
    pval = calculate_bootstrap_p_value(trade_returns)
    
    return {"ret": ret, "dd": max_dd*100, "n": n, "pf": pf, "wilson": wilson, "pval": pval, "calmar": calmar}

def run_portfolio_backtest(data, ind):
    cash = INITIAL_CAPITAL
    positions = {} 
    cooldowns = {} 
    trades = []
    equity_curve = []
    min_len = len(data["BTCUSDT"])
    
    for i in range(100, min_len):
        btc_adx = ind["BTCUSDT"]["adx"][i]
        
        if btc_adx > 25:
            w_m9, w_vsb, w_grid = 0.2, 0.3, 0.5
        elif btc_adx < 20:
            w_m9, w_vsb, w_grid = 0.5, 0.3, 0.2
        else:
            w_m9, w_vsb, w_grid = 0.33, 0.33, 0.34
            
        current_equity = cash
        for sym in list(positions.keys()):
            c = data[sym][i]
            pos = positions[sym]
            current_equity += pos["units"] * c["c"]
            
            exit_triggered = False
            exit_fee = TAKER_FEE
            exit_price = c["c"]
            
            if pos["strategy"] == "M9":
                if c["l"] <= pos["sl"]:
                    exit_triggered = True
                    exit_price = pos["sl"]
                elif c["h"] >= pos["tp"]:
                    exit_triggered = True
                    exit_price = pos["tp"]
                    
            elif pos["strategy"] == "VSB":
                if c["l"] <= pos["sl"]:
                    exit_triggered = True
                    exit_price = pos["sl"]
                elif c["h"] >= pos["tp"]:
                    exit_triggered = True
                    exit_price = pos["tp"]
                    
            elif pos["strategy"] == "Grid":
                if c["l"] <= pos["initial"] * 0.90:
                    exit_triggered = True
                    exit_price = pos["initial"] * 0.90
                elif c["h"] >= pos["avg_entry"] * 1.02:
                    exit_triggered = True
                    exit_price = pos["avg_entry"] * 1.02
                    exit_fee = MAKER_FEE
                else:
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
                trade_ret = (exit_val / pos["invested"]) - 1
                trades.append({"ret": trade_ret})
                del positions[sym]
                cooldowns[sym] = i + COOLDOWN_PERIOD
                
        equity_curve.append(current_equity)
        
        for sym in ASSETS:
            if sym in positions: continue
            if i < cooldowns.get(sym, 0): continue
            
            c = data[sym][i]
            
            strat = None
            if btc_adx > 25:
                strat = "VSB" if sym in ["ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"] else "M9"
            elif btc_adx < 20:
                strat = "Grid" if sym in ["BTCUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"] else "M9"
            else:
                strat = "M9"
                
            if strat == "M9": alloc_pct = w_m9 / 5
            elif strat == "VSB": alloc_pct = w_vsb / 5
            else: alloc_pct = w_grid / 5
            
            alloc_amt = current_equity * alloc_pct
            if alloc_amt > cash: alloc_amt = cash * 0.95
            if alloc_amt < 10: continue
            
            entry_triggered = False
            entry_price = c["c"]
            fee = TAKER_FEE
            sl, tp = 0, 0
            
            if strat == "M9":
                lower_bb = ind[sym]["lower_bb"][i]
                rsi_val = ind[sym]["rsi"][i]
                atr_val = ind[sym]["atr"][i]
                if lower_bb and rsi_val and atr_val:
                    if c["c"] <= lower_bb and rsi_val < 35:
                        entry_triggered = True
                        sl = entry_price - (2 * atr_val)
                        tp = entry_price + (4 * atr_val)
                        
            elif strat == "VSB":
                squeeze = ind[sym]["squeeze"][i]
                vol_sma = ind[sym]["vol_sma"][i]
                upper_bb = ind[sym]["upper_bb"][i]
                atr_val = ind[sym]["atr"][i]
                if squeeze and vol_sma and upper_bb and atr_val:
                    if c["c"] > upper_bb and c["v"] > (1.2 * vol_sma):
                        entry_triggered = True
                        sl = entry_price - (2 * atr_val)
                        tp = entry_price + (4 * atr_val)
                        
            elif strat == "Grid":
                lower_bb = ind[sym]["lower_bb"][i]
                rsi_val = ind[sym]["rsi"][i]
                if lower_bb and rsi_val:
                    if c["c"] <= lower_bb and rsi_val < 35:
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
                    "sl": sl,
                    "tp": tp,
                    "initial": entry_price,
                    "avg_entry": entry_price,
                    "levels": 1,
                    "initial_val": alloc_amt
                }
                
    for sym, pos in positions.items():
        exit_val = pos["units"] * data[sym][min_len-1]["c"] * (1 - TAKER_FEE)
        cash += exit_val
        trade_ret = (exit_val / pos["invested"]) - 1
        trades.append({"ret": trade_ret})
        
    equity_curve.append(cash)
    return equity_curve, [t["ret"] for t in trades]

def evaluate_wf(data, ind, window_size):
    profitable = 0
    for w in range(4):
        start = w * window_size
        end = start + window_size if w < 3 else len(data["BTCUSDT"])
        sub_data = {sym: data[sym][start:end] for sym in ASSETS}
        sub_ind = {sym: {k: v[start:end] for k, v in ind[sym].items()} for sym in ASSETS}
        
        eq, _ = run_portfolio_backtest(sub_data, sub_ind)
        if eq[-1] > eq[0]: profitable += 1
    return profitable >= 3

def main():
    print("=== Global Strategies (M9, VSB, Grid) on Wallex USDT (Final Fix) ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Maker: {MAKER_FEE*100}% | Taker: {TAKER_FEE*100}%\n")
    
    data = {}
    for sym in ASSETS:
        candles = load_candles(sym)
        if candles: data[sym] = candles
        
    min_len = min(len(data[sym]) for sym in ASSETS)
    for sym in ASSETS:
        data[sym] = data[sym][-min_len:]
        
    print("Pre-calculating indicators...")
    ind = {}
    for sym in ASSETS:
        closes = [x["c"] for x in data[sym]]
        vols = [x["v"] for x in data[sym]]
        
        sma20 = calc_sma(closes, 20)
        std20 = calc_std(closes, 20, sma20)
        ema20 = calc_ema(closes, 20)
        atr14 = calc_atr(data[sym], 14)
        vol_sma = calc_sma(vols, 20)
        
        upper_bb = [None] * len(closes)
        lower_bb = [None] * len(closes)
        upper_kc = [None] * len(closes)
        lower_kc = [None] * len(closes)
        squeeze = [False] * len(closes)
        
        for i in range(len(closes)):
            if sma20[i] and std20[i]:
                upper_bb[i] = sma20[i] + (2 * std20[i])
                lower_bb[i] = sma20[i] - (2 * std20[i])
            if ema20[i] and atr14[i]:
                upper_kc[i] = ema20[i] + (1.5 * atr14[i])
                lower_kc[i] = ema20[i] - (1.5 * atr14[i])
            if all(x is not None for x in [lower_bb[i], lower_kc[i], upper_bb[i], upper_kc[i]]):
                squeeze[i] = (lower_bb[i] > lower_kc[i]) and (upper_bb[i] < upper_kc[i])
                
        ind[sym] = {
            "rsi": calc_rsi(closes, 14),
            "atr": atr14,
            "adx": calc_adx(data[sym], 14),
            "upper_bb": upper_bb,
            "lower_bb": lower_bb,
            "squeeze": squeeze,
            "vol_sma": vol_sma
        }
        
    print("Running backtest...")
    eq_curve, trade_rets = run_portfolio_backtest(data, ind)
    m = get_metrics(eq_curve, trade_rets)
    
    print("Running Walk-Forward...")
    window_size = len(data["BTCUSDT"]) // 4
    wf_passed = evaluate_wf(data, ind, window_size)
    
    passed = (m["pf"] > 1.2 and m["wilson"] > 36 and m["dd"] < 30 and m["pval"] < 0.05 and wf_passed)
    
    print(f"\n=== Final Results ===")
    print(f"Total Return: {m['ret']:.2f}%")
    print(f"MaxDD: {m['dd']:.2f}%")
    print(f"Calmar: {m['calmar']:.2f}")
    print(f"Total Trades: {m['n']}")
    print(f"PF: {m['pf']:.2f}")
    print(f"Wilson: {m['wilson']:.2f}%")
    print(f"Monte Carlo P-Val (Bootstrap): {m['pval']:.4f}")
    print(f"Walk-Forward (3/4 windows): {'PASS' if wf_passed else 'FAIL'}")
    print(f"\nFinal Portfolio Status: {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
