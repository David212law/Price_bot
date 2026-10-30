import sys
print("⚠️ WARNING: FOR SIMULATION ONLY.")
import json, os, math
from collections import defaultdict

LEDGER_PATH = "research_lab/logs/trial_ledger.json"

def calc_corr(x, y):
    n = len(x)
    if n == 0: return 0
    mx, my = sum(x)/n, sum(y)/n
    c = sum((a-mx)*(b-my) for a, b in zip(x,y))
    sx = math.sqrt(sum((a-mx)**2 for a in x))
    sy = math.sqrt(sum((b-my)**2 for b in y))
    return c/(sx*sy) if sx*sy > 0 else 0

def per_exchange_hrp():
    print("=== 🧠 Per-Exchange HRP (D-229) ===\n")
    if not os.path.exists(LEDGER_PATH):
        print("❌ Trial ledger not found.")
        return
    
    with open(LEDGER_PATH) as f:
        ledger = json.load(f)
    
    # گروه‌بندی بر اساس صرافی
    by_exchange = defaultdict(list)
    for e in ledger:
        if e.get("metrics", {}).get("status") == "OK":
            by_exchange[e.get("exchange", "unknown")].append(e)
    
    for exchange, entries in by_exchange.items():
        print(f"\n═══ {exchange.upper()} ═══")
        
        # فیلتر کاندیداها (PF>1.2 و n>=30)
        candidates = {}
        for e in entries:
            m = e["metrics"]
            if m.get("pf", 0) > 1.2 and m.get("n", 0) >= 30:
                name = e["strategy"]
                if name not in candidates or m["pf"] > candidates[name]["pf"]:
                    candidates[name] = m
        
        if len(candidates) < 2:
            print(f"  ⚠️ Only {len(candidates)} candidate(s). Skipping HRP.")
            if candidates:
                for n, m in candidates.items():
                    print(f"  • {n}: PF={m['pf']}, n={m['n']} (100%)")
            continue
        
        # HRP (Inverse Variance as proxy)
        weights = {}
        for name, m in candidates.items():
            # واریانس معکوس بر مبنای MaxDD
            dd = max(m.get("max_dd", 1), 1)
            weights[name] = 1.0 / dd
        
        total = sum(weights.values())
        weights = {n: w/total for n, w in weights.items()}
        
        # اعمال سقف ۵۰٪ و کف ۵٪
        for _ in range(20):
            total = sum(weights.values())
            weights = {n: w/total for n, w in weights.items()}
            over = [n for n, w in weights.items() if w > 0.50]
            if not over: break
            for n in over: weights[n] = 0.50
            under = [n for n, w in weights.items() if w < 0.50 - 1e-9]
            deficit = sum(0.50 - weights[n] for n in over)
            under_sum = sum(weights[n] for n in under)
            if under_sum > 1e-9:
                for n in under: weights[n] += deficit * (weights[n] / under_sum)
        
        print(f"  🎯 HRP Combination:")
        for n, w in sorted(weights.items(), key=lambda x: -x[1]):
            print(f"     {n:20} {w*100:5.1f}%  (PF={candidates[n]['pf']}, n={candidates[n]['n']})")
        print(f"     Sum: {sum(weights.values())*100:.1f}%")

if __name__ == "__main__":
    per_exchange_hrp()
