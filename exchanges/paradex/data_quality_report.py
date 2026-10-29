import json
import os
from datetime import datetime, timezone

DATA_DIR = "exchanges/paradex/data"
SYMBOLS = ["BTC_USD_PERP", "ETH_USD_PERP", "SOL_USD_PERP", "BNB_USD_PERP", "AVAX_USD_PERP", "XRP_USD_PERP"]

def format_ts(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')

def analyze_file(symbol):
    klines_file = f"{DATA_DIR}/{symbol}_4h.json"
    funding_file = f"{DATA_DIR}/{symbol}_funding.json"
    
    print(f"📊 **{symbol.replace('_', '-')}**")
    
    # 1. Klines Analysis
    if os.path.exists(klines_file):
        with open(klines_file, 'r') as f:
            data = json.load(f)
            candles = data.get("candles", [])
            
        if candles:
            total_candles = len(candles)
            start_time = candles[0]["t"]
            end_time = candles[-1]["t"]
            
            # محاسبه شکاف‌ها (Gaps)
            gaps = 0
            max_gap_ms = 0
            interval_ms = 4 * 60 * 60 * 1000 # 4 ساعت
            
            for i in range(1, len(candles)):
                diff = candles[i]["t"] - candles[i-1]["t"]
                if diff > interval_ms:
                    gaps += 1
                    if diff > max_gap_ms:
                        max_gap_ms = diff
                        
            print(f"  • Klines: {total_candles} candles")
            print(f"  • Period: {format_ts(start_time)} to {format_ts(end_time)}")
            print(f"  • Gaps: {gaps} missing intervals", end="")
            if gaps > 0:
                print(f" (Max gap: {max_gap_ms / (3600*1000):.1f} hours)")
            else:
                print()
        else:
            print("  • Klines: No data found.")
    else:
        print("  • Klines: File not found.")
        
    # 2. Funding Analysis
    if os.path.exists(funding_file):
        with open(funding_file, 'r') as f:
            funding = json.load(f)
            if funding:
                latest = funding[-1]
                rate = float(latest.get("funding_rate", 0)) * 100
                period = latest.get("funding_period_hours", "?")
                print(f"  • Funding: {len(funding)} records (Latest: {rate:.4f}% per {period}h)")
            else:
                print("  • Funding: No records.")
    else:
        print("  • Funding: File not found.")
        
    print("-" * 40)

def main():
    print(f"=== Paradex Data Quality Report ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    for sym in SYMBOLS:
        analyze_file(sym)

if __name__ == "__main__":
    main()
