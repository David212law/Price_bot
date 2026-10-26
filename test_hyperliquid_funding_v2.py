import json
import os
import math
import random
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (M31-V2 Optimized) ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0002  # 0.02% per side
ENTRY_THRESHOLD = 0.0005   # 0.05% per hour
EXIT_THRESHOLD = 0.0001    # 0.01% per hour
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
DAYS = 730

# ─── Data Fetching (Paginated) ───
def fetch_funding_history(symbol, days=DAYS):
    print(f"[{symbol}] Fetching funding history ({days} days)...")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)
    
    url = "https://api.hyperliquid.xyz/info"
    all_records = []
    current_end = end_ms
    chunk_count = 0
    
    while current_end > start_ms:
        # Fetch 30-day chunks
        current_start = max(start_ms, current_end - (30 * 24 * 3600 * 1000))
        payload = {
            "type": "fundingHistory",
            "coin": symbol,
            "startTime": current_start,
            "endTime": current_end
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data:
                    break
                for rec in data:
                    all_records.append({
                        "t": int(rec["time"]),
                        "rate": float(rec["fundingRate"])
                    })
                # Move cursor back to earliest record in this chunk
                earliest = min(int(rec["time"]) for rec in data)
                current_end = earliest - 1
                chunk_count += 1
            else:
                print(f"  Error at chunk: {r.status_code}")
                break
        except Exception as e:
            print(f"  Exception: {e}")
            break
        time.sleep(0.2)
    
    # Deduplicate and sort
    unique = {r["t"]: r for r in all_records}
    sorted_records = sorted(unique.values(), key=lambda x: x["t"])
    
    if sorted_records:
        first_date = datetime.fromtimestamp(sorted_records[0]["t"]/1000, timezone.utc).strftime('%Y-%m-%d')
        last_date = datetime.fromtimestamp(sorted_records[-1]["t"]/1000, timezone.utc).strftime('%Y-%m-%d')
        print(f"[{symbol}] Received {len(sorted_records)} records (from {first_date} to {last_date}) in {chunk_count} chunks.")
    return sorted_records

# ─── Metrics ───
def block_bootstrap_p_value(equity_curve, block_size=24, iterations=500):
    # block_size=24 hours = 1 day
    if len(equity_curve) < block_size * 2: return 1.0
    rets = [(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1] for i in range(1, len(equity_curve)) if equity_curve[i-1] > 0]
    actual_final = equity_curve[-1] / equity_curve[0]
    n_blocks = len(rets) // block_size
    if n_blocks < 2: return 1.0
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

# ─── Backtest Engine ───
def run_backtest(data):
    capital_per_sym = INITIAL_CAPITAL / len(SYMBOLS)
    
    # State tracking per symbol
    states = {}
    for sym in SYMBOLS:
        states[sym] = {"in_position": False, "entry_time": None, "funding_earned": 0.0, "fees_paid": 0.0, "num_trades": 0}
    
    # Merge all events into a single timeline
    all_events = []
    for sym in SYMBOLS:
        for rec in data.get(sym, []):
            all_events.append({"t": rec["t"], "rate": rec["rate"], "symbol": sym})
    
    all_events.sort(key=lambda x: x["t"])
    
    total_equity = INITIAL_CAPITAL
    equity_curve = [total_equity]
    trades = []
    
    for event in all_events:
        sym = event["symbol"]
        rate = event["rate"]
        st = states[sym]
        
        if st["in_position"]:
            # Earn funding (positive funding = short position earning)
            if rate > 0:
                funding = capital_per_sym * rate
                st["funding_earned"] += funding
                total_equity += funding
            
            # Exit check
            if rate < EXIT_THRESHOLD:
                # Pay exit fees (both legs)
                fee = capital_per_sym * MAKER_FEE * 2
                st["fees_paid"] += fee
                total_equity -= fee
                
                trades.append({
                    "symbol": sym, "entry_time": st["entry_time"], "exit_time": event["t"],
                    "funding": st["funding_earned"], "fees": st["fees_paid"]
                })
                st["in_position"] = False
                st["funding_earned"] = 0
                st["fees_paid"] = 0
                st["num_trades"] += 1
        else:
            # Entry check
            if rate > ENTRY_THRESHOLD:
                fee = capital_per_sym * MAKER_FEE * 2
                st["fees_paid"] += fee
                total_equity -= fee
                st["in_position"] = True
                st["entry_time"] = event["t"]
        
        equity_curve.append(total_equity)
    
    # Force close any remaining positions at the end
    for sym in SYMBOLS:
        st = states[sym]
        if st["in_position"]:
            fee = capital_per_sym * MAKER_FEE * 2
            st["fees_paid"] += fee
            total_equity -= fee
            trades.append({
                "symbol": sym, "entry_time": st["entry_time"], "exit_time": all_events[-1]["t"] if all_events else 0,
                "funding": st["funding_earned"], "fees": st["fees_paid"]
            })
    
    equity_curve.append(total_equity)
    return equity_curve, trades, states

def main():
    print(f"=== M31-V2: Optimized Funding Arbitrage ===")
    print(f"Capital: {INITIAL_CAPITAL} USDT | Symbols: {len(SYMBOLS)}")
    print(f"Entry: >{ENTRY_THRESHOLD*100:.4f}%/hr | Exit: <{EXIT_THRESHOLD*100:.4f}%/hr | Fee: {MAKER_FEE*100}%\n")
    
    data = {}
    for sym in SYMBOLS:
        records = fetch_funding_history(sym)
        if records:
            data[sym] = records
    
    if not data:
        print("No data fetched. Aborting.")
        return
    
    print("\nRunning Backtest...")
    eq_curve, trades, states = run_backtest(data)
    
    final_eq = eq_curve[-1]
    ret = ((final_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    # MaxDD
    peak = eq_curve[0]
    max_dd = 0.0
    for val in eq_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
    
    # APY
    days_elapsed = DAYS
    apy = ((final_eq / INITIAL_CAPITAL) ** (365 / days_elapsed) - 1) * 100 if days_elapsed > 0 else 0
    
    # P-Value
    pval = block_bootstrap_p_value(eq_curve)
    
    # Total funding and fees
    total_funding = sum(st["funding_earned"] if not st["in_position"] else st["funding_earned"] for st in states.values())
    total_fees = sum(st["fees_paid"] for st in states.values())
    total_trades = sum(st["num_trades"] for st in states.values())
    
    print("\n=== FINAL RESULTS ===")
    print(f"Total Return: {ret:.2f}%")
    print(f"APY: {apy:.2f}%")
    print(f"MaxDD: {max_dd*100:.2f}%")
    print(f"P-Value: {pval:.4f}")
    print(f"Total Trades: {total_trades}")
    
    print("\n--- Symbol Breakdown ---")
    for sym in SYMBOLS:
        st = states[sym]
        print(f"[{sym}] Funding Earned: {st['funding_earned']:.2f} | Fees Paid: {st['fees_paid']:.2f} | Trades: {st['num_trades']}")
    
    # Gate: APY > 10% | MaxDD < 5% | P-Value < 0.05
    passed = (apy > 10.0 and max_dd < 0.05 and pval < 0.05)
    print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")

if __name__ == "__main__":
    main()
