import os, json, math
from collections import defaultdict
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data

def run_parity_test():
    print("=== 🔬 Parity Test (D-198) + HRP on M31+A20+M40 ===\n")
    SYMBOLS = ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]
    STRATS = {"A20": strategy_a20, "M40": strategy_m40}
    
    # ─── محاسبه بازدهی ماهانه A20 و M40 ───
    monthly = {n: defaultdict(float) for n in STRATS}
    for name, func in STRATS.items():
        for sym in SYMBOLS:
            cd = load_data("kucoin", sym)
            if not cd: continue
            for t in func(cd):
                m = t["t"] // (30*24*60*60*1000)
                monthly[name][m] += t["ret"] * 0.01
    
    all_m = sorted(set(m for n in STRATS for m in monthly[n]))
    rets = {n: [monthly[n].get(m, 0.0) for m in all_m] for n in STRATS}
    
    # ─── HRP ساده (پیاده‌سازی خودمان) ───
    def corr(x, y):
        n = len(x); mx = sum(x)/n; my = sum(y)/n
        c = sum((a-mx)*(b-my) for a, b in zip(x, y))
        sx = math.sqrt(sum((a-mx)**2 for a in x)); sy = math.sqrt(sum((b-my)**2 for b in y))
        return c/(sx*sy) if sx*sy > 0 else 0
    
    def var(x):
        n = len(x); m = sum(x)/n
        return sum((a-m)**2 for a in x)/n
    
    names = list(STRATS.keys())
    N = len(names)
    
    # ماتریس همبستگی
    cm = [[corr(rets[a], rets[b]) for b in names] for a in names]
    print("Correlation Matrix:")
    for i, a in enumerate(names):
        print(f"  {a:5} " + " ".join(f"{cm[i][j]:6.2f}" for j in range(N)))
    
    # فاصله و خوشه‌بندی
    dm = [[math.sqrt(max(0, 0.5*(1-cm[i][j]))) for j in range(N)] for i in range(N)]
    clusters = [[i] for i in range(N)]
    while len(clusters) > 1:
        md = float('inf'); mp = None
        for i in range(len(clusters)):
            for j in range(i+1, len(clusters)):
                d = min(dm[a][b] for a in clusters[i] for b in clusters[j])
                if d < md: md = d; mp = (i, j)
        if mp:
            i, j = mp
            clusters[i].extend(clusters[j]); clusters.pop(j)
    
    # تخصیص
    pre_cap = {}
    for cl in clusters:
        vs = [var(rets[names[idx]]) for idx in cl]
        ivs = [1.0/(v+1e-8) for v in vs]
        tot = sum(ivs)
        for idx, iv in zip(cl, ivs):
            pre_cap[names[idx]] = iv/tot/len(clusters)
    
    print("\nPre-Cap Weights (Directional Bucket):")
    for n, w in pre_cap.items():
        print(f"  {n}: {w*100:.2f}%")
    
    # ─── مقایسه با D-218 (M31=50%, A20=25%, M40=25%) ───
    print("\n=== 📊 مقایسه با D-218 ===")
    print(f"D-218 (دستی):  M31=50%, A20=25%, M40=25%")
    print(f"HRP (الگوریتم): M31=50% (ثابت Funding Bucket), A20={pre_cap.get('A20',0)*50:.1f}%, M40={pre_cap.get('M40',0)*50:.1f}%")
    diff_a20 = abs(25 - pre_cap.get('A20', 0)*50)
    diff_m40 = abs(25 - pre_cap.get('M40', 0)*50)
    print(f"\nاختلاف A20: {diff_a20:.1f}٪ | اختلاف M40: {diff_m40:.1f}٪")
    
    if max(diff_a20, diff_m40) <= 5:
        print("✅ Parity OK: اختلاف < 5٪. D-218 تایید می‌شود.")
        verdict = "APPROVED"
    else:
        print("⚠️ Parity FAIL: اختلاف > 5٪. D-218 نیازمند اصلاح است.")
        verdict = "NEEDS_REVISION"
    
    # ─── همبستگی A20-M40 (D-221) ───
    c_a20_m40 = cm[0][1] if len(cm) >= 2 else 0
    print(f"\nهمبستگی A20-M40: {c_a20_m40:.2f}")
    if abs(c_a20_m40) > 0.5:
        print("⚠️ همبستگی بالا: ترکیب عملاً ۲ فاکتوری است.")
    
    # ذخیره
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/parity_result.json", "w") as f:
        json.dump({
            "verdict": verdict,
            "a20_precap": pre_cap.get("A20", 0),
            "m40_precap": pre_cap.get("M40", 0),
            "a20_m40_correlation": c_a20_m40,
            "diff_a20_pct": diff_a20,
            "diff_m40_pct": diff_m40
        }, f, indent=2)

if __name__ == "__main__":
    run_parity_test()
