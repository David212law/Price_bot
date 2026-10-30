import sys
print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE.")
import json
import os
import math
from collections import defaultdict
from strategies.core_engine import strategy_a8, strategy_a20, strategy_m40, load_data
from research_lab.bale_notifier import send_bale
from research_lab.portfolio_optimizer import calc_correlation, calc_variance

def calculate_hrp():
    print("=== 🧠 HRP Optimizer (Pure Python) ===")
    exchange = "kucoin"
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    # ۱. فقط استراتژی‌های فعال (M35 حذف شد، M31 جداگانه مدیریت می‌شود)
    active_strategies = {"A8": strategy_a8, "A20": strategy_a20, "M40": strategy_m40}
    monthly_returns = {name: defaultdict(float) for name in active_strategies}
    
    for name, func in active_strategies.items():
        for sym in symbols:
            candles = load_data(exchange, sym)
            if not candles: continue
            trades = func(candles)
            for t in trades:
                month = t["t"] // (30 * 24 * 60 * 60 * 1000)
                monthly_returns[name][month] += t["ret"] * 0.01 
                
    all_months = set()
    for name in active_strategies:
        all_months.update(monthly_returns[name].keys())
    sorted_months = sorted(list(all_months))
    
    if len(sorted_months) < 3:
        print("❌ Not enough data.")
        return
        
    strat_names = list(active_strategies.keys())
    returns_arrays = {name: [monthly_returns[name].get(m, 0.0) for m in sorted_months] for name in strat_names}
    
    # ۲. ماتریس همبستگی
    corr_matrix = []
    for s1 in strat_names:
        row = []
        for s2 in strat_names:
            row.append(calc_correlation(returns_arrays[s1], returns_arrays[s2]))
        corr_matrix.append(row)
        
    print("\n📊 Real Correlation Matrix (Full Disclosure - D-197):")
    print(f"{'':10}", end="")
    for s in strat_names:
        print(f"{s:>10}", end="")
    print()
    for i, s1 in enumerate(strat_names):
        print(f"{s1:10}", end="")
        for j in range(len(strat_names)):
            print(f"{corr_matrix[i][j]:>10.2f}", end="")
        print()

    # ۳. ماتریس فاصله و خوشه‌بندی
    dist_matrix = [[math.sqrt(max(0, 0.5 * (1 - corr))) for corr in row] for row in corr_matrix]
    clusters = [[i] for i in range(len(strat_names))]
    while len(clusters) > 1:
        min_dist = float('inf')
        merge_pair = None
        for i in range(len(clusters)):
            for j in range(i+1, len(clusters)):
                d = min(dist_matrix[a][b] for a in clusters[i] for b in clusters[j])
                if d < min_dist:
                    min_dist = d
                    merge_pair = (i, j)
        if merge_pair:
            i, j = merge_pair
            clusters[i].extend(clusters[j])
            clusters.pop(j)
            
    # ۴. تخصیص اولیه (Pre-Cap)
    weights = {}
    for cluster in clusters:
        variances = [calc_variance(returns_arrays[strat_names[idx]]) for idx in cluster]
        inv_vars = [1.0 / (v + 1e-8) for v in variances]
        total = sum(inv_vars)
        for idx, iv in zip(cluster, inv_vars):
            weights[strat_names[idx]] = iv / total / len(clusters)

    # ذخیره وزن‌های Pre-Cap برای نمایش
    pre_cap_weights = weights.copy()

    # ۵. اعمال سقف و کف (D-190)
    for name in weights:
        weights[name] = max(0.05, min(0.30, weights[name]))
    
    # ۶. نرمال‌سازی تکراری (D-199)
    for _ in range(10):
        total_w = sum(weights.values())
        for name in weights:
            weights[name] = weights[name] / total_w
            if weights[name] > 0.30: weights[name] = 0.30
            if weights[name] < 0.05: weights[name] = 0.05
            
    # ۷. نرمال‌سازی نهایی برای دقیقاً ۱۰۰٪
    total_w = sum(weights.values())
    for name in weights:
        weights[name] = round(weights[name] / total_w, 4)
        
    # ─── گزارش نهایی ───
    print("\n🔍 Pre-Cap Weights (D-195):")
    for name, w in pre_cap_weights.items():
        print(f"  {name}: {w*100:.1f}%")
        
    print("\n🏆 Post-Cap HRP Weights (Directional Bucket - 50% of Total):")
    report_msg = "📋 **HRP Allocation (50% Directional Bucket)**\n\n"
    for name, w in weights.items():
        print(f"  {name}: {w*100:.1f}%")
        report_msg += f"• {name}: {round(w*100, 1)}%\n"
    
    send_bale(report_msg)
    
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/hrp_allocation.json", "w") as f:
        json.dump(weights, f, indent=2)

if __name__ == "__main__":
    calculate_hrp()
