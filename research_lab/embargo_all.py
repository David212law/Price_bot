import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_a20, strategy_m40, strategy_m35, strategy_a8, load_data, calculate_metrics

EXCHANGES = {
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"]
}
STRATS = {"A20": strategy_a20, "M35": strategy_m35, "A8": strategy_a8, "M40": strategy_m40}

def run_wf(exchange, symbols, strat_func, embargo=20, n_windows=5):
    train_trades, test_trades = [], []
    for sym in symbols:
        candles = load_data(exchange, sym)
        if not candles: continue
        ws = len(candles) // n_windows
        for i in range(n_windows):
            s = i * ws
            tr_end = s + int(ws * 0.7) - embargo
            te_start = s + int(ws * 0.7) + embargo
            tr_data = candles[s:tr_end]
            te_data = candles[te_start:s+ws]
            if len(tr_data) > 200: train_trades.extend(strat_func(tr_data))
            if len(te_data) > 20: test_trades.extend(strat_func(te_data))
    return calculate_metrics(train_trades), calculate_metrics(test_trades)

print("=== Embargo-WF: Aster & Hyperliquid ===\n")
for ex, syms in EXCHANGES.items():
    print(f"═══ {ex.upper()} ═══")
    for name, func in STRATS.items():
        tr, te = run_wf(ex, syms, func)
        tr_pf = tr.get("pf", 0) if tr.get("status")=="OK" else 0
        te_pf = te.get("pf", 0) if te.get("status")=="OK" else 0
        tr_n = tr.get("n", 0); te_n = te.get("n", 0)
        ratio = (te_pf/tr_pf) if tr_pf > 0 else 0
        status = "✅ لبه واقعی" if (tr_pf > 1.2 and te_pf > 1.0 and ratio > 0.7) else "❌ کاذب" if (te_pf < 0.8) else "⚠️ مرزی"
        print(f"  {name:5} | Train: PF={tr_pf:5.2f} (n={tr_n:3}) | Test: PF={te_pf:5.2f} (n={te_n:3}) | Ratio={ratio:4.2f} | {status}")
    print()
