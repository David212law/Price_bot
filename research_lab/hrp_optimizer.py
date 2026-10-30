import sys
print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE (D-174).")
import json
import os
import math
from collections import defaultdict
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data
from research_lab.bale_notifier import send_bale
from research_lab.portfolio_optimizer import calc_correlation, calc_variance

def calculate_hrp():
    print("=== 🧠 HRP Optimizer (Pure Python, D-201/202/203) ===")
    exchange = "kucoin"
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    # ۱. بررسی مجوز استراتژی‌ها
    import json
    eligibility_file = "research_lab/logs/kucoin_eligibility.json"
    eligible_names = []
    if os.path.exists(eligibility_file):
        with open(eligibility_file, "r") as f:
            elig = json.load(f)
            eligible_names = [k for k, v in elig.items() if v["status"] in ["PRIMARY", "DIVERSIFIER"]]
    else:
        print("⚠️ Eligibility file not found. Run kucoin_validator first.")
        return
    
    print(f"✅ Eligible strategies (PF>1.2, n>=30): {eligible_names}")
    
    all_strategies = {"M35": strategy_m35, "A8": strategy_a8, "A20": strategy_a20, "M40": strategy_m40}
    active_strategies = {k: v for k, v in all_strategies.items() if k in eligible_names}
    
    # ─── مدیریت تک‌استراتژی (فقط اگر واقعاً یک Diversifier هم نباشد) ───
    if len(active_strategies) == 0:
        print("❌ No eligible strategies. Aborting HRP.")
        return
    elif len(active_strategies) == 1:
        single = list(active_strategies.keys())[0]
        print(f"\n⚠️ Only 1 eligible strategy: {single}. Assigning 100% weight (last resort).")
        weights = {single: 1.0}
        send_bale(f"📋 Only 1 strategy ({single}) survived D-88 filter. 100% assigned.")
        os.makedirs("research_lab/logs", exist_ok=True)
        with open("research_lab/logs/hrp_allocation.json", "w") as f:
            json.dump({"weights": weights}, f, indent=2)
        return
    
    # ─── ادامه HRP برای ۲ یا بیشتر ───
    N = len(active_strategies)
    cap = max(0.30, 1.0/N + 0.05) if N >= 3 else 0.50 
    if N == 3: cap = 0.30
    print(f"ℹ️ Active strategies: {N} | Cap: {cap*100:.0f}% | Floor: 5%")
    
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
    
    # ماتریس همبستگی
    corr_matrix = []
    for s1 in strat_names:
        row = []
        for s2 in strat_names:
            row.append(calc_correlation(returns_arrays[s1], returns_arrays[s2]))
        corr_matrix.append(row)
        
    print("\n📊 Correlation Matrix (Full Disclosure - D-197):")
    print(f"{'':10}", end="")
    for s in strat_names:
        print(f"{s:>10}", end="")
    print()
    for i, s1 in enumerate(strat_names):
        print(f"{s1:10}", end="")
        for j in range(len(strat_names)):
            print(f"{corr_matrix[i][j]:>10.2f}", end="")
        print()

    # ماتریس فاصله و خوشه‌بندی
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
    
    # تخصیص Pre-Cap
    pre_cap = {}
    for cluster in clusters:
        variances = [calc_variance(returns_arrays[strat_names[idx]]) for idx in cluster]
        inv_vars = [1.0 / (v + 1e-8) for v in variances]
        total = sum(inv_vars)
        for idx, iv in zip(cluster, inv_vars):
            pre_cap[strat_names[idx]] = iv / total / len(clusters)
            
    print("\n🔍 Pre-Cap Weights (D-195):")
    for name, w in pre_cap.items():
        print(f"  {name}: {w*100:.1f}%")
    
    # نرمال‌سازی با سقف و کف
    weights = capped_normalize(pre_cap, cap=0.30, floor=0.05)
    
    # اعمال سقف ۲۵٪ برای Diversifiers (D-88)
    for name in weights:
        if name in elig and elig[name]["status"] == "DIVERSIFIER" and weights[name] > 0.25:
            excess = weights[name] - 0.25
            weights[name] = 0.25
            # توزیع به PRIMARY ها
            primaries = [k for k in weights if k in elig and elig[k]["status"] == "PRIMARY"]
            if primaries:
                for p in primaries:
                    weights[p] += excess / len(primaries)
    
    # نرمال‌سازی نهایی
    total = sum(weights.values())
    weights = {n: round(w / total, 4) for n, w in weights.items()}
    
    cap_binding = any(w >= cap - 1e-4 for w in weights.values())
    
    print(f"\n🏆 Post-Cap HRP Weights (Cap={cap*100:.0f}%):")
    report_msg = f"📋 **HRP Allocation (Cap={cap*100:.0f}%)**\n\n"
    for name, w in weights.items():
        print(f"  {name}: {w*100:.1f}%")
        report_msg += f"• {name}: {round(w*100, 1)}%\n"
    
    if cap_binding:
        print(f"\n⚠️ Cap is BINDING: HRP would have concentrated more.")
        report_msg += f"\n⚠️ Cap binding.\n"
    
    total_check = sum(weights.values())
    print(f"\n✅ Sum check: {total_check*100:.1f}% (must be 100.0%)")
    report_msg += f"\nSum: {total_check*100:.1f}%"
    
    send_bale(report_msg)
    
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/hrp_allocation.json", "w") as f:
        json.dump({"weights": weights, "cap": cap, "pre_cap": pre_cap, "cap_binding": cap_binding}, f, indent=2)

# تابع نرمال‌سازی (همانند قبل)
def capped_normalize(weights, cap, floor=0.05, max_iter=100):
    weights = dict(weights)
    names = list(weights.keys())
    for iteration in range(max_iter):
        total = sum(weights.values())
        if total <= 0: break
        weights = {n: weights[n] / total for n in names}
        if all(floor - 1e-9 <= weights[n] <= cap + 1e-9 for n in names): break
        excess = 0
        for n in names:
            if weights[n] > cap:
                excess += weights[n] - cap
                weights[n] = cap
        if excess > 0:
            uncapped = [n for n in names if weights[n] < cap - 1e-9]
            uncapped_sum = sum(weights[n] for n in uncapped)
            if uncapped_sum > 1e-9:
                for n in uncapped:
                    weights[n] += excess * (weights[n] / uncapped_sum)
        deficit = 0
        for n in names:
            if weights[n] < floor:
                deficit += floor - weights[n]
                weights[n] = floor
        if deficit > 0:
            above_floor = [n for n in names if weights[n] > floor + 1e-9]
            above_sum = sum(weights[n] - floor for n in above_floor)
            if above_sum > 1e-9:
                for n in above_floor:
                    weights[n] -= deficit * ((weights[n] - floor) / above_sum)
    total = sum(weights.values())
    if total > 0:
        weights = {n: round(weights[n] / total, 4) for n in names}
    return weights

if __name__ == "__main__":
    calculate_hrp()
