import sys, os
sys.path.append(os.getcwd())
import json, itertools
from strategies.core_engine import (strategy_m35, strategy_a8, strategy_a20, strategy_m40,
                                     load_data, calculate_metrics, log_trial)
from research_lab.budget_manager import check_budget, log_test, load_ledger
from research_lab.bale_notifier import send_bale

EXCHANGES = ["kucoin", "aster", "hyperliquid"]
EXCHANGE_SYMBOLS = {
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"]
}

def run_auto_discovery():
    print("=== 🤖 Universal Auto-Discovery Engine ===")
    
    # لیست تست‌های قابل انجام (استراتژی + پارامتر)
    tests = [
        ("M35_EMA(20,100)", strategy_m35, {"fast":20, "slow":100}),
        ("M35_EMA(20,200)", strategy_m35, {"fast":20, "slow":200}),
        ("M35_EMA(50,100)", strategy_m35, {"fast":50, "slow":100}),
        ("M35_EMA(50,200)", strategy_m35, {"fast":50, "slow":200}),
        ("A8_Grid", strategy_a8, {}),
        ("A20_SuperTrend", strategy_a20, {}),
        ("M40_Pullback", strategy_m40, {}),
    ]
    
    existing_ledger = load_ledger()
    existing_tests = {(e["strategy"], e.get("exchange","")) for e in existing_ledger}
    
    for exchange in EXCHANGES:
        symbols = EXCHANGE_SYMBOLS[exchange]
        print(f"\n--- {exchange.upper()} ---")
        for test_name, func, params in tests:
            key = (test_name, exchange)
            if key in existing_tests:
                print(f"  ⏭️ {test_name}: already tested")
                continue
            if not check_budget(): 
                print("  🛑 Budget limit reached.")
                return
            
            print(f"  Testing {test_name} on {exchange}...")
            all_trades = []
            for sym in symbols:
                cd = load_data(exchange, sym)
                if not cd: continue
                split_idx = int(len(cd) * 0.6)
                try:
                    trades = func(cd[:split_idx], **params) if params else func(cd[:split_idx])
                    all_trades.extend(trades)
                except Exception as e:
                    print(f"    ⚠️ {sym}: {e}")
                    continue
            
            metrics = calculate_metrics(all_trades)
            log_test(test_name, metrics, exchange=exchange)
            
            if metrics.get("pf",0) > 1.2 and metrics.get("n",0) >= 30:
                send_bale(f"🎯 Candidate: {test_name} on {exchange}\nPF={metrics['pf']} n={metrics['n']}")

if __name__ == "__main__":
    run_auto_discovery()
