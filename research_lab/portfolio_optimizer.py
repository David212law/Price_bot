import sys
print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE (D-174).")
import json
import os
import math
from collections import defaultdict
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data
from research_lab.bale_notifier import send_bale

def calc_correlation(x, y):
    n = len(x)
    if n == 0: return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    std_x = math.sqrt(sum((a - mean_x)**2 for a in x))
    std_y = math.sqrt(sum((b - mean_y)**2 for b in y))
    if std_x == 0 or std_y == 0: return 0.0
    return cov / (std_x * std_y)

def calc_variance(x):
    n = len(x)
    if n == 0: return 0.0
    mean_x = sum(x) / n
    return sum((a - mean_x)**2 for a in x) / n

def calculate_real_correlation():
    print("=== 🧠 Portfolio Architect: Monthly Correlation Matrix (Pure Python) ===")
    exchange = "kucoin"
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    strategies = {"M35": strategy_m35, "A8": strategy_a8, "A20": strategy_a20, "M40": strategy_m40}
    monthly_returns = {name: defaultdict(float) for name in strategies}
    
    for name, func in strategies.items():
        for sym in symbols:
            candles = load_data(exchange, sym)
            if not candles: continue
            trades = func(candles)
            for t in trades:
                month = t["t"] // (30 * 24 * 60 * 60 * 1000)
                monthly_returns[name][month] += t["ret"] * 0.01 
                
    all_months = set()
    for name in strategies:
        all_months.update(monthly_returns[name].keys())
    sorted_months = sorted(list(all_months))
    
    if len(sorted_months) < 3:
        print("❌ Not enough data for monthly correlation.")
        return
        
    strat_names = list(strategies.keys())
    returns_arrays = {name: [monthly_returns[name].get(m, 0.0) for m in sorted_months] for name in strat_names}
    
    # ساخت ماتریس همبستگی دستی
    corr_matrix = []
    for s1 in strat_names:
        row = []
        for s2 in strat_names:
            row.append(calc_correlation(returns_arrays[s1], returns_arrays[s2]))
        corr_matrix.append(row)
    
    print("\n📊 Real Correlation Matrix (Monthly Aggregated):")
    print(f"{'':15}", end="")
    for s in strat_names:
        print(f"{s:>10}", end="")
    print()
    
    for i, s1 in enumerate(strat_names):
        print(f"{s1:15}", end="")
        for j in range(len(strat_names)):
            print(f"{corr_matrix[i][j]:>10.2f}", end="")
        print()
        
    print("\n🔍 Complementary Analysis:")
    for i in range(len(strat_names)):
        for j in range(i+1, len(strat_names)):
            corr = corr_matrix[i][j]
            if corr < 0.3:
                print(f"  ✅ {strat_names[i]} & {strat_names[j]}: Corr={corr:.2f} (Complementary)")
            elif corr > 0.7:
                print(f"  ⚠️ {strat_names[i]} & {strat_names[j]}: Corr={corr:.2f} (Highly Correlated)")

    send_bale("🧠 Portfolio Architect: Monthly correlation matrix calculated.")
    
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/real_correlation_matrix.json", "w") as f:
        json.dump({"strategies": strat_names, "matrix": corr_matrix}, f, indent=2)

if __name__ == "__main__":
    calculate_real_correlation()
