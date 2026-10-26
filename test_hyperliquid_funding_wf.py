import json
import os
import math
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (M31-V6 Balanced Logic) ───
INITIAL_CAPITAL = 10000.0
BASE_MAKER_FEE = 0.0002
LEVERAGE = 5
SMA_PERIODS = 12
ENTRY_THRESHOLD_SMA = 0.00005  # 0.005%
EXIT_THRESHOLD_SMA = 0.00001   # 0.001%
COOLDOWN_PERIODS = 3           # 3 hours
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

# ─── Window Backtest Engine ───
def run_window(data, start_time, end_time, window_name):
    capital_per_sym = INITIAL_CAPITAL / len(SYMBOLS)
    
    states = {
        sym: {"in_position": False, "funding": 0.0, "fees": 0.0, "last_exit_time": start_time, "rate_history": []} 
        for sym in SYMBOLS
    }
    
    all_events = []
    for sym in SYMBOLS:
        for rec in data.get(sym, []):
            if start_time <= rec["t"] < end_time:
                all_events.append({"t": rec["t"], "rate": rec["rate"], "symbol": sym})
    all_events.sort(key=lambda x: x["t"])
    
    total_equity = INITIAL_CAPITAL
    equity_curve = [total_equity]
    
    for event in all_events:
        sym = event["symbol"]
        rate = event["rate"]
        st = states[sym]
        
        st["rate_history"].append(rate)
        if len(st["rate_history"]) > SMA_PERIODS: 
            st["rate_history"].pop(0)
        
        avg_rate = sum(st["rate_history"]) / len(st["rate_history"])
        
        if st["in_position"]:
            if rate > 0:
                funding = capital_per_sym * rate * LEVERAGE
                st["funding"] += funding
                total_equity += funding
            
            if avg_rate < EXIT_THRESHOLD_SMA:
                cost = capital_per_sym * BASE_MAKER_FEE * 2 * LEVERAGE
                st["fees"] += cost
                total_equity -= cost
                st["in_position"] = False
                st["last_exit_time"] = event["t"]
        else:
            time_since_exit = (event["t"] - st["last_exit_time"]) / (3600 * 1000)
            if avg_rate > ENTRY_THRESHOLD_SMA and rate > 0 and time_since_exit >= COOLDOWN_PERIODS:
                cost = capital_per_sym * BASE_MAKER_FEE * 2 * LEVERAGE
                st["fees"] += cost
                total_equity -= cost
                st["in_position"] = True
                
        equity_curve.append(total_equity)
        
    # Force close
    for sym in SYMBOLS:
        st = states[sym]
        if st["in_position"]:
            cost = capital_per_sym * BASE_MAKER_FEE * 2 * LEVERAGE
            st["fees"] += cost
            total_equity -= cost
            
    equity_curve.append(total_equity)
    
    ret = ((total_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    peak = INITIAL_CAPITAL
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    print(f"\n--- {window_name} ---")
    print(f"Return: {ret:.2f}% | MaxDD: {max_dd*100:.2f}%")
    
    return ret

def main():
    print(f"=== M31-V6 Walk-Forward Analysis (4 Windows) ===")
    
    data = {}
    for sym in SYMBOLS:
        records = fetch_funding_history(sym)
        if records: data[sym] = records
    
    if not data:
        print("No data.")
        return
        
    # Find absolute min and max times across all data
    all_times = [rec["t"] for sym_data in data.values() for rec in sym_data]
    global_start = min(all_times)
    global_end = max(all_times)
    
    total_duration = global_end - global_start
    window_size = total_duration // 4
    
    print(f"\nTotal Data Range: {total_duration / (24*3600*1000):.1f} days")
    print(f"Window Size: {window_size / (24*3600*1000):.1f} days\n")
    
    win_returns = []
    
    for i in range(4):
        w_start = global_start + (i * window_size)
        w_end = w_start + window_size if i < 3 else global_end
        
        start_str = datetime.fromtimestamp(w_start/1000, timezone.utc).strftime('%Y-%m-%d')
        end_str = datetime.fromtimestamp(w_end/1000, timezone.utc).strftime('%Y-%m-%d')
        
        ret = run_window(data, w_start, w_end, f"Window {i+1} ({start_str} to {end_str})")
        win_returns.append(ret)
        
    print("\n=== WALK-FORWARD SUMMARY ===")
    profitable_windows = sum(1 for r in win_returns if r > 0)
    print(f"Profitable Windows: {profitable_windows} / 4")
    
    passed = (profitable_windows >= 3)
    print(f"\nFinal WF Status: {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
