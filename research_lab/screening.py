"""Screening Engine — fast filter of 38 strategies × params on train split."""
import sys, os, json, math
sys.path.append(os.getcwd())
from datetime import datetime, timezone
from strategies.library.registry import expand_param_grid, get_strategy, list_strategies
from strategies.core_engine import load_data, calculate_metrics
from research_lab.audit_core import load_funding

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

MIN_N_PER_SYMBOL = 5   # per-symbol floor (was 30, too strict)
MIN_N_TOTAL = 30       # aggregate floor
MIN_PF = 1.15
TRAIN_SPLIT = 0.7
TRAIN_SPLIT = 0.7

def _metrics_from_funding_returns(daily_dict):
    """Convert funding daily returns dict to (n, pf, wr) tuple."""
    rets = list(daily_dict.values())
    if len(rets) < 5: return None
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    if not losses:
        pf = 99.99 if wins else 0
    else:
        pf = sum(wins) / abs(sum(losses)) if losses else 99.99
    # n = number of daily periods (more meaningful than trades for funding)
    n = len(rets)
    wr = len(wins) / len(rets) * 100 if rets else 0
    return {"n": n, "pf": round(pf, 2), "wr": round(wr, 1), "mean_pct": round(sum(rets)/len(rets)*100, 4)}

def _run_candle_strategy(name, params, exchange, symbol):
    """Run candle-based strategy, return trade list metrics."""
    func, grid, kind = get_strategy(name)
    candles = load_data(exchange, symbol)
    if not candles or len(candles) < 200: return None
    # Train split only
    train_end = int(len(candles) * TRAIN_SPLIT)
    train_candles = candles[:train_end]
    try:
        trades = func(train_candles, **params)
    except Exception:
        return None
    if not trades or len(trades) < MIN_N_PER_SYMBOL: return None
    m = calculate_metrics(trades)
    if m.get("status") != "OK": return None
    return {"n": m["n"], "pf": m["pf"], "wr": m["win_rate"], "max_dd": m.get("max_dd", 0)}

def _run_funding_strategy(name, params, exchange, symbol):
    """Run funding-based strategy, return metrics."""
    func, grid, kind = get_strategy(name)
    records = load_funding(exchange, symbol)
    if not records or len(records) < 100: return None
    # Train split
    train_end = int(len(records) * TRAIN_SPLIT)
    train_records = records[:train_end]
    try:
        daily = func(train_records, **params)
    except Exception:
        return None
    if not daily: return None
    return _metrics_from_funding_returns(daily)

def screening_run(exchange, symbols):
    """Run all strategies × params on one exchange. Return top candidates."""
    print(f"═══ Screening {exchange.upper()} ═══")
    results = []
    strategies = list_strategies()
    total_combos = 0
    
    for name, kind in strategies:
        func, grid, _ = get_strategy(name)
        param_combos = expand_param_grid(grid)
        for params in param_combos:
            total_combos += 1
            # Pool metrics across all symbols
            all_metrics = []
            for sym in symbols:
                if kind == "candle":
                    m = _run_candle_strategy(name, params, exchange, sym)
                else:
                    m = _run_funding_strategy(name, params, exchange, sym)
                if m: all_metrics.append(m)
            
            if not all_metrics: continue
            # Aggregate
            total_n = sum(m["n"] for m in all_metrics)
            if total_n < MIN_N_TOTAL: continue
            avg_pf = sum(m["pf"] for m in all_metrics) / len(all_metrics)
            if avg_pf < MIN_PF: continue
            
            results.append({
                "strategy": name,
                "kind": kind,
                "params": params,
                "n": total_n,
                "pf": round(avg_pf, 2),
                "wr": round(sum(m["wr"] for m in all_metrics) / len(all_metrics), 1),
                "symbols": len(all_metrics),
            })
    
    # Sort each family separately
    funding_results = [r for r in results if r["kind"] == "funding"]
    candle_results = [r for r in results if r["kind"] == "candle"]
    funding_results.sort(key=lambda x: (-x["pf"], -x["n"]))
    candle_results.sort(key=lambda x: (-x["pf"], -x["n"]))
    # Diversity: top 5 funding + top 15 candle (allows new edges to enter validation)
    top = funding_results[:5] + candle_results[:15]
    print(f"  {total_combos} combos tested → {len(results)} passed filter → top {len(top)} kept")
    for r in top[:5]:
        print(f"    {r['strategy']:20s} PF={r['pf']:5.2f} n={r['n']:4} params={r['params']}")
    if len(top) > 5: print(f"    ... +{len(top)-5} more")
    return top

def main():
    all_results = {}
    for exchange, symbols in EXCHANGES.items():
        all_results[exchange] = screening_run(exchange, symbols)
        print()
    
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/screening_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"📄 screening_results.json saved")
    total = sum(len(v) for v in all_results.values())
    print(f"Total candidates: {total}")

if __name__ == "__main__":
    main()
