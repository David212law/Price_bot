import sys, os, json, math, random
sys.path.append(os.getcwd())
from strategies.core_engine import (strategy_a20, strategy_m40, strategy_m35,
                                     strategy_a8, load_data, calculate_metrics)

EXCHANGES = {
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"]
}

def block_bootstrap_p_value(trades, block_size=6, iterations=1000):
    """محاسبه P-Value واقعی با Block Bootstrap (روش D-68-Plus)"""
    if not trades or len(trades) < block_size * 2:
        return 1.0
    
    rets = [t["ret"] for t in trades]
    n = len(rets)
    
    # Equity Curve واقعی
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1 + r * 0.01))  # 1% risk per trade
    actual_final = eq[-1]
    
    n_blocks = n // block_size
    better = 0
    random.seed(42)
    
    for _ in range(iterations):
        sim_eq = 1.0
        for _ in range(n_blocks):
            start = random.randint(0, n - block_size)
            for i in range(block_size):
                sim_eq *= (1 + rets[start + i] * 0.01)
        if sim_eq >= actual_final:
            better += 1
    
    return better / iterations

def holm_bonferroni(p_values, alpha=0.05):
    n = len(p_values)
    sorted_idx = sorted(range(n), key=lambda i: p_values[i])
    passed = [False] * n
    thresholds = [0.0] * n
    for k, idx in enumerate(sorted_idx):
        threshold = alpha / (n - k)
        thresholds[idx] = threshold
        if p_values[idx] <= threshold:
            passed[idx] = True
        else:
            break
    return passed, thresholds

def main():
    print("=== 🎯 Real Block Bootstrap P-Value (D-289) ===\n")
    
    STRATS = {"A20": strategy_a20, "M40": strategy_m40,
              "M35": strategy_m35, "A8": strategy_a8}
    
    candidates = []
    
    for ex, syms in EXCHANGES.items():
        print(f"═══ {ex.upper()} ═══")
        for name, func in STRATS.items():
            all_trades = []
            for sym in syms:
                candles = load_data(ex, sym)
                if candles:
                    try:
                        all_trades.extend(func(candles))
                    except Exception:
                        pass
            
            if len(all_trades) < 30:
                print(f"  {name:5}: n={len(all_trades):3} → too few trades")
                continue
            
            metrics = calculate_metrics(all_trades)
            pf = metrics.get("pf", 0)
            n = metrics.get("n", 0)
            
            # P-Value با Block Bootstrap واقعی
            p_val = block_bootstrap_p_value(all_trades, block_size=6, iterations=500)
            
            print(f"  {name:5}: PF={pf:5.2f}, n={n:3} → P-Value(bootstrap)={p_val:.4f}")
            
            if pf > 1.0:
                candidates.append({
                    "exchange": ex, "strategy": name,
                    "pf": pf, "n": n, "p_value": p_val
                })
        print()
    
    print("═══ Holm-Bonferroni Correction ═══\n")
    if not candidates:
        print("❌ No candidates.")
        return
    
    p_vals = [c["p_value"] for c in candidates]
    passed, thresholds = holm_bonferroni(p_vals)
    
    print(f"Total candidates: {len(candidates)}\n")
    for i, c in enumerate(candidates):
        status = "✅ PASS" if passed[i] else "❌ FAIL"
        print(f"  {c['exchange']:12} | {c['strategy']:5} | PF={c['pf']:.2f}, n={c['n']:3} | P={c['p_value']:.4f} (Holm α={thresholds[i]:.4f}) → {status}")
    
    print("\n═══ Minimum Portfolio Rule (D-265) ═══\n")
    by_exchange = {}
    for i, c in enumerate(candidates):
        if passed[i]:
            by_exchange.setdefault(c["exchange"], []).append(c["strategy"])
    
    for ex in sorted(set(c["exchange"] for c in candidates)):
        survivors = by_exchange.get(ex, [])
        if len(survivors) >= 2:
            print(f"  {ex:12}: ✅ {len(survivors)} passed: {survivors}")
        else:
            print(f"  {ex:12}: ⚠️ {len(survivors)} passed: {survivors if survivors else 'none'} → NO_WINNER")

if __name__ == "__main__":
    main()
