import sys, os
sys.path.append(os.getcwd())
import json
import os

LEDGER_PATH = "research_lab/logs/trial_ledger.json"

def calculate_risk_parity_weights():
    print("=== ⚖️ Portfolio Optimizer (Risk Parity from Real Ledger) ===")
    
    if not os.path.exists(LEDGER_PATH):
        print("❌ Trial ledger not found. Run discovery first.")
        return
        
    with open(LEDGER_PATH, "r") as f:
        ledger = json.load(f)
        
    # فیلتر کردن استراتژی‌هایی که در OOS معتبر بودند
    valid_strats = {}
    for entry in ledger:
        # فقط تست‌های OOS یا تست‌های با n معتبر را در نظر می‌گیریم
        metrics = entry.get("metrics", {})
        if metrics.get("status") == "OK" and metrics.get("n", 0) >= 30 and metrics.get("pf", 0) > 1.2:
            strat_name = entry["strategy"]
            # اگر چند بار تست شده، بهترین نتیجه را نگه می‌داریم (برای گزارش)
            if strat_name not in valid_strats or metrics["pf"] > valid_strats[strat_name]["pf"]:
                valid_strats[strat_name] = metrics
            
    if not valid_strats:
        print("❌ No valid strategies passed the OOS gate. NO_WINNER.")
        return {}
        
    # محاسبه وزن بر اساس معکوس MaxDD (Risk Parity)
    total_inv_risk = 0
    weights = {}
    for strat, data in valid_strats.items():
        risk = max(data["max_dd"], 1.0) # جلوگیری از تقسیم بر صفر
        inv_risk = 1.0 / risk
        weights[strat] = inv_risk
        total_inv_risk += inv_risk
        
    # نرمال‌سازی وزن‌ها
    for strat in weights:
        weights[strat] = round(weights[strat] / total_inv_risk, 4)
        
    print("🏆 Proposed Allocation (Simulation Only):")
    for strat, w in weights.items():
        print(f"  {strat}: {w*100:.1f}% (Risk: {valid_strats[strat]['max_dd']}%)")
        
    # ذخیره گزارش
    with open("research_lab/logs/proposed_allocation.json", "w") as f:
        json.dump(weights, f, indent=2)

if __name__ == "__main__":
    calculate_risk_parity_weights()
