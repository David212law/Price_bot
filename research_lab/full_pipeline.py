import sys, os, random, math
sys.path.append(os.getcwd())
from strategies.core_engine import (strategy_m35, strategy_a20, strategy_m40,
                                     strategy_a8, strategy_m50_regime_bh,
                                     strategy_m51_extreme_rev, strategy_m52_xsect_momentum,
                                     strategy_m53_vol_breakout, load_data, calculate_metrics)

VARIANTS = {
    "M35_20_100": ("M35", lambda c: strategy_m35(c, fast=20, slow=100)),
    "M35_20_200": ("M35", lambda c: strategy_m35(c, fast=20, slow=200)),
    "M35_50_100": ("M35", lambda c: strategy_m35(c, fast=50, slow=100)),
    "M35_50_200": ("M35", lambda c: strategy_m35(c, fast=50, slow=200)),
    "A20":        ("A20", strategy_a20),
    "M40":        ("M40", strategy_m40),
    "A8":         ("A8",  strategy_a8),
    "M50_RegimeBH": ("M50", strategy_m50_regime_bh),
    "M51_ExtremeRev": ("M51", strategy_m51_extreme_rev),
    "M52_XsectMom": ("M52", strategy_m52_xsect_momentum),
    "M53_VolBreakout": ("M53", strategy_m53_vol_breakout),
}
EXCHANGES = {
    "kucoin":     ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
    "aster":      ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid":["BTC","ETH","SOL","BNB","XRP","AVAX"],
}

def embargo_wf(candles, n_windows=5, embargo=20, train_ratio=0.7):
    ws = len(candles) // n_windows
    for i in range(n_windows):
        s = i * ws
        tr_end = s + int(ws * train_ratio) - embargo
        te_start = s + int(ws * train_ratio) + embargo
        yield candles[s:tr_end], candles[te_start:s+ws]

def boot_p(rets, block_size=6, iterations=500, seed=42):
    n = len(rets)
    if n < 20: return 1.0
    actual = 1.0
    for r in rets: actual *= (1 + r * 0.01)
    rng = random.Random(seed)
    better = 0
    for _ in range(iterations):
        sim = 1.0
        sm = 0
        while sm < n:
            st = rng.randint(0, n - 1)
            for i in range(block_size):
                if sm >= n: break
                sim *= (1 + rets[(st+i) % n] * 0.01)
                sm += 1
        if sim >= actual: better += 1
    return better / iterations

def holm(p_vals, alpha=0.05):
    n = len(p_vals)
    order = sorted(range(n), key=lambda i: p_vals[i])
    passed = [False] * n
    for k, idx in enumerate(order):
        if p_vals[idx] <= alpha / (n - k):
            passed[idx] = True
        else:
            break
    return passed

def corr(x, y):
    n = min(len(x), len(y))
    if n < 3: return 0
    x, y = x[-n:], y[-n:]
    mx, my = sum(x)/n, sum(y)/n
    c = sum((a-mx)*(b-my) for a,b in zip(x,y))
    sx = math.sqrt(sum((a-mx)**2 for a in x))
    sy = math.sqrt(sum((b-my)**2 for b in y))
    return c/(sx*sy) if sx*sy > 0 else 0

def run_exchange(ex, syms):
    print(f"\n{'='*60}\n  {ex.upper()}\n{'='*60}")
    results = []
    for name, (_, func) in VARIANTS.items():
        trades = []
        for sym in syms:
            cd = load_data(ex, sym)
            if not cd: continue
            for _, test in embargo_wf(cd):
                if len(test) > 20:
                    try: trades.extend(func(test))
                    except: pass
        if len(trades) < 15: continue
        m = calculate_metrics(trades)
        rets = [t["ret"] for t in trades]
        results.append({
            "name": name, "pf": m.get("pf", 0), "n": m.get("n", 0),
            "p": boot_p(rets), "rets": rets
        })
        print(f"  {name:12}: PF={m.get('pf',0):5.2f}, n={m.get('n',0):3}, P={results[-1]['p']:.3f}")
    
    if len(results) < 2:
        print("  ❌ Not enough variants.")
        return None
    
    passed = holm([r["p"] for r in results])
    print(f"\n  Holm-Bonferroni:")
    survivors = []
    for i, r in enumerate(results):
        st = "✅" if passed[i] else "❌"
        print(f"    {st} {r['name']:12} P={r['p']:.3f}")
        if passed[i]: survivors.append(r)
    
    # Fallback: if < 2, take PF>1.0 and P<0.5
    if len(survivors) < 2:
        print(f"\n  ⚠️ Fallback (PF>1.0 & P<0.5):")
        survivors = [r for r in results if r["pf"] > 1.0 and r["p"] < 0.5]
        for r in survivors:
            print(f"    ⚠️ {r['name']:12} PF={r['pf']:.2f} P={r['p']:.3f}")
    
    if len(survivors) < 2:
        print(f"\n  ❌ NO_WINNER ({len(survivors)} survivors)")
        return {"status": "NO_WINNER", "survivors": [s["name"] for s in survivors]}
    
    # HRP: inverse variance
    weights = {}
    for r in survivors:
        rets = r["rets"]; n = len(rets)
        mean = sum(rets)/n
        var = sum((x-mean)**2 for x in rets)/n
        weights[r["name"]] = 1.0 / (var + 1e-8)
    total = sum(weights.values())
    weights = {k: v/total for k, v in weights.items()}
    
    # Cap at 50%, floor 10%
    for _ in range(30):
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        if all(0.10 <= w <= 0.50 for w in weights.values()):
            break
        over = [k for k,v in weights.items() if v > 0.50]
        under = [k for k,v in weights.items() if v < 0.10]
        for k in over: weights[k] = 0.50
        for k in under: weights[k] = 0.10
        # renormalize
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
    
    # Final round to sum=100
    total = sum(weights.values())
    weights = {k: round(v/total, 4) for k, v in weights.items()}
    
    print(f"\n  🏆 Combination:")
    for k, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"    {k:12}: {w*100:5.1f}%")
    
    # Correlation
    print(f"\n  Correlation:")
    names = list(weights.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            c = corr(survivors[i]["rets"], survivors[j]["rets"])
            print(f"    {names[i]} ↔ {names[j]}: {c:.2f}")
    
    return {"status": "OK", "weights": weights}

def main():
    print("="*60 + "\n  🤖 FULL RESEARCH PIPELINE\n" + "="*60)
    final = {}
    for ex, syms in EXCHANGES.items():
        final[ex] = run_exchange(ex, syms)
    
    print("\n" + "="*60 + "\n  📊 FINAL SUMMARY\n" + "="*60)
    for ex, res in final.items():
        if res is None or res.get("status") == "NO_WINNER":
            print(f"  {ex:12}: ⚠️ NO_WINNER")
        else:
            print(f"  {ex:12}: ✅")
            for k, w in sorted(res["weights"].items(), key=lambda x: -x[1]):
                print(f"    → {k:12}: {w*100:.1f}%")

if __name__ == "__main__":
    main()
