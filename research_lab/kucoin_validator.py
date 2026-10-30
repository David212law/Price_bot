import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data, calculate_metrics

def validate_all_for_kucoin():
    print("=== 🔍 KuCoin Strategy Validation (D-88 Criteria) ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    strategies = {"M35": strategy_m35, "A8": strategy_a8, "A20": strategy_a20, "M40": strategy_m40}
    
    eligible = {}
    for name, func in strategies.items():
        # تست روی داده OOS (۲۰٪ آخر)
        oos_trades = []
        for sym in symbols:
            candles = load_data("kucoin", sym)
            if not candles: continue
            val_idx = int(len(candles) * 0.8)
            test_data = candles[val_idx:]
            oos_trades.extend(func(test_data))
            
        metrics = calculate_metrics(oos_trades)
        pf = metrics.get("pf", 0)
        n = metrics.get("n", 0)
        max_dd = metrics.get("max_dd", 100)
        
        # تعیین دسته بر اساس D-68 و D-88
        if pf > 1.2 and n >= 30 and max_dd < 15:
            status = "PRIMARY"  # برنده D-68
        elif pf > 1.2 and max_dd < 15:
            status = "DIVERSIFIER"  # برنده D-88
        else:
            status = "REJECTED"  # حذف کامل
            
        eligible[name] = {"pf": pf, "n": n, "max_dd": max_dd, "status": status}
        print(f"  [{name}] PF={pf} | n={n} | MaxDD={max_dd}% | Status: {status}")
    
    import json
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/kucoin_eligibility.json", "w") as f:
        json.dump(eligible, f, indent=2)

if __name__ == "__main__":
    validate_all_for_kucoin()
