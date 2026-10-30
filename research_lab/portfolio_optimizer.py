import sys
print("⚠️ WARNING: FOR SIMULATION ONLY. DO NOT USE IN LIVE (D-174).")
import json
import os
import numpy as np
from collections import defaultdict
from strategies.core_engine import strategy_m35, strategy_a8, strategy_a20, strategy_m40, load_data
from research_lab.bale_notifier import send_bale

def calculate_real_correlation():
    print("=== 🧠 Portfolio Architect: Real Correlation Matrix ===")
    exchange = "kucoin"
    symbols = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
    
    strategies = {
        "M35": strategy_m35, 
        "A8": strategy_a8, 
        "A20": strategy_a20, 
        "M40": strategy_m40
    }
    
    # دیکشنری برای ذخیره بازدهی روزانه هر استراتژی
    daily_returns = {name: defaultdict(float) for name in strategies}
    
    for name, func in strategies.items():
        for sym in symbols:
            candles = load_data(exchange, sym)
            if not candles: continue
            trades = func(candles)
            for t in trades:
                # تبدیل timestamp (میلی‌ثانیه) به روز (تقسیم بر 86,400,000)
                day = t["t"] // (24 * 60 * 60 * 1000)
                # فرض تخصیص مساوی: هر معامله ۱٪ ریسک دارد
                daily_returns[name][day] += t["ret"] * 0.01 
                
    # پیدا کردن تمام روزهای مشترک
    all_days = set()
    for name in strategies:
        all_days.update(daily_returns[name].keys())
    sorted_days = sorted(list(all_days))
    
    if not sorted_days:
        print("❌ No trades found.")
        return
        
    # ساخت آرایه‌های بازدهی
    returns_arrays = {}
    for name in strategies:
        arr = np.array([daily_returns[name].get(day, 0.0) for day in sorted_days])
        returns_arrays[name] = arr
        
    # محاسبه ماتریس همبستگی
    strat_names = list(strategies.keys())
    matrix_data = np.array([returns_arrays[name] for name in strat_names])
    corr_matrix = np.corrcoef(matrix_data)
    
    print("\n📊 Real Correlation Matrix (Based on KuCoin Data):")
    print(f"{'':15}", end="")
    for s in strat_names:
        print(f"{s:>10}", end="")
    print()
    
    for i, s1 in enumerate(strat_names):
        print(f"{s1:15}", end="")
        for j in range(len(strat_names)):
            print(f"{corr_matrix[i][j]:>10.2f}", end="")
        print()
        
    # شناسایی مکمل‌ها
    print("\n🔍 Complementary Analysis:")
    for i in range(len(strat_names)):
        for j in range(i+1, len(strat_names)):
            corr = corr_matrix[i][j]
            if corr < 0.3:
                print(f"  ✅ {strat_names[i]} & {strat_names[j]}: Corr={corr:.2f} (Complementary)")
            elif corr > 0.7:
                print(f"  ⚠️ {strat_names[i]} & {strat_names[j]}: Corr={corr:.2f} (Highly Correlated)")

    send_bale("🧠 Portfolio Architect: Real correlation matrix calculated.")
    
    # ذخیره گزارش
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/real_correlation_matrix.json", "w") as f:
        json.dump({"strategies": strat_names, "matrix": corr_matrix.tolist()}, f, indent=2)

if __name__ == "__main__":
    calculate_real_correlation()
