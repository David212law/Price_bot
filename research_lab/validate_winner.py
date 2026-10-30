import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_m35, load_data, calculate_metrics

def validate_m35_20_200():
    print("=== 🏆 Validating Winner: M35_EMA(20,200) (Strict OOS) ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    oos_trades = []
    stress_trades = []
    
    for sym in symbols:
        candles = load_data("kucoin", sym)
        if not candles: continue
        
        # تفکیک سه‌گانه: 60% Train, 20% Val, 20% Test (OOS)
        train_idx = int(len(candles) * 0.6)
        val_idx = int(len(candles) * 0.8)
        
        test_data = candles[val_idx:] # داده‌ای که هرگز دیده نشده است
        
        # ۱. تست Out-of-Sample واقعی (روی ۲۰٪ آخر)
        oos_trades.extend(strategy_m35(test_data, fast=20, slow=200))
        
        # ۲. تست Fee Stress روی کل داده (برای بررسی استحکام کلی)
        stress_trades.extend(strategy_m35(candles, fast=20, slow=200, fee_multiplier=1.25))
        
    oos_metrics = calculate_metrics(oos_trades)
    stress_metrics = calculate_metrics(stress_trades)
    
    print(f"📉 OOS (20% Test) Result: PF={oos_metrics.get('pf')} | n={oos_metrics.get('n')} | MaxDD={oos_metrics.get('max_dd')}%")
    print(f"💸 Fee Stress (Full) Result: PF={stress_metrics.get('pf')} | n={stress_metrics.get('n')}")

if __name__ == "__main__":
    validate_m35_20_200()
