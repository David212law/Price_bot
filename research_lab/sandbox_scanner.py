import json
import os
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, load_data, calculate_metrics
from research_lab.budget_manager import check_budget, log_test

def split_data(candles, train_ratio=0.7):
    split_idx = int(len(candles) * train_ratio)
    return candles[:split_idx], candles[split_idx:]

def run_secure_scan():
    if not check_budget():
        print("Test aborted due to budget limit.")
        return
        
    print("=== SECURE SANDBOX SCAN (IS/OOS Split) ===")
    # تست فقط روی KuCoin
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    strategies = {"M35": strategy_m35, "A8": strategy_a8, "A20": strategy_a20}
    
    for name, func in strategies.items():
        is_trades, oos_trades = [], []
        for sym in symbols:
            candles = load_data("kucoin", sym)
            if not candles: continue
            
            # ۱. تفکیک مکانیکی داده
            train_data, test_data = split_data(candles)
            
            # ۲. تست روی In-Sample (آموزش)
            is_trades.extend(func(train_data))
            
            # ۳. تست روی Out-of-Sample (داوری)
            oos_trades.extend(func(test_data))
            
        # محاسبه متریک‌ها
        is_metrics = calculate_metrics(is_trades)
        oos_metrics = calculate_metrics(oos_trades)
        
        # محاسبه نسبت OOS/IS (D-82)
        if is_metrics.get("pf", 0) > 0 and oos_metrics.get("status") == "OK":
            ratio = oos_metrics["pf"] / is_metrics["pf"]
        else:
            ratio = 0
            
        print(f"[{name}] IS_PF={is_metrics.get('pf')} | OOS_PF={oos_metrics.get('pf')} | OOS/IS Ratio={ratio:.2f}")
        
        # ۴. ثبت در دفتر آزمون (Trial Ledger)
        log_test(name, {"IS": is_metrics, "OOS": oos_metrics, "OOS_IS_Ratio": ratio})

if __name__ == "__main__":
    run_secure_scan()
