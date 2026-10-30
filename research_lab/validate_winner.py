import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_m35, load_data, calculate_metrics

def validate_m35_20_200():
    print("=== 🏆 Validating Winner: M35_EMA(20,200) (Transparent OOS) ===")
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    oos_trades = []
    total_oos_days = 0
    
    for sym in symbols:
        candles = load_data("kucoin", sym)
        if not candles: continue
        
        train_idx = int(len(candles) * 0.6)
        val_idx = int(len(candles) * 0.8)
        
        test_data = candles[val_idx:]
        total_oos_days += (len(test_data) * 4) / 24 # تبدیل کندل 4h به روز
        
        oos_trades.extend(strategy_m35(test_data, fast=20, slow=200))
        
    oos_metrics = calculate_metrics(oos_trades)
    
    n_oss = oos_metrics.get('n', 0)
    win_rate = oos_metrics.get('win_rate', 0)
    
    print(f"📉 OOS Result: PF={oos_metrics.get('pf')} | n_oss={n_oss} | WR={win_rate}% | Test Days={total_oos_days:.1f}")
    
    if n_oss < 15:
        print("⚠️ WARNING: n_oss < 15. Result is INCONCLUSIVE, not Rejected (D-179).")
    elif oos_metrics.get('pf', 0) < 1.0:
        print("❌ REJECTED: Genuine OOS Failure (D-181).")

if __name__ == "__main__":
    validate_m35_20_200()
