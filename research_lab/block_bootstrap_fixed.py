import sys, os, random
sys.path.append(os.getcwd())
from strategies.core_engine import (strategy_a20, strategy_m40, strategy_m35,
                                     strategy_a8, load_data, calculate_metrics)

EXCHANGES = {
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"]
}

def circular_block_bootstrap_p(trades, block_size=6, iterations=1000, seed=42):
    """Circular Block Bootstrap - دقیقاً n نمونه"""
    if not trades or len(trades) < 30:
        return 1.0
    rets = [t["ret"] for t in trades]
    n = len(rets)
    actual_final = 1.0
    for r in rets:
        actual_final *= (1 + r * 0.01)
    rng = random.Random(seed)
    better = 0
    for _ in range(iterations):
        sim_final = 1.0
        samples = 0
        while samples < n:
            start = rng.randint(0, n - 1)
            for i in range(block_size):
                if samples >= n: break
                sim_final *= (1 + rets[(start + i) % n] * 0.01)
                samples += 1
        if sim_final >= actual_final:
            better += 1
    return better / iterations

def holm(p_vals, alpha=0.05):
    n = len(p_vals)
    sorted_idx = sorted(range(n), key=lambda i: p_vals[i])
    passed = [False] * n
    thresholds = [0.0] * n
    for k, idx in enumerate(sorted_idx):
        t = alpha / (n - k)
        thresholds[idx] = t
        if p_vals[idx] <= t:
            passed[idx] = True
        else:
            break
    return passed, thresholds

def main():
    print("=== 🎯 Circular Block Bootstrap (بدون سوگیری نمونه) ===\n")
    STRATS = {"A20": strategy_a20, "M40": strategy_m40}
    candidates = []
    for ex, syms in EXCHANGES.items():
        print(f"═══ {ex.upper()} ═══")
        for name, func in STRATS.items():
            trades = []
            for sym in syms:
                candles = load_data(ex, sym)
                if candles:
                    try: trades.extend(func(candles))
                    except: pass
            if len(trades) < 30:
                print(f"  {name:5}: n={len(trades):3} → too few")
                continue
            m = calculate_metrics(trades)
            pf = m.get("pf", 0); n = m.get("n", 0)
            p = circular_block_bootstrap_p(trades, block_size=6, iterations=1000)
            print(f"  {name:5}: PF={pf:5.2f}, n={n:3} → P={p:.4f}")
            if pf > 1.0:
                candidates.append({"exchange": ex, "strategy": name, "pf": pf, "n": n, "p": p})
        print()

    if not candidates:
        print("❌ No candidates.")
        return

    print("═══ Holm-Bonferroni ═══\n")
    p_vals = [c["p"] for c in candidates]
    passed, thresholds = holm(p_vals)
    for i, c in enumerate(candidates):
        status = "✅ PASS" if passed[i] else "❌ FAIL"
        print(f"  {c['exchange']:12} | {c['strategy']:5} | PF={c['pf']:.2f}, n={c['n']:3} | P={c['p']:.4f} (α={thresholds[i]:.4f}) → {status}")

if __name__ == "__main__":
    main()
