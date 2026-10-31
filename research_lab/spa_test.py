"""
Hansen (2005) SPA — Test if best candidate beats benchmark (default: zero).
Reference: Hansen, P.R. (2005), "A Test for Superior Predictive Ability"
"""
import sys, os, math, random, json
sys.path.append(os.getcwd())
from research_lab.audit_core import load_funding
from datetime import datetime, timezone
from collections import defaultdict

SYMBOLS = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

N_BOOTSTRAP = 1000

def portfolio_returns(exchange):
    """Daily portfolio returns (equal-weight across symbols)."""
    syms = SYMBOLS.get(exchange, [])
    all_days = defaultdict(list)
    for sym in syms:
        rates = load_funding(exchange, sym)
        sym_daily = defaultdict(float)
        for r in rates:
            day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            sym_daily[day] += r["rate"]
        for day, ret in sym_daily.items():
            all_days[day].append(ret)
    return [(d, sum(all_days[d])/len(all_days[d])) for d in sorted(all_days.keys())]

def spa_test(candidate_returns, benchmark_returns=None, n_bootstrap=N_BOOTSTRAP):
    """
    SPA test: H0 = max_k E[μ_k] <= μ_benchmark (default 0).
    HA = max_k E[μ_k] > μ_benchmark.
    """
    n = len(candidate_returns[0])
    if n < 30:
        return {"error": f"n={n} < 30", "n": n}
    
    # Benchmark mean (default: zero = cash)
    if benchmark_returns is None:
        bench_mean = 0.0
        bench_series = [0.0] * n
    else:
        bench_mean = sum(benchmark_returns[:n]) / n
        bench_series = benchmark_returns[:n]
    
    # Observed: max_k (mean_k - bench_mean)
    diffs = []
    for cand in candidate_returns:
        cand_mean = sum(cand[:n]) / n
        diffs.append(cand_mean - bench_mean)
    t_obs = max(0, max(diffs))
    
    if t_obs == 0:
        return {"T_spa": 0, "p_value": 1.0, "n": n, "n_candidates": len(candidate_returns),
                "verdict": "FAIL (no candidate beats benchmark)"}
    
    # Bootstrap under H0: center candidates at benchmark
    rng = random.Random(42)
    centered = [[c[i] - (sum(c[:n])/n - bench_mean) for i in range(n)] for c in candidate_returns]
    centered_bench = [bench_series[i] - (bench_mean - bench_mean) for i in range(n)]  # = bench_series
    
    t_boots = []
    block_size = 10
    for _ in range(n_bootstrap):
        indices = []
        while len(indices) < n:
            start = rng.randint(0, n - block_size)
            indices.extend(range(start, start + block_size))
        indices = indices[:n]
        
        boot_bench_mean = sum(centered_bench[i] for i in indices) / n
        boot_diffs = []
        for c in centered:
            boot_mean = sum(c[i] for i in indices) / n
            boot_diffs.append(boot_mean - boot_bench_mean)
        t_boot = max(0, max(boot_diffs))
        t_boots.append(t_boot)
    
    p_value = sum(1 for t in t_boots if t >= t_obs) / n_bootstrap
    
    if p_value < 0.01:
        verdict = f"STRONG PASS (p={p_value:.4f})"
    elif p_value < 0.05:
        verdict = f"PASS (p={p_value:.4f})"
    elif p_value < 0.10:
        verdict = f"WEAK (p={p_value:.4f})"
    else:
        verdict = f"FAIL (p={p_value:.4f})"
    
    return {
        "T_spa": round(t_obs, 8),
        "p_value": round(p_value, 4),
        "n": n,
        "n_candidates": len(candidate_returns),
        "verdict": verdict,
        "bench_mean_ann": round(bench_mean * 365, 4),
    }

def main():
    print("═" * 72)
    print("  SPA TEST (Hansen 2005) — Multiple Testing vs Cash Benchmark")
    print("═" * 72 + "\n")
    
    results = {}
    for exchange in SYMBOLS.keys():
        print(f"═══ {exchange.upper()} ═══")
        daily = portfolio_returns(exchange)
        rets = [r for _, r in daily]
        
        if len(rets) < 30:
            print(f"  ⚠️ Insufficient data (n={len(rets)})\n")
            continue
        
        # Test M31 alone vs cash (0)
        result_m31 = spa_test([rets], benchmark_returns=None)
        print(f"  M31 vs Cash (n={result_m31.get('n', 0)}):")
        print(f"    T_SPA = {result_m31.get('T_spa', 0):.8f}")
        print(f"    P-Value = {result_m31.get('p_value', 1.0)}")
        print(f"    Verdict: {result_m31.get('verdict', 'N/A')}\n")
        
        results[exchange] = {"M31_vs_cash": result_m31}
    
    with open("spa_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"📄 spa_results.json saved ({len(results)} exchanges)")
    print()
    print("Interpretation:")
    print("  PASS = M31 statistically beats zero (cash) after multiple testing")
    print("  FAIL = no evidence of edge above cash")

if __name__ == "__main__":
    main()
