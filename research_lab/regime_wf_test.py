import sys, os, json, random, math
sys.path.append(os.getcwd())
from strategies.core_engine import (strategy_a20, strategy_m40, strategy_m35,
                                     load_data, calculate_metrics, calc_atr)
from research_lab.regime_analysis import classify_regime, tag_trades_with_regime

def embargo_wf(candles, n_windows=5, embargo=20, train_ratio=0.7):
    ws = len(candles) // n_windows
    for i in range(n_windows):
        s = i * ws
        tr_end = s + int(ws * train_ratio) - embargo
        te_start = s + int(ws * train_ratio) + embargo
        yield candles[s:tr_end], candles[te_start:s+ws]

def boot_p(rets, block_size=6, iterations=500, seed=42):
    """P-Value: آیا میانگین بازده معنادارانه > 0 است؟"""
    n = len(rets)
    if n < 15: return 1.0
    mean = sum(rets) / n
    if mean <= 0: return 1.0
    std = math.sqrt(sum((r - mean)**2 for r in rets) / (n - 1))
    if std == 0: return 0.0
    rng = random.Random(seed)
    better = 0
    for _ in range(iterations):
        sample = [rng.gauss(0, std) for _ in range(n)]
        sample_mean = sum(sample) / n
        if sample_mean >= mean:
            better += 1
    return better / iterations

def test_strategy_regime_on_wf(name, func, exchange, symbols):
    """تست رژیم‌محور با Embargo-WF"""
    print(f"\n═══ {name} on {exchange.upper()} (Embargo-WF) ═══")
    
    regime_trades = {"TREND": [], "NEUTRAL": [], "RANGE": []}
    
    for sym in symbols:
        candles = load_data(exchange, sym)
        if not candles: continue
        for train, test in embargo_wf(candles):
            if len(test) < 20: continue
            trades = func(test)
            tagged = tag_trades_with_regime(trades, test)
            for t in tagged:
                if t["regime"] in regime_trades:
                    regime_trades[t["regime"]].append(t["ret"])
    
    print(f"  {'Regime':10} | {'n':>4} | {'Mean%':>7} | {'PF':>5} | {'P-Value':>8} | Status")
    print("  " + "-" * 60)
    
    survivors = {}
    for regime in ["TREND", "NEUTRAL", "RANGE"]:
        rets = regime_trades[regime]
        n = len(rets)
        if n < 15:
            print(f"  {regime:10} | {n:4} | n/a (insufficient)")
            continue
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]
        pf = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 99.99
        mean_ret = sum(rets) / n * 100
        p_val = boot_p(rets)
        
        # تصمیم
        if p_val < 0.05 and pf > 1.2 and mean_ret > 0:
            status = "✅ VALID"
            survivors[regime] = {"n": n, "pf": pf, "p": p_val}
        elif p_val < 0.15 and pf > 1.2 and mean_ret > 0:
            status = "⚠️ WEAK"
        else:
            status = "❌ FAIL"
        
        print(f"  {regime:10} | {n:4} | {mean_ret:+6.3f} | {pf:5.2f} | {p_val:8.4f} | {status}")
    
    return survivors

def main():
    print("=" * 65)
    print("  🎯 Regime-Aware Strategy Test with Embargo-WF")
    print("=" * 65)
    print("\nآستانه پیش‌ثبت‌شده: P<0.05، PF>1.2، n>=15")
    print("هر رژیم جداگانه با Embargo-WF تست می‌شود.\n")
    
    EXCHANGES = {
        "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
        "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
        "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
    }
    STRATEGIES = {
        "A20": strategy_a20,
        "M40": strategy_m40,
        "M35": lambda c: strategy_m35(c, fast=50, slow=200),
    }
    
    results = {}
    for ex, syms in EXCHANGES.items():
        results[ex] = {}
        for name, func in STRATEGIES.items():
            survivors = test_strategy_regime_on_wf(name, func, ex, syms)
            results[ex][name] = survivors
    
    print("\n" + "=" * 65)
    print("  📊 FINAL VERDICT — Regime-Aware Survivors")
    print("=" * 65)
    for ex, strats in results.items():
        print(f"\n{ex.upper()}:")
        for name, surv in strats.items():
            if surv:
                for regime, stats in surv.items():
                    print(f"  ✅ {name} in {regime}: n={stats['n']}, PF={stats['pf']:.2f}, P={stats['p']:.4f}")
            else:
                print(f"  ❌ {name}: no valid regime")
    
    # ذخیره نتایج
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/regime_wf_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\n✅ Results saved to regime_wf_results.json")

if __name__ == "__main__":
    main()
