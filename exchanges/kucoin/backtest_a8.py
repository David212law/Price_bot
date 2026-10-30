import json
import os
import math
import random
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]

INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0006 # 0.06% (KuCoin Futures)
MAKER_FEE = 0.0002 # 0.02% (KuCoin Futures)

# A8 Params
BB_PERIOD = 20
BB_STD = 2.0
RSI_PERIOD = 14
RSI_LOW = 35
TP_PCT = 0.02
SL_PCT = 0.10
LEVEL_2_DROP = 0.03
LEVEL_3_DROP = 0.06
RISK_PER_TRADE = 0.01
MAX_CONCURRENT = 3
TIME_STOP_CANDLES = 15
EMA_TREND_PERIOD = 200
ADX_PERIOD = 14
ADX_THRESHOLD = 20

def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: 
        data = json.load(f)
        return data.get("candles", [])

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

def calc_bb(closes, period, std_mult):
    upper = [None] * len(closes)
    lower = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i-period+1:i+1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = variance ** 0.5
        upper[i] = sma + (std_mult * std)
        lower[i] = sma - (std_mult * std)
    return upper, lower

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

def run_backtest(data_dict):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve = []
    
    ind = {}
    for sym in SYMBOLS:
        candles = data_dict[sym]
        closes_4h = [c["c"] for c in candles]
        bb_u, bb_l = calc_bb(closes_4h, BB_PERIOD, BB_STD)
        rsi_4h = calc_rsi(closes_4h, RSI_PERIOD)
        
        # تبدیل ۴ ساعته به روزانه برای EMA200 و ADX
        closes_1d = []
        candles_1d = []
        for i in range(0, len(candles), 6):
            chunk = candles[i:i+6]
            if len(chunk) == 6:
                closes_1d.append(chunk[-1]["c"])
                candles_1d.append({
                    "h": max(c["h"] for c in chunk),
                    "l": min(c["l"] for c in chunk),
                    "c": chunk[-1]["c"]
                })
                
        ema_1d = calc_ema(closes_1d, EMA_TREND_PERIOD)
        adx_1d = calc_adx(candles_1d, ADX_PERIOD)
        
        ind[sym] = {"bb_l": bb_l, "rsi": rsi_4h, "ema_1d": ema_1d, "adx_1d": adx_1d}

    min_len = min(len(data_dict[s]) for s in SYMBOLS)
    
    for i in range(EMA_TREND_PERIOD * 6 + 2, min_len):
        current_equity = cash
        for _sym in positions:
            current_equity += positions[_sym]["units"] * data_dict[_sym][i]["c"]
            
        for sym in list(positions.keys()):
            pos = positions[sym]
            c = data_dict[sym][i]
            exit_triggered = False
            exit_price = c["c"]
            reason = ""
            
            if (i - pos["entry_idx"]) >= TIME_STOP_CANDLES:
                exit_triggered, reason = True, "TIME_STOP"
            elif c["l"] <= pos["initial"] * (1 - SL_PCT):
                exit_triggered, exit_price, reason = True, pos["initial"] * (1 - SL_PCT), "SL"
            elif c["h"] >= pos["avg"] * (1 + TP_PCT):
                exit_triggered, exit_price, reason = True, pos["avg"] * (1 + TP_PCT), "TP"
            else:
                if pos["levels"] == 1 and c["l"] <= pos["initial"] * (1 - LEVEL_2_DROP):
                    add = current_equity * RISK_PER_TRADE
                    if cash >= add:
                        pos["invested"] += add
                        pos["units"] += (add * (1 - MAKER_FEE)) / (pos["initial"] * (1 - LEVEL_2_DROP))
                        pos["avg"] = pos["invested"] / pos["units"]
                        pos["levels"] = 2
                        cash -= add
                elif pos["levels"] == 2 and c["l"] <= pos["initial"] * (1 - LEVEL_3_DROP):
                    add = current_equity * RISK_PER_TRADE
                    if cash >= add:
                        pos["invested"] += add
                        pos["units"] += (add * (1 - MAKER_FEE)) / (pos["initial"] * (1 - LEVEL_3_DROP))
                        pos["avg"] = pos["invested"] / pos["units"]
                        pos["levels"] = 3
                        cash -= add
                        
            if exit_triggered:
                exit_val = pos["units"] * exit_price * (1 - TAKER_FEE)
                cash += exit_val
                ret = (exit_val - pos["invested"]) / pos["invested"]
                trades.append({"ret": ret, "reason": reason})
                del positions[sym]

        equity_curve.append(current_equity)
        
        for sym in SYMBOLS:
            if sym in positions or len(positions) >= MAX_CONCURRENT: continue
            
            c = data_dict[sym][i]
            daily_idx = min(i // 6, len(ind[sym]["ema_1d"]) - 1)
            bb_l = ind[sym]["bb_l"][i]
            rsi = ind[sym]["rsi"][i]
            ema = ind[sym]["ema_1d"][daily_idx]
            adx = ind[sym]["adx_1d"][daily_idx]
            
            if None in [bb_l, rsi, ema, adx]: continue
            
            if c["c"] > ema and adx < ADX_THRESHOLD and c["c"] <= bb_l and rsi < RSI_LOW:
                alloc = current_equity * RISK_PER_TRADE
                if alloc < 10 or cash < alloc: continue
                cash -= alloc
                units = (alloc * (1 - MAKER_FEE)) / c["c"]
                positions[sym] = {
                    "initial": c["c"], "avg": c["c"], "units": units, 
                    "invested": alloc, "levels": 1, "entry_idx": i
                }

    return equity_curve, trades

def main():
    print(f"=== A8 Grid Backtest on KuCoin Data ===")
    data_dict = {}
    for sym in SYMBOLS:
        d = load_data(sym)
        if d: data_dict[sym] = d
        
    if len(data_dict) < len(SYMBOLS):
        print("Missing data.")
        return
        
    eq, trades = run_backtest(data_dict)
    
    final_eq = eq[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    peak = eq[0]
    max_dd = 0.0
    for val in eq:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    n = len(trades)
    if n > 0:
        wins = sum(1 for t in trades if t["ret"] > 0)
        pf = calculate_pf(trades)
        wilson = calculate_wilson_lower_bound(wins, n)
        pval = block_bootstrap_p_value(eq)
        
        reason_counts = {}
        for t in trades:
            r = t.get("reason", "UNKNOWN")
            reason_counts[r] = reason_counts.get(r, 0) + 1
        
        print(f"Total Return: {ret:.2f}%")
        print(f"MaxDD: {max_dd*100:.2f}%")
        print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}%")
        print(f"Profit Factor: {pf:.2f}")
        print(f"Wilson LB: {wilson:.2f}% | P-Value: {pval:.4f}")
        print(f"\nExit Reasons: {reason_counts}")
        
        passed = (n >= 30 and ret > 0 and max_dd < 0.15 and pf > 1.2 and wilson > 36 and pval < 0.05)
        print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")
    else:
        print("No trades generated.")

if __name__ == "__main__":
    main()
