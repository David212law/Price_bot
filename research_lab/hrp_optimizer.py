print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE.")
import json
import os
import math
from collections import defaultdict
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data
from research_lab.bale_notifier import send_bale
from research_lab.portfolio_optimizer import calc_correlation, calc_variance

def calculate_hrp():
    print("=== 🧠 HRP Optimizer (Pure Python) ===")
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
        print("❌ Not enough data.")
        return
        
    strat_names = list(strategies.keys())
    returns_arrays = {name: [monthly_returns[name].get(m, 0.0) for m in sorted_months] for name in strat_names}
    
    # ۱. ماتریس همبستگی
    corr_matrix = []
    for s1 in strat_names:
        row = []
        for s2 in strat_names:
            row.append(calc_correlation(returns_arrays[s1], returns_arrays[s2]))
        corr_matrix.append(row)
        
    # ۲. ماتریس فاصله
    dist_matrix = [[math.sqrt(max(0, 0.5 * (1 - corr))) for corr in row] for row in corr_matrix]
    
    # ۳. خوشه‌بندی (Single-Linkage ساده)
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
            
    # ۴. تخصیص ریسک برابر درون خوشه‌ها
    weights = {}
    for cluster in clusters:
        variances = [calc_variance(returns_arrays[strat_names[idx]]) for idx in cluster]
        inv_vars = [1.0 / (v + 1e-8) for v in variances]
        total = sum(inv_vars)
        for idx, iv in zip(cluster, inv_vars):
            weights[strat_names[idx]] = iv / total / len(clusters)
    
    # ۵. اعمال سقف و کف (D-190)
    for name in weights:
        weights[name] = max(0.05, min(0.30, weights[name]))
    
    # نرمال‌سازی
    total_w = sum(weights.values())
    for name in weights:
        weights[name] = round(weights[name] / total_w, 4)
        
    # گزارش
    print("\n🏆 HRP Optimized Weights:")
    report_msg = "📋 **HRP Portfolio Allocation**\n\n"
    for name, w in weights.items():
        print(f"  {name}: {w*100:.1f}%")
        report_msg += f"• {name}: {w*100:.1f}%\n"
    
    send_bale(report_msg)
    
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/hrp_allocation.json", "w") as f:
        json.dump(weights, f, indent=2)

if __name__ == "__main__":
    calculate_hrp()
