import json
import os
from datetime import datetime, timezone

DATA_DIR = "exchanges/paradex/data"
SYMBOLS = ["BTC_USD_PERP", "ETH_USD_PERP", "SOL_USD_PERP", "BNB_USD_PERP", "AVAX_USD_PERP", "XRP_USD_PERP"]
INTERVAL_MS = 4 * 60 * 60 * 1000  # 4 ساعت
TOLERANCE_MS = 30 * 60 * 1000    # تحمل ۳۰ دقیقه اختلاف

def fill_gaps(symbol):
    filepath = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(filepath):
        return
    
    with open(filepath, "r") as f:
        data = json.load(f)
    
    candles = data.get("candles", [])
    if len(candles) < 2:
        return
    
    candles.sort(key=lambda x: x["t"])
    
    new_candles = []
    filled_count = 0
    max_gap = 0
    current_gap_run = 0
    
    # اولین کندل را مستقیماً اضافه می‌کنیم
    new_candles.append(candles[0])
    last_close = candles[0]["c"]
    
    for i in range(1, len(candles)):
        prev_candle = candles[i-1]
        curr_candle = candles[i]
        
        diff = curr_candle["t"] - prev_candle["t"]
        
        # اگر فاصله بیشتر از ۴ ساعت + تحمل بود
        if diff > (INTERVAL_MS + TOLERANCE_MS):
            # تعداد کندل‌های گم‌شده را حساب کن
            missing_count = (diff // INTERVAL_MS) - 1
            
            if missing_count > 0:
                for _ in range(missing_count):
                    new_t = prev_candle["t"] + INTERVAL_MS
                    new_candles.append({
                        "t": new_t, "o": last_close, "h": last_close, 
                        "l": last_close, "c": last_close, "v": 0.0,
                        "is_filled": True
                    })
                    filled_count += 1
                    current_gap_run += 1
                    prev_candle = {"t": new_t, "c": last_close} # آپدیت برای تکرار
                    
        max_gap = max(max_gap, current_gap_run)
        current_gap_run = 0
        
        new_candles.append(curr_candle)
        last_close = curr_candle["c"]
        
    max_gap = max(max_gap, current_gap_run)
    
    total_candles = len(new_candles)
    gap_pct = (filled_count / total_candles) * 100
    max_gap_hours = (max_gap * 4)
    
    quality = "GOOD"
    if gap_pct > 5.0 or max_gap_hours > 48:
        quality = "LOW_QUALITY"
        
    data["metadata"]["gaps_filled"] = filled_count
    data["metadata"]["gap_percentage"] = round(gap_pct, 2)
    data["metadata"]["max_gap_hours"] = max_gap_hours
    data["metadata"]["quality_status"] = quality
    data["candles"] = new_candles
    
    out_path = f"{DATA_DIR}/{symbol}_4h_clean.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
        
    print(f"✅ {symbol.replace('_', '-')}: Filled {filled_count} gaps ({gap_pct:.2f}%). Max gap: {max_gap_hours}h. Status: {quality}")

def main():
    print("=== Corrected Gap-Filler & Data Quality Filter ===")
    for sym in SYMBOLS:
        fill_gaps(sym)
    print("=" * 50)

if __name__ == "__main__":
    main()
