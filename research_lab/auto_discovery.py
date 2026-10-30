import sys, os
sys.path.append(os.getcwd())
import json, itertools
from strategies.core_engine import strategy_m35, strategy_m40, load_data, calculate_metrics
from research_lab.budget_manager import check_budget, log_test, load_ledger
from research_lab.bale_notifier import send_bale

def run_auto_discovery():
    print("=== 🤖 Auto-Discovery Engine Started ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    fast_emas, slow_emas = [20, 50], [100, 200]
    existing_ledger = load_ledger()
    existing_strats = {entry["strategy"] for entry in existing_ledger}
    
    for fast, slow in itertools.product(fast_emas, slow_emas):
        if fast >= slow: continue
        strat_name = f"M35_EMA({fast},{slow})"
        if strat_name in existing_strats: continue
        if not check_budget(): break
            
        all_trades = []
        for sym in symbols:
            candles = load_data("kucoin", sym)
            if candles:
                split_idx = int(len(candles) * 0.6) # Train 60%
                all_trades.extend(strategy_m35(candles[:split_idx], fast=fast, slow=slow))
                
        metrics = calculate_metrics(all_trades)
        log_test(strat_name, metrics)
        
        if metrics.get("pf", 0) > 1.2 and metrics.get("n", 0) >= 30:
            send_bale(f"🎯 New Winner Found: {strat_name}\nPF: {metrics['pf']} | n: {metrics['n']}")

if __name__ == "__main__":
    run_auto_discovery()
