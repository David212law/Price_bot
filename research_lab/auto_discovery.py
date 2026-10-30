import sys, os
sys.path.append(os.getcwd())
import json
import itertools
from strategies.core_engine import strategy_m35, load_data, calculate_metrics
from research_lab.budget_manager import check_budget, log_test

def run_auto_discovery():
    print("=== 🤖 Auto-Discovery Engine Started ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    # تولید پارامترهای مختلف برای M35 (Grid Search محدود)
    fast_emas = [20, 50]
    slow_emas = [100, 200]
    
    for fast, slow in itertools.product(fast_emas, slow_emas):
        if fast >= slow: continue
        
        # بررسی بودجه قبل از هر تست
        if not check_budget():
            print("🛑 Stopping discovery due to monthly budget limit.")
            break
            
        print(f"Testing Hypothesis: M35_EMA({fast},{slow})...")
        
        all_trades = []
        for sym in symbols:
            candles = load_data("kucoin", sym)
            if candles:
                # در محیط ایزوله، صرفاً ۷۰٪ داده اول (IS) را برای کشف استفاده می‌کنیم
                split_idx = int(len(candles) * 0.7)
                all_trades.extend(strategy_m35(candles[:split_idx], fast=fast, slow=slow))
                
        metrics = calculate_metrics(all_trades)
        
        # ثبت در دفتر آزمون (Trial Ledger)
        log_test(f"M35_EMA({fast},{slow})", metrics)
        
        print(f"  Result: PF={metrics.get('pf', 0)} | n={metrics.get('n', 0)}")

if __name__ == "__main__":
    run_auto_discovery()
