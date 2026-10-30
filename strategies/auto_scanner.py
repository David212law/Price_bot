import os, json
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, load_data, calculate_metrics

def scan_exchange(exchange):
    print(f"=== Auto-Scanning {exchange.upper()} ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"] if exchange == "kucoin" else ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"]
    strategies = {"M35": strategy_m35, "A8": strategy_a8, "A20": strategy_a20}
    
    results = {}
    for name, func in strategies.items():
        all_trades = []
        for sym in symbols:
            candles = load_data(exchange, sym)
            if candles: all_trades.extend(func(candles))
        
        metrics = calculate_metrics(all_trades)
        results[name] = metrics
        
        # چاپ خلاصه
        if metrics["status"] == "OK":
            print(f"  [{name}] n={metrics['n']} | PF={metrics['pf']} | MaxDD={metrics['max_dd']}% | WR={metrics['win_rate']}% | Ret={metrics['return']}%")
        else:
            print(f"  [{name}] No trades generated.")
            
    # ذخیره در فایل گزارش
    os.makedirs("reports/auto_scan", exist_ok=True)
    with open(f"reports/auto_scan/{exchange}_summary.json", "w") as f:
        json.dump(results, f, indent=2)
