import json
import os
import math

def calculate_risk_parity_weights(metrics_dict):
    """
    محاسبه وزن بهینه بر اساس معکوس واریانس (Risk Parity ساده‌شده)
    """
    print("=== ⚖️ Portfolio Optimizer (Risk Parity) ===")
    
    # فیلتر کردن استراتژی‌هایی که در OOS معتبر بودند
    valid_strats = {}
    for strat, data in metrics_dict.items():
        if data.get("status") == "OK" and data.get("n", 0) >= 30 and data.get("pf", 0) > 1.2:
            valid_strats[strat] = data
            
    if not valid_strats:
        print("❌ No valid strategies passed the OOS gate. NO_WINNER.")
        return {}
        
    # محاسبه وزن بر اساس معکوس MaxDD (هرچه ریسک کمتر، وزن بیشتر)
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
        
    print("Proposed Allocation (Simulation Only):")
    for strat, w in weights.items():
        print(f"  {strat}: {w*100:.1f}%")
        
    # ذخیره گزارش
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/proposed_allocation.json", "w") as f:
        json.dump(weights, f, indent=2)
        
    return weights

if __name__ == "__main__":
    # تست با داده‌های فرضی (در محیط واقعی از خروجی Sandbox خوانده می‌شود)
    sample_metrics = {
        "M35": {"status": "OK", "n": 45, "pf": 1.9, "max_dd": 2.1},
        "A20": {"status": "OK", "n": 120, "pf": 1.3, "max_dd": 5.0}
    }
    calculate_risk_parity_weights(sample_metrics)
