import sys, os
sys.path.append(os.getcwd())
import json
import itertools
from strategies.core_engine import strategy_m35, load_data, calculate_metrics
from research_lab.budget_manager import check_budget, log_test, load_ledger

def run_auto_discovery():
    print("=== 🤖 Auto-Discovery Engine Started ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    fast_emas = [20, 50]
    slow_emas = [100, 200]
    
    # دریافت تاریخچه تست‌های انجام شده
    existing_ledger = load_ledger()
    existing_strats = {entry["strategy"] for entry in existing_ledger}
    
    for fast, slow in itertools.product(fast_emas, slow_emas):
        if fast >= slow: continue
        strat_name = f"M35_EMA({fast},{slow})"
        
        # اگر قبلا تست شده، رد شو (جلوگیری از هدر دادن بودجه)
        if strat_name in existing_strats:
            print(f"⏭️ Skipping {strat_name} (already tested).")
            continue
            
        if not check_budget():
            print("🛑 Stopping discovery due to monthly budget limit.")
            break
            
        print(f"Testing Hypothesis: {strat_name}...")
        
        all_trades = []
        for sym in symbols:
            candles = load_data("kucoin", sym)
            if candles:
                split_idx = int(len(candles) * 0.7)
                all_trades.extend(strategy_m35(candles[:split_idx], fast=fast, slow=slow))
                
        metrics = calculate_metrics(all_trades)
        log_test(strat_name, metrics)
        print(f"  Result: PF={metrics.get('pf', 0)} | n={metrics.get('n', 0)}")

if __name__ == "__main__":
    run_auto_discovery()
