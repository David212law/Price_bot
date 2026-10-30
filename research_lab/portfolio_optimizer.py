import sys
print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE (D-174).")
import json
import os
import numpy as np
from research_lab.bale_notifier import send_bale

LEDGER_PATH = "research_lab/logs/trial_ledger.json"

def calculate_optimizer():
    print("=== ⚖️ Portfolio Optimizer (Correlation Matrix & Risk Parity) ===")
    if not os.path.exists(LEDGER_PATH): return
        
    with open(LEDGER_PATH, "r") as f:
        ledger = json.load(f)
        
    valid_strats = {}
    for entry in ledger:
        metrics = entry.get("metrics", {})
        if metrics.get("status") == "OK" and metrics.get("n", 0) >= 30 and metrics.get("pf", 0) > 1.2:
            strat_name = entry["strategy"]
            if strat_name not in valid_strats or metrics["pf"] > valid_strats[strat_name]["pf"]:
                valid_strats[strat_name] = metrics
            
    if not valid_strats:
        print("❌ NO_WINNER.")
        return {}
        
    # محاسبه Risk Parity
    total_inv_risk = 0
    weights = {}
    for strat, data in valid_strats.items():
        risk = max(data["max_dd"], 1.0)
        weights[strat] = 1.0 / risk
        total_inv_risk += weights[strat]
        
    for strat in weights:
        weights[strat] = round(weights[strat] / total_inv_risk, 4)
        
    # گزارش نهایی
    report_msg = "📋 **Auto-Research Candidate Report**\n\n"
    for strat, w in weights.items():
        report_msg += f"• {strat}: {w*100:.1f}% (MaxDD: {valid_strats[strat]['max_dd']}%)\n"
        
    print(report_msg)
    send_bale(report_msg)
    
    with open("research_lab/logs/proposed_allocation.json", "w") as f:
        json.dump(weights, f, indent=2)

if __name__ == "__main__":
    calculate_optimizer()
