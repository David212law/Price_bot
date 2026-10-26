import json
import os
import math
import random
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (M31-V5 Optimized & Protected) ───
INITIAL_CAPITAL = 10000.0
BASE_MAKER_FEE = 0.0002
LEVERAGE = 5
ENTRY_THRESHOLD = 0.0001    # 0.01%
EXIT_THRESHOLD = 0.00001    # 0.001%
SMOOTHING_PERIODS = 6       # 24 hours (6 * 4h? No, funding is hourly, so 24 periods = 24h. We will use 24 for SMA)
COOLDOWN_PERIODS = 6        # 6 hours wait after exit
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
DAYS = 730

# ─── Data Fetching ───
def fetch_funding_history(symbol, days=DAYS):
    print(f"[{symbol}] Fetching funding history...")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    all_records = []
    current_end = end_ms
    
    while current_end > start_ms:
        current_start = max(start_ms, current_end - (30 * 24 * 3600 * 1000))
        payload = {"type": "fundingHistory", "coin": symbol, "startTime": current_start, "endTime": current_end}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for rec in data:
                    all_records.append({"t": int(rec["time"]), "rate": float(rec["fundingRate"])})
                earliest = min(int(rec["time"]) for rec in data)
                current_end = earliest - 1
            elif r.status_code == 429:
                time.sleep(5)
                continue
        except:
            break
        time.sleep(1.5)
        
    unique = {r["t"]: r for r in all_records}
    return sorted(unique.values(), key=lambda x: x["t"])

# ─── Backtest Engine (With Smoothing & Cooldown) ───
def run_stress_scenario(data, funding_multiplier, fee_multiplier, negative_prob, scenario_name):
    capital_per_sym = INITIAL_CAPITAL / len(SYMBOLS)
    fee = BASE_MAKER_FEE * fee_multiplier
    
    states = {
        sym: {
            "in_position": False, "funding": 0.0, "fees": 0.0, 
            "last_exit_time": 0, "rate_history": []
        } for sym in SYMBOLS
    }
    
    all_events = []
    for sym in SYMBOLS:
        for rec in data.get(sym, []):
            all_events.append({"t": rec["t"], "rate": rec["rate"], "symbol": sym})
    all_events.sort(key=lambda x: x["t"])
    
    total_equity = INITIAL_CAPITAL
    equity_curve = [total_equity]
    
    for event in all_events:
        sym = event["symbol"]
        rate = event["rate"]
        st = states[sym]
        
        # 1. Apply Stress
        if random.random() < negative_prob:
            rate = -abs(rate)
        rate = rate * funding_multiplier
        
        # 2. Update Rolling SMA (24 periods)
        st["rate_history"].append(rate)
        if len(st["rate_history"]) > 24: 
            st["rate_history"].pop(0)
        
        avg_rate = sum(st["rate_history"]) / len(st["rate_history"])
        
        # 3. Logic
        if st["in_position"]:
            if avg_rate > 0:
                funding = capital_per_sym * avg_rate * LEVERAGE
                st["funding"] += funding
                total_equity += funding
            
            # Exit Condition (using smoothed rate)
            if avg_rate < EXIT_THRESHOLD:
                cost = capital_per_sym * fee * 2 * LEVERAGE
                st["fees"] += cost
                total_equity -= cost
                st["in_position"] = False
                st["last_exit_time"] = event["t"]
        else:
            # Entry Condition (SMA > Threshold AND Cooldown Passed)
            time_since_exit = (event["t"] - st["last_exit_time"]) / (3600 * 1000) # in hours
            if avg_rate > ENTRY_THRESHOLD and time_since_exit >= COOLDOWN_PERIODS:
                cost = capital_per_sym * fee * 2 * LEVERAGE
                st["fees"] += cost
                total_equity -= cost
                st["in_position"] = True
                
        equity_curve.append(total_equity)
        
    # Force close remaining
    for sym in SYMBOLS:
        st = states[sym]
        if st["in_position"]:
            cost = capital_per_sym * fee * 2 * LEVERAGE
            st["fees"] += cost
            total_equity -= cost
            st["in_position"] = False
            
    equity_curve.append(total_equity)
    
    # Calculate metrics
    final_eq = equity_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    apy = ((final_eq / INITIAL_CAPITAL) ** (365 / DAYS) - 1) * 100 if DAYS > 0 else 0
    
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    total_funding = sum(st["funding"] for st in states.values())
    total_fees = sum(st["fees"] for st in states.values())
    
    print(f"\n--- {scenario_name} ---")
    print(f"Total Return: {ret:.2f}% | APY: {apy:.2f}% | MaxDD: {max_dd*100:.2f}%")
    print(f"Funding: {total_funding:,.2f} | Fees: {total_fees:,.2f}")
    
    return apy, max_dd

def main():
    print(f"=== M31-V5 Stress Testing (With SMA & Cooldown) ===")
    print(f"Base Capital: {INITIAL_CAPITAL} USDT | Leverage: {LEVERAGE}x\n")
    
    random.seed(42) # For reproducibility of Negative Funding scenario
    
    data = {}
    for sym in SYMBOLS:
        records = fetch_funding_history(sym)
        if records: data[sym] = records
            
    print("\nRunning Scenarios...")
    
    # 1. Base Case
    run_stress_scenario(data, 1.0, 1.0, 0.0, "[1] Base Case")
    
    # 2. Negative Funding 20% Prob (The Critical Test)
    run_stress_scenario(data, 1.0, 1.0, 0.20, "[2] Stress: Negative Funding (20% Prob)")
    
    # 3. Extreme Stress (All Combined)
    run_stress_scenario(data, 0.5, 2.0, 0.20, "[3] Extreme Stress (All Combined)")

if __name__ == "__main__":
    main()
