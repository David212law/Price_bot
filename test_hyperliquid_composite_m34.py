import json
import os
import math
import random

# ─── Configuration ───
INITIAL_CAPITAL = 10000.0
DATA_DIR = "data_hyperliquid"
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

# M31 Config
M31_CAPITAL_PCT = 0.50  # 50% of total capital for Funding Arb
M31_LEVERAGE = 5
M31_SMA_PERIODS = 12
M31_ENTRY_THRESHOLD = 0.00005
M31_EXIT_THRESHOLD = 0.00001
M31_COOLDOWN = 3
FUNDING_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]

# M32-V2 Config (Optimized for fewer, higher quality trades)
M32_CAPITAL_PCT = 0.50  # 50% of total capital for Lead-Lag
LEADER = "BTC"
FOLLOWERS = ["ETH", "SOL", "BNB", "XRP", "AVAX"]
LEADER_RET_THRESHOLD = 0.040  # Increased from 2.5% to 4.0% (fewer, stronger signals)
TP_PCT = 0.040                # Increased to 4%
SL_PCT = 0.020                # SL is 2% (R:R = 1:2)
TIME_CAP_CANDLES = 5          # 5 candles = 20 hours
MAX_POSITIONS = 3

# ─── Data Loaders ───
def load_ohlcv(symbol, interval="4h"):
    path = f"{DATA_DIR}/{symbol}_{interval}.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

def load_funding(symbol):
    path = f"{DATA_DIR}/{symbol}_funding.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

