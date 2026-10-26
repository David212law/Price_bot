import json
import os
import math
import random

# ─── Configuration (M34 -> M35 EMA Crossover) ───
INITIAL_CAPITAL = 10000.0
DATA_DIR = "data_hyperliquid"
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

# M31 Config (Funding Arbitrage)
M31_CAPITAL_PCT = 0.50
M31_LEVERAGE = 5
M31_SMA_PERIODS = 12
M31_ENTRY_THRESHOLD = 0.00005
M31_EXIT_THRESHOLD = 0.00001
M31_COOLDOWN = 3
FUNDING_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]

# M35 Config (EMA Crossover 1D)
M35_CAPITAL_PCT = 0.50
M35_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14
ATR_MULTIPLIER = 3.0

# ─── Data Loaders ───
def load_ohlcv(symbol, interval="4h"):
    path = f"{DATA_DIR}/{symbol}_{interval}.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

def load_funding(symbol):
    path = f"{DATA_DIR}/{symbol}_funding.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

# ─── Indicators (Pure Python) ───
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

# ─── Composite Engine ───
def run_composite():
    print(f"=== M35: Hyperliquid Composite (M31 Funding + M35 EMA 1D) ===")
    
    # 1. Load Data
    data_4h = {}
    data_1d = {}
    funding_data = {}
    for sym in FUNDING_SYMBOLS:
        d4 = load_ohlcv(sym, "4h")
        d1 = load_ohlcv(sym, "1d")
        f = load_funding(sym)
        if d4 and d1 and f:
            data_4h[sym] = d4
            data_1d[sym] = d1
            funding_data[sym] = f
            
    min_len_1d = min(len(data_1d[s]) for s in data_1d)
    for s in data_1d: data_1d[s] = data_1d[s][-min_len_1d:]
    
    # 2. Pre-calculate M35 Indicators (Daily)
    ind_m35 = {}
    for sym in M35_SYMBOLS:
        closes = [c["c"] for c in data_1d[sym]]
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        atr = calc_atr(data_1d[sym], ATR_PERIOD)
        ind_m35[sym] = {"ema_fast": ema_fast, "ema_slow": ema_slow, "atr": atr}
        
    # 3. Simulate M35 (Daily Loop)
    m35_capital = INITIAL_CAPITAL * M35_CAPITAL_PCT
    m35_cash = m35_capital
    m35_positions = {}
    m35_equity_curve = [m35_capital]
    
    for i in range(EMA_SLOW, min_len_1d):
        # Manage Positions
        for sym in list(m35_positions.keys()):
            pos = m35_positions[sym]
            c = data_1d[sym][i]
            
            exit_triggered = False
            exit_price = c["c"]
            reason = ""
            
            # Trailing Stop / Crossover Exit
            if pos["side"] == "LONG":
                if ind_m35[sym]["atr"][i]:
                    new_stop = c["h"] - (ATR_MULTIPLIER * ind_m35[sym]["atr"][i])
                    if new_stop > pos["stop"]: pos["stop"] = new_stop
                if c["l"] <= pos["stop"]:
                    exit_triggered, exit_price, reason = True, pos["stop"], "TRAILING_STOP"
                elif ind_m35[sym]["ema_fast"][i] < ind_m35[sym]["ema_slow"][i]:
                    exit_triggered, reason = True, "CROSSOVER"
            elif pos["side"] == "SHORT":
                if ind_m35[sym]["atr"][i]:
                    new_stop = c["l"] + (ATR_MULTIPLIER * ind_m35[sym]["atr"][i])
                    if new_stop < pos["stop"]: pos["stop"] = new_stop
                if c["h"] >= pos["stop"]:
                    exit_triggered, exit_price, reason = True, pos["stop"], "TRAILING_STOP"
                elif ind_m35[sym]["ema_fast"][i] > ind_m35[sym]["ema_slow"][i]:
                    exit_triggered, reason = True, "CROSSOVER"
                    
            if exit_triggered:
                if pos["side"] == "LONG":
                    ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                else:
                    ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                m35_cash += pos["invested"] * (1 + ret)
                del m35_positions[sym]
                
        # New Entries
        for sym in M35_SYMBOLS:
            if sym in m35_positions: continue
            
            ef = ind_m35[sym]["ema_fast"][i]
            es = ind_m35[sym]["ema_slow"][i]
            ef_prev = ind_m35[sym]["ema_fast"][i-1]
            es_prev = ind_m35[sym]["ema_slow"][i-1]
            atr_val = ind_m35[sym]["atr"][i]
            
            if None in [ef, es, ef_prev, es_prev, atr_val]: continue
            
            side = None
            if ef > es and ef_prev <= es_prev: side = "LONG"
            elif ef < es and ef_prev >= es_prev: side = "SHORT"
            
            if side:
                entry_price = data_1d[sym][i]["c"]
                alloc_amt = m35_cash * 0.20 # 20% of M35 cash per trade (max 5 trades)
                if alloc_amt > m35_cash * 0.95: alloc_amt = m35_cash * 0.95
                
                if side == "LONG":
                    stop = entry_price - (ATR_MULTIPLIER * atr_val)
                else:
                    stop = entry_price + (ATR_MULTIPLIER * atr_val)
                    
                m35_cash -= alloc_amt
                m35_positions[sym] = {"side": side, "entry_price": entry_price, "invested": alloc_amt, "stop": stop}
                
        # Calculate M35 Equity
        m35_eq = m35_cash + sum(p["invested"] for p in m35_positions.values()) # Simplified for daily
        m35_equity_curve.append(m35_eq)

    m35_final = m35_equity_curve[-1]
    print(f"--- M35 (EMA 1D) Final: {m35_final:.2f} USDT | Return: {((m35_final-m35_capital)/m35_capital)*100:.2f}%")

    # 4. Simulate M31 (Funding) using 4H / Funding events
    # Note: For simplicity and accurate composite, we just run the M31 logic as before.
    m31_capital = INITIAL_CAPITAL * M31_CAPITAL_PCT
    m31_capital_per_sym = m31_capital / len(FUNDING_SYMBOLS)
    m31_states = {sym: {"in_pos": False, "funding": 0, "fees": 0, "last_exit": 0, "hist": []} for sym in FUNDING_SYMBOLS}
    
    all_funding_events = []
    for sym in FUNDING_SYMBOLS:
        for rec in funding_data.get(sym, []):
            all_funding_events.append({"t": rec["t"], "rate": rec["rate"], "sym": sym})
    all_funding_events.sort(key=lambda x: x["t"])
    
    for event in all_funding_events:
        sym = event["sym"]
        rate = event["rate"]
        st = m31_states[sym]
        
        st["hist"].append(rate)
        if len(st["hist"]) > M31_SMA_PERIODS: st["hist"].pop(0)
        avg_rate = sum(st["hist"]) / len(st["hist"])
        
        if st["in_pos"]:
            if rate > 0: st["funding"] += m31_capital_per_sym * rate * M31_LEVERAGE
            if avg_rate < M31_EXIT_THRESHOLD:
                st["fees"] += m31_capital_per_sym * MAKER_FEE * 2 * M31_LEVERAGE
                st["in_pos"] = False
                st["last_exit"] = event["t"]
        else:
            time_since_exit = (event["t"] - st["last_exit"]) / (3600 * 1000)
            if avg_rate > M31_ENTRY_THRESHOLD and rate > 0 and time_since_exit >= M31_COOLDOWN:
                st["fees"] += m31_capital_per_sym * MAKER_FEE * 2 * M31_LEVERAGE
                st["in_pos"] = True
                
    m31_final = m31_capital + sum(st["funding"] - st["fees"] for st in m31_states.values())
    print(f"--- M31 (Funding) Final: {m31_final:.2f} USDT | Return: {((m31_final-m31_capital)/m31_capital)*100:.2f}%")

    # 5. Combined Results
    combined_final = m31_final + m35_final
    total_ret = ((combined_final - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    # Approximate Combined MaxDD (Just for this test, we assume no correlation for simplicity, 
    # or we can just report the max of individual DDs. Let's report a rough estimate).
    # Since we don't have a unified 4H equity curve here, we'll just report the sum.
    days = min_len_1d
    apy = ((combined_final / INITIAL_CAPITAL) ** (365 / days) - 1) * 100 if days > 0 else 0
    
    print(f"\n=== COMPOSITE RESULTS ===")
    print(f"Total Return: {total_ret:.2f}% | APY: {apy:.2f}%")
    print(f"Combined Capital: {combined_final:.2f} USDT")
    
    passed = (apy > 10.0)
    print(f"\nFinal Status (Target: APY > 10%): {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    run_composite()
