"""Validation Engine — SPA + DSR on screening survivors (on held-out 30%)."""
import sys, os, json, math, random
sys.path.append(os.getcwd())
from strategies.library.registry import get_strategy
from strategies.core_engine import load_data, calculate_metrics
from research_lab.audit_core import load_funding, deflated_sharpe

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

TEST_SPLIT = 0.7  # start of test = 70% (train was 0-70%)
MIN_N = 15
MIN_PF = 1.2
N_BOOTSTRAP = 500

def _test_returns_candle(name, params, exchange, symbol):
    """Get trade returns from test split."""
    func, _, _ = get_strategy(name)
    candles = load_data(exchange, symbol)
    if not candles: return []
    test_candles = candles[int(len(candles)*TEST_SPLIT):]
    try:
        trades = func(test_candles, **params)
    except Exception:
        return []
    return [t["ret"] for t in trades]

def _test_returns_funding(name, params, exchange, symbol):
    """Get daily returns from test split."""
    func, _, _ = get_strategy(name)
    records = load_funding(exchange, symbol)
    if not records: return []
    test_records = records[int(len(records)*TEST_SPLIT):]
    try:
        daily = func(test_records, **params)
    except Exception:
        return []
    return list(daily.values())

def spa_test(candidate_returns, n_bootstrap=N_BOOTSTRAP):
    """SPA vs zero (cash). Proper: center at H0=0, then bootstrap."""
    if not candidate_returns or len(candidate_returns) < 10:
        return 1.0
    n = len(candidate_returns)
    mean = sum(candidate_returns) / n
    if mean <= 0: return 1.0
    
    t_obs = mean
    
    # Center at zero (impose H0: E[ret]=0)
    centered = [r - mean for r in candidate_returns]
    
    rng = random.Random(42)
    t_boots = []
    block_size = min(10, max(2, n // 5))
    for _ in range(n_bootstrap):
        indices = []
        while len(indices) < n:
            start = rng.randint(0, n - block_size)
            indices.extend(range(start, start + block_size))
        indices = indices[:n]
        boot_mean = sum(centered[i] for i in indices) / n
        t_boots.append(boot_mean)
    
    p = sum(1 for t in t_boots if t >= t_obs) / n_bootstrap
    return p

def validate_candidate(cand, exchange, symbols):
    """Validate one candidate on test split."""
    name = cand["strategy"]
    kind = cand["kind"]
    params = cand["params"]
    
    all_returns = []
    n_trades = 0
    for sym in symbols:
        if kind == "candle":
            rets = _test_returns_candle(name, params, exchange, sym)
        else:
            rets = _test_returns_funding(name, params, exchange, sym)
        all_returns.extend(rets)
        n_trades += len(rets)
    
    if n_trades < MIN_N:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"n={n_trades}<{MIN_N}"}
    
    mean = sum(all_returns) / len(all_returns)
    if mean <= 0:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": "mean<=0"}
    
    wins = [r for r in all_returns if r > 0]
    losses = [r for r in all_returns if r < 0]
    pf = sum(wins) / abs(sum(losses)) if losses else 99.99
    if pf < MIN_PF:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"PF={pf:.2f}<{MIN_PF}"}
    
    # SPA
    p = spa_test(all_returns)
    if p > 0.05:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"SPA p={p:.3f}", "pf": round(pf,2), "n": n_trades}
    
    # DSR
    std = math.sqrt(sum((r-mean)**2 for r in all_returns) / max(len(all_returns)-1, 1))
    if std > 0:
        sharpe = mean / std  # per-period (NOT annualized) — D-398 fix
        d = deflated_sharpe(sharpe, len(all_returns), 54, annualized=False)
        dsr = d["DSR"] if d else 0
    else:
        dsr = 1.0
    
    if dsr < 0.90:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"DSR={dsr:.3f}<0.90", "pf": round(pf,2), "n": n_trades, "spa_p": round(p,4)}
    
    return {
        "strategy": name, "params": params, "verdict": "PASS",
        "pf": round(pf,2), "n": n_trades, "spa_p": round(p,4), "dsr": round(dsr,4),
        "mean_pct": round(mean*100, 4),
    }

def main():
    screening_file = "research_lab/logs/screening_results.json"
    if not os.path.exists(screening_file):
        print("❌ No screening results. Run screening.py first."); return
    
    with open(screening_file) as f:
        screening = json.load(f)
    
    print("═" * 60)
    print("  VALIDATION — SPA + DSR on test split")
    print("═" * 60 + "\n")
    
    all_survivors = {}
    for exchange, candidates in screening.items():
        symbols = EXCHANGES[exchange]
        print(f"═══ {exchange.upper()} ({len(candidates)} candidates) ═══")
        survivors = []
        for cand in candidates:
            result = validate_candidate(cand, exchange, symbols)
            if result["verdict"] == "PASS":
                survivors.append(result)
                print(f"  ✅ {result['strategy']:20s} PF={result['pf']:5.2f} n={result['n']:3} SPA_p={result['spa_p']:.3f} DSR={result['dsr']:.3f}")
            else:
                print(f"  ❌ {result['strategy']:20s} {result['reason']}")
        all_survivors[exchange] = survivors
        print(f"  → {len(survivors)} survivors\n")
    
    with open("research_lab/logs/validation_results.json", "w") as f:
        json.dump(all_survivors, f, indent=2, default=str)
    print(f"📄 validation_results.json saved")
    total = sum(len(v) for v in all_survivors.values())
    print(f"Total survivors: {total}")

if __name__ == "__main__":
    main()
