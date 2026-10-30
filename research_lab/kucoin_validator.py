import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data, calculate_metrics

def validate_all_for_kucoin():
    print("=== 🔍 KuCoin Strategy Validation (D-211) ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    strategies = {"M35": strategy_m35, "A8": strategy_a8, "A20": strategy_a20, "M40": strategy_m40}
    
    eligible = {}
    for name, func in strategies.items():
        oos_trades = []
        for sym in symbols:
            candles = load_data("kucoin", sym)
            if not candles: continue
            train_idx = int(len(candles) * 0.6)
            val_idx = int(len(candles) * 0.8)
            test_data = candles[val_idx:]
            oos_trades.extend(func(test_data))
            
        metrics = calculate_metrics(oos_trades)
        pf = metrics.get("pf", 0)
        n = metrics.get("n", 0)
        
        status = "ELIGIBLE" if (pf > 1.2 and n >= 30) else "NOT_ELIGIBLE"
        eligible[name] = {"pf": pf, "n": n, "status": status}
        print(f"  [{name}] PF={pf} | n={n} | Status: {status}")
    
    import json
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/kucoin_eligibility.json", "w") as f:
        json.dump(eligible, f, indent=2)

if __name__ == "__main__":
    validate_all_for_kucoin()
