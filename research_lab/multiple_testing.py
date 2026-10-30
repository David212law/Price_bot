import sys, os
sys.path.append(os.getcwd())
import json, math
from strategies.core_engine import calculate_metrics

LEDGER_PATH = "research_lab/logs/trial_ledger.json"

def holm_bonferroni(p_values, alpha=0.05):
    """اصلاح Holm-Bonferroni برای کنترل خطای خانواده (Family-Wise Error Rate)"""
    n = len(p_values)
    sorted_indices = sorted(range(n), key=lambda i: p_values[i])
    passed = [False] * n
    for k, idx in enumerate(sorted_indices):
        threshold = alpha / (n - k)
        if p_values[idx] <= threshold:
            passed[idx] = True
        else:
            break # بقیه هم رد می‌شوند
    return passed

def main():
    print("=== 📊 Multiple Testing & Min Portfolio Rule ===\n")
    
    if not os.path.exists(LEDGER_PATH):
        print("❌ Trial ledger not found.")
        return

    with open(LEDGER_PATH) as f:
        ledger = json.load(f)
        
    # فیلتر کردن تست‌های موفق و محاسبه P-Value تقریبی بر اساس PF و n
    # (فرض: P-Value = 1 / (1 + (PF-1) * sqrt(n)))
    candidates = []
    for e in ledger:
        m = e.get("metrics", {})
        pf = m.get("pf", 0)
        n = m.get("n", 0)
        if n >= 30 and pf > 1.0:
            p_val = 1.0 / (1.0 + (pf - 1.0) * math.sqrt(n))
            candidates.append({
                "strategy": e["strategy"],
                "exchange": e["exchange"],
                "pf": pf, "n": n, "p_value": p_val
            })

    # حذف تکراری‌ها (بهترین PF برای هر استراتژی در هر صرافی)
    best_candidates = {}
    for c in candidates:
        key = (c["exchange"], c["strategy"])
        if key not in best_candidates or c["pf"] > best_candidates[key]["pf"]:
            best_candidates[key] = c
            
    cand_list = list(best_candidates.values())
    if not cand_list:
        print("❌ No candidates found in ledger.")
        return

    print(f"تعداد کل کاندیداها (قبل از تصحیح): {len(cand_list)}")
    
    # اعمال Holm-Bonferroni
    p_vals = [c["p_value"] for c in cand_list]
    passed_flags = holm_bonferroni(p_vals)
    
    print("\n--- نتایج پس از تصحیح Multiple Testing ---")
    for i, c in enumerate(cand_list):
        status = "✅ تایید" if passed_flags[i] else "❌ رد (احتمال شانس)"
        print(f"  {c['exchange']:12} | {c['strategy']:20} | PF={c['pf']:.2f}, n={c['n']:3} | P-Value={c['p_value']:.4f} | {status}")
        
    # Minimum Portfolio Rule (D-265)
    print("\n--- بررسی Minimum Portfolio Rule (حداقل ۲ استراتژی غیرهمبسته) ---")
    for ex in set(c["exchange"] for c in cand_list):
        survivors = [c["strategy"] for i, c in enumerate(cand_list) if c["exchange"] == ex and passed_flags[i]]
        if len(survivors) >= 2:
            print(f"  {ex:12}: ✅ {len(survivors)} استراتژی تایید شد ({', '.join(survivors)})")
        else:
            print(f"  {ex:12}: ⚠️ کمتر از ۲ استراتژی تایید شد ({', '.join(survivors) if survivors else 'هیچ'}) - NO_WINNER")

if __name__ == "__main__":
    main()
