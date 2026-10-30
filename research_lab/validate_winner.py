import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_m35, load_data, calculate_metrics

def validate_m35_20_200():
    print("=== 🏆 Validating Winner: M35_EMA(20,200) ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    # ۱. تست Out-of-Sample (۳۰٪ داده آخر)
    oos_trades = []
    for sym in symbols:
        candles = load_data("kucoin", sym)
        if not candles: continue
        split_idx = int(len(candles) * 0.7)
        test_data = candles[split_idx:] # داده‌ای که ربات در کشف ندیده بود
        oos_trades.extend(strategy_m35(test_data, fast=20, slow=200))
        
    oos_metrics = calculate_metrics(oos_trades)
    print(f"📉 OOS Result: PF={oos_metrics.get('pf')} | n={oos_metrics.get('n')} | MaxDD={oos_metrics.get('max_dd')}%")
    
    # ۲. تست Fee Stress (با کارمزد ۲۵٪ بالاتر)
    stress_trades = []
    for sym in symbols:
        candles = load_data("kucoin", sym)
        if not candles: continue
        stress_trades.extend(strategy_m35(candles, fast=20, slow=200, fee_multiplier=1.25))
        
    stress_metrics = calculate_metrics(stress_trades)
    print(f"💸 Fee Stress Result: PF={stress_metrics.get('pf')} | n={stress_metrics.get('n')}")

if __name__ == "__main__":
    validate_m35_20_200()
