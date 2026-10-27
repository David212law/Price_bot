import json
import os
import math
import random

# ─── Configuration (M40 on New Assets) ───
INITIAL_CAPITAL = 10000.0
DATA_DIR = "data/hyperliquid"
TAKER_FEE = 0.0005
EMA_TREND = 200
RSI_PERIOD = 14
RSI_LONG = 35
RSI_SHORT = 65
ATR_PERIOD = 14
TP_ATR = 4.0
SL_ATR = 2.0
RISK_PER_TRADE = 0.02
MAX_CONCURRENT = 3
NEW_SYMBOLS = ["DOGE", "ADA", "LINK"]

def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

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

def calc_atr(candles, period=14):
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

def calculate_pf(trades):
    gp = sum(t["ret"] for t in trades if t["ret"] > 0)
    gl = abs(sum(t["ret"] for t in trades if t["ret"] <= 0))
    return gp / gl if gl > 0 else 99.99

def run_backtest(data):
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    equity_curve = []
    
    ind = {}
    for sym in NEW_SYMBOLS:
        closes = [c["c"] for c in data[sym]]
        ind[sym] = {
            "ema": calc_ema(closes, EMA_TREND),
            "rsi": calc_rsi(closes, RSI_PERIOD),
            "atr": calc_atr(data[sym], ATR_PERIOD)
        }

    for i in range(EMA_TREND + RSI_PERIOD, len(data[NEW_SYMBOLS[0]])):
        current_equity = cash
        
        for sym in list(positions.keys()):
            pos = positions[sym]
            c = data[sym][i]
            
            exit_triggered = False
            exit_price = c["c"]
            
            if pos["side"] == "LONG":
                if c["l"] <= pos["sl"]: exit_triggered, exit_price = True, pos["sl"]
                elif c["h"] >= pos["tp"]: exit_triggered, exit_price = True, pos["tp"]
            elif pos["side"] == "SHORT":
                if c["h"] >= pos["sl"]: exit_triggered, exit_price = True, pos["sl"]
                elif c["l"] <= pos["tp"]: exit_triggered, exit_price = True, pos["tp"]
                
            if exit_triggered:
                ret = (exit_price - pos["entry"]) / pos["entry"] if pos["side"] == "LONG" else (pos["entry"] - exit_price) / pos["entry"]
                pnl = pos["invested"] * ret
                cash += pos["invested"] + pnl
                trades.append({"ret": ret})
                del positions[sym]

        equity_curve.append(current_equity)
        
        for sym in NEW_SYMBOLS:
            if sym in positions: continue
            if len(positions) >= MAX_CONCURRENT: break
            
            ema_val = ind[sym]["ema"][i]
            rsi_val = ind[sym]["rsi"][i]
            atr_val = ind[sym]["atr"][i]
            
            if None in [ema_val, rsi_val, atr_val]: continue
            
            c = data[sym][i]
            side = None
            
            if c["c"] > ema_val and rsi_val < RSI_LONG: side = "LONG"
            elif c["c"] < ema_val and rsi_val > RSI_SHORT: side = "SHORT"
            
            if side:
                alloc = current_equity * RISK_PER_TRADE
                if alloc < 10: continue
                
                cash -= alloc
                entry_price = c["c"]
                if side == "LONG":
                    tp = entry_price + (TP_ATR * atr_val)
                    sl = entry_price - (SL_ATR * atr_val)
                else:
                    tp = entry_price - (TP_ATR * atr_val)
                    sl = entry_price + (SL_ATR * atr_val)
                    
                positions[sym] = {"side": side, "entry": entry_price, "invested": alloc, "tp": tp, "sl": sl}

    for sym, pos in positions.items():
        exit_price = data[sym][-1]["c"]
        ret = (exit_price - pos["entry"]) / pos["entry"] if pos["side"] == "LONG" else (pos["entry"] - exit_price) / pos["entry"]
        pnl = pos["invested"] * ret
        cash += pos["invested"] + pnl
        trades.append({"ret": ret})

    equity_curve.append(cash)
    return equity_curve, trades

def main():
    print(f"=== M40 Test on New Assets (DOGE, ADA, LINK) ===")
    
    data = {}
    for sym in NEW_SYMBOLS:
        d = load_data(sym)
        if d: data[sym] = d
        else:
            print(f"Missing data for {sym}. Please run the data adapter first.")
            return
            
    # Align data lengths
    min_len = min(len(data[s]) for s in data)
    for s in data: data[s] = data[s][-min_len:]
    
    eq_curve, trades = run_backtest(data)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    max_dd = 0.0
    peak = eq_curve[0]
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    n = len(trades)
    wins = sum(1 for t in trades if t["ret"] > 0)
    
    print(f"\n=== RESULTS ===")
    print(f"Total Return: {ret:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}%")
    print(f"Trades: {n} | Win Rate: {(wins/n)*100:.2f}%")
    print(f"Profit Factor: {calculate_pf(trades):.2f}")

if __name__ == "__main__":
    main()
