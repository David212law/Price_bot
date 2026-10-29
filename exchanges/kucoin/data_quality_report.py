import json
import os
from datetime import datetime, timezone

DATA_DIR = "exchanges/kucoin/data"
SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]

def format_ts(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')

def analyze_file(symbol):
    klines_file = f"{DATA_DIR}/{symbol}_4h.json"
    funding_file = f"{DATA_DIR}/{symbol}_funding.json"
    
    print(f"📊 **{symbol}**")
    
    if os.path.exists(klines_file):
        with open(klines_file, 'r') as f:
            data = json.load(f)
            candles = data.get("candles", [])
            
        if candles:
            total_candles = len(candles)
            start_time = candles[0]["t"]
            end_time = candles[-1]["t"]
            
            gaps = 0
            interval_ms = 4 * 60 * 60 * 1000
            for i in range(1, len(candles)):
                diff = candles[i]["t"] - candles[i-1]["t"]
                if diff > interval_ms + (30 * 60 * 1000):
                    gaps += 1
                        
            print(f"  • Klines: {total_candles} candles")
            print(f"  • Period: {format_ts(start_time)} to {format_ts(end_time)}")
            print(f"  • Gaps: {gaps} missing intervals")
            
            if gaps == 0:
                print(f"  • Quality: 🌟 PERFECT (Zero Gaps)")
        else:
            print("  • Klines: No data found.")
    else:
        print("  • Klines: File not found.")
        
    if os.path.exists(funding_file):
        with open(funding_file, 'r') as f:
            funding = json.load(f)
            if funding:
                print(f"  • Funding: {len(funding)} records found.")
    print("-" * 40)

def main():
    print(f"=== KuCoin Data Quality Report ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    for sym in SYMBOLS:
        analyze_file(sym)

if __name__ == "__main__":
    main()
