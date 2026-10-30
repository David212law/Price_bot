import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_a20, load_data, calculate_metrics

def run_wf_with_embargo(exchange, symbols, embargo_candles, n_windows=5):
    all_train_trades = []
    all_test_trades = []
    
    for sym in symbols:
        candles = load_data(exchange, sym)
        if not candles: continue
        
        total = len(candles)
        window_size = total // n_windows
        
        for i in range(n_windows):
            start = i * window_size
            end = start + window_size
            
            # 70% برای Train، 30% برای Test، با Embargo در وسط
            train_end = start + int(window_size * 0.7) - embargo_candles
            test_start = start + int(window_size * 0.7) + embargo_candles
            
            train_data = candles[start:train_end]
            test_data = candles[test_start:end]
            
            # نیاز به حداقل ۲۰۰ کندل برای warmup EMA200
            if len(train_data) > 200:
                all_train_trades.extend(strategy_a20(train_data))
            if len(test_data) > 20:
                all_test_trades.extend(strategy_a20(test_data))
                
    train_m = calculate_metrics(all_train_trades)
    test_m = calculate_metrics(all_test_trades)
    return train_m, test_m

def main():
    exchange = "kucoin"
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    print("=== 📊 Embargo Walk-Forward Test (A20 on KuCoin) ===")
    print("مقایسه ۳ حالت: Embargo=0 (نشت‌دار) vs 20 vs 50 کندل\n")
    
    for emb in [0, 20, 50]:
        print(f"--- Embargo = {emb} کندل ---")
        train_m, test_m = run_wf_with_embargo(exchange, symbols, emb)
        
        tr_pf = train_m.get("pf", 0) if train_m.get("status") == "OK" else 0
        tr_n = train_m.get("n", 0)
        te_pf = test_m.get("pf", 0) if test_m.get("status") == "OK" else 0
        te_n = test_m.get("n", 0)
        
        # محاسبه نسبت OOS/IS (پایداری)
        ratio = (te_pf / tr_pf) if tr_pf > 0 else 0
        
        print(f"  Train: n={tr_n:3} | PF={tr_pf:5.2f}")
        print(f"  Test:  n={te_n:3} | PF={te_pf:5.2f}")
        print(f"  نسبت Test/Train: {ratio:.2f} (نزدیک به ۱ = پایداری خوب)")
        print()

if __name__ == "__main__":
    main()