# ─── Composite Engine ───
def run_composite():
    print(f"=== M34: Hyperliquid Composite (M31 + M32-V2) ===")
    
    # Load Data
    data_4h = {}
    for sym in FUNDING_SYMBOLS:
        d = load_ohlcv(sym, "4h")
        if d: data_4h[sym] = d
        
    funding_data = {}
    for sym in FUNDING_SYMBOLS:
        d = load_funding(sym)
        if d: funding_data[sym] = d
        
    min_len = min(len(data_4h[s]) for s in data_4h)
    for s in data_4h: data_4h[s] = data_4h[s][-min_len:]
    
    # Initialize Portfolios
    m31_capital = INITIAL_CAPITAL * M31_CAPITAL_PCT
    m31_capital_per_sym = m31_capital / len(FUNDING_SYMBOLS)
    m31_states = {sym: {"in_pos": False, "funding": 0, "fees": 0, "last_exit": 0, "hist": []} for sym in FUNDING_SYMBOLS}
    
    m32_capital = INITIAL_CAPITAL * M32_CAPITAL_PCT
    m32_cash = m32_capital
    m32_positions = {}
    m32_trades = []
    
    equity_curve = []
    
    # Align Funding data to 4H timestamps (Funding is hourly, need to map to 4H candles)
    # For simplicity, we process events chronologically.
    all_funding_events = []
    for sym in FUNDING_SYMBOLS:
        for rec in funding_data.get(sym, []):
            all_funding_events.append({"t": rec["t"], "rate": rec["rate"], "sym": sym})
    all_funding_events.sort(key=lambda x: x["t"])
    f_idx = 0
    
    for i in range(50, min_len):
        current_time = data_4h[LEADER][i]["t"]
        current_equity = 0
        
        # ─── 1. Process M31 (Funding) ───
        # Apply funding events that occurred up to this candle
        while f_idx < len(all_funding_events) and all_funding_events[f_idx]["t"] <= current_time:
            event = all_funding_events[f_idx]
            sym = event["sym"]
            rate = event["rate"]
            st = m31_states[sym]
            
            st["hist"].append(rate)
            if len(st["hist"]) > M31_SMA_PERIODS: st["hist"].pop(0)
            avg_rate = sum(st["hist"]) / len(st["hist"])
            
            if st["in_pos"]:
                if rate > 0:
                    st["funding"] += m31_capital_per_sym * rate * M31_LEVERAGE
                if avg_rate < M31_EXIT_THRESHOLD:
                    st["fees"] += m31_capital_per_sym * MAKER_FEE * 2 * M31_LEVERAGE
                    st["in_pos"] = False
                    st["last_exit"] = event["t"]
            else:
                time_since_exit = (event["t"] - st["last_exit"]) / (3600 * 1000)
                if avg_rate > M31_ENTRY_THRESHOLD and rate > 0 and time_since_exit >= M31_COOLDOWN:
                    st["fees"] += m31_capital_per_sym * MAKER_FEE * 2 * M31_LEVERAGE
                    st["in_pos"] = True
            f_idx += 1
            
        # Calculate M31 Equity
        m31_equity = m31_capital + sum(st["funding"] - st["fees"] for st in m31_states.values())
        
        # ─── 2. Process M32 (Lead-Lag) ───
        # Manage active positions
        for sym in list(m32_positions.keys()):
            pos = m32_positions[sym]
            c = data_4h[sym][i]
            
            exit_triggered = False
            exit_price = c["c"]
            
            if (i - pos["entry_idx"]) >= TIME_CAP_CANDLES:
                exit_triggered = True
            elif pos["side"] == "LONG":
                if c["l"] <= pos["sl"]: exit_triggered, exit_price = True, pos["sl"]
                elif c["h"] >= pos["tp"]: exit_triggered, exit_price = True, pos["tp"]
            elif pos["side"] == "SHORT":
                if c["h"] >= pos["sl"]: exit_triggered, exit_price = True, pos["sl"]
                elif c["l"] <= pos["tp"]: exit_triggered, exit_price = True, pos["tp"]
                
            if exit_triggered:
                if pos["side"] == "LONG":
                    ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                else:
                    ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                m32_cash += pos["invested"] * (1 + ret)
                m32_trades.append({"ret": ret})
                del m32_positions[sym]
                
        # Signals
        if i > 50:
            prev_c = data_4h[LEADER][i-1]
            prev_c2 = data_4h[LEADER][i-2]
            leader_ret = (prev_c["c"] - prev_c2["c"]) / prev_c2["c"]
            
            if abs(leader_ret) >= LEADER_RET_THRESHOLD:
                side = "LONG" if leader_ret > 0 else "SHORT"
                for sym in FOLLOWERS:
                    if sym in m32_positions: continue
                    if len(m32_positions) >= MAX_POSITIONS: break
                    
                    entry_price = data_4h[sym][i]["o"]
                    alloc_amt = (m32_cash + sum(p["invested"] for p in m32_positions.values())) * 0.10 # 10% of M32 eq
                    if alloc_amt > m32_cash * 0.95: alloc_amt = m32_cash * 0.95
                    
                    if side == "LONG":
                        tp, sl = entry_price * (1 + TP_PCT), entry_price * (1 - SL_PCT)
                    else:
                        tp, sl = entry_price * (1 - TP_PCT), entry_price * (1 + SL_PCT)
                        
                    m32_cash -= alloc_amt
                    m32_positions[sym] = {"side": side, "entry_price": entry_price, "invested": alloc_amt, "sl": sl, "tp": tp, "entry_idx": i}
                    
        m32_equity = m32_cash + sum(p["invested"] for p in m32_positions.values()) # simplified
        
        equity_curve.append(m31_equity + m32_equity)
        
    # Final Reporting
    final_eq = equity_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    days = min_len * 4 / 24
    apy = ((final_eq / INITIAL_CAPITAL) ** (365 / days) - 1) * 100 if days > 0 else 0
    calmar = apy / (max_dd * 100) if max_dd > 0 else 0
    
    print(f"\n=== COMPOSITE RESULTS ===")
    print(f"Total Return: {ret:.2f}% | APY: {apy:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}% | Calmar: {calmar:.2f}")
    
    # Breakdown
    m31_final = m31_capital + sum(st["funding"] - st["fees"] for st in m31_states.values())
    m32_final = m32_cash + sum(p["invested"] for p in m32_positions.values())
    
    print(f"\n--- M31 (Funding): {m31_final:.2f} USDT | Return: {((m31_final-m31_capital)/m31_capital)*100:.2f}%")
    print(f"--- M32 (Lead-Lag): {m32_final:.2f} USDT | Return: {((m32_final-m32_capital)/m32_capital)*100:.2f}%")
    
    print(f"\nM32 Trades: {len(m32_trades)}")
    if len(m32_trades) > 0:
        wins = sum(1 for t in m32_trades if t["ret"] > 0)
        print(f"M32 Win Rate: {(wins/len(m32_trades))*100:.2f}%")

    passed = (apy > 10.0 and max_dd < 0.05)
    print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    run_composite()
