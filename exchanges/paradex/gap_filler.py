import json
import os
from datetime import datetime, timezone

DATA_DIR = "exchanges/paradex/data"
SYMBOLS = ["BTC_USD_PERP", "ETH_USD_PERP", "SOL_USD_PERP", "BNB_USD_PERP", "AVAX_USD_PERP", "XRP_USD_PERP"]
INTERVAL_MS = 4 * 60 * 60 * 1000  # 4 ساعت

def fill_gaps(symbol):
    filepath = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(filepath):
        return
    
    with open(filepath, "r") as f:
        data = json.load(f)
    
    candles = data.get("candles", [])
    if len(candles) < 2:
        return
    
    # ساخت دیکشنری برای دسترسی سریع
    candle_dict = {c["t"]: c for c in candles}
    
    start_t = candles[0]["t"]
    end_t = candles[-1]["t"]
    
    new_candles = []
    current_t = start_t
    filled_count = 0
    max_gap = 0
    current_gap_run = 0
    last_close = candles[0]["c"]
    
    while current_t <= end_t:
        if current_t in candle_dict:
            new_candles.append(candle_dict[current_t])
            last_close = candle_dict[current_t]["c"]
            max_gap = max(max_gap, current_gap_run)
            current_gap_run = 0
        else:
            # Forward Fill
            new_candles.append({
                "t": current_t, "o": last_close, "h": last_close, 
                "l": last_close, "c": last_close, "v": 0.0,
                "is_filled": True
            })
            filled_count += 1
            current_gap_run += 1
        current_t += INTERVAL_MS
        
    max_gap = max(max_gap, current_gap_run) # بررسی شکاف پایانی
    
    # محاسبه درصد شکاف
    total_expected = len(new_candles)
    gap_pct = (filled_count / total_expected) * 100
    max_gap_hours = (max_gap * 4)
    
    # تعیین وضعیت کیفیت
    quality = "GOOD"
    if gap_pct > 5.0 or max_gap_hours > 48:
        quality = "LOW_QUALITY"
        
    data["metadata"]["gaps_filled"] = filled_count
    data["metadata"]["gap_percentage"] = round(gap_pct, 2)
    data["metadata"]["max_gap_hours"] = max_gap_hours
    data["metadata"]["quality_status"] = quality
    data["candles"] = new_candles
    
    # ذخیره در فایل جدید
    out_path = f"{DATA_DIR}/{symbol}_4h_clean.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
        
    print(f"✅ {symbol.replace('_', '-')}: Filled {filled_count} gaps ({gap_pct:.2f}%). Max gap: {max_gap_hours}h. Status: {quality}")

def main():
    print("=== Gap-Filler & Data Quality Filter ===")
    for sym in SYMBOLS:
        fill_gaps(sym)
    print("=" * 50)

if __name__ == "__main__":
    main()
