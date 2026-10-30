import sys
print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE (D-174).")
import json
import os
import numpy as np
from research_lab.bale_notifier import send_bale

LEDGER_PATH = "research_lab/logs/trial_ledger.json"

def calculate_correlation_matrix():
    print("=== 🧠 Portfolio Architect: Correlation Matrix ===")
    
    # برای شبیه‌سازی همبستگی، از داده‌های شبیه‌سازی شده استفاده می‌کنیم
    # (در محیط واقعی، باید بازدهی روزانه هر استراتژی از ledger خوانده شود)
    strategies = ["M35_EMA(20,200)", "A8_Grid", "A20_SuperTrend", "M40_Pullback"]
    
    # شبیه‌سازی بازدهی روزانه (برای نمایش کارکرد)
    np.random.seed(42)
    returns = {
        "M35_EMA(20,200)": np.random.normal(0.001, 0.02, 100),
        "A8_Grid": np.random.normal(0.0005, 0.01, 100),
        "A20_SuperTrend": np.random.normal(0.0008, 0.025, 100),
        "M40_Pullback": np.random.normal(0.0006, 0.015, 100)
    }
    
    # محاسبه ماتریس همبستگی
    df = np.array([returns[s] for s in strategies])
    corr_matrix = np.corrcoef(df)
    
    print("\n📊 Correlation Matrix:")
    print(f"{'':20}", end="")
    for s in strategies:
        print(f"{s[:10]:>12}", end="")
    print()
    
    for i, s1 in enumerate(strategies):
        print(f"{s1[:20]:20}", end="")
        for j in range(len(strategies)):
            print(f"{corr_matrix[i][j]:>12.2f}", end="")
        print()
        
    # شناسایی استراتژی‌های مکمل (همبستگی < 0.3)
    print("\n🔍 Complementary Analysis:")
    complementary_found = False
    for i in range(len(strategies)):
        for j in range(i+1, len(strategies)):
            corr = corr_matrix[i][j]
            if corr < 0.3:
                print(f"  ✅ {strategies[i]} & {strategies[j]}: Correlation={corr:.2f} (Complementary)")
                complementary_found = True
            elif corr > 0.7:
                print(f"  ⚠️ {strategies[i]} & {strategies[j]}: Correlation={corr:.2f} (Highly Correlated - avoid both)")
                
    if complementary_found:
        send_bale("🧠 Portfolio Architect: Complementary pairs found! Check logs.")
    
    # ذخیره گزارش
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/correlation_matrix.json", "w") as f:
        json.dump({"strategies": strategies, "matrix": corr_matrix.tolist()}, f, indent=2)

if __name__ == "__main__":
    calculate_correlation_matrix()
