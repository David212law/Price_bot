import sys, os, json, requests, time
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_kucoin_klines(symbol, interval="240", years_back=3):
    """دریافت تاریخچه طولانی از KuCoin Futures API"""
    end_ms = int(time.time() * 1000)
    start_target_ms = end_ms - (years_back * 365 * 24 * 3600 * 1000)
    
    all_candles = []
    current_end = end_ms
    
    print(f"  {symbol}: fetching {years_back} years...")
    
    while current_end > start_target_ms:
        # هر درخواست 1500 کندل (حداکثر KuCoin)
        current_start = max(current_end - (1500 * 4 * 3600 * 1000), start_target_ms)
        try:
            r = requests.get(
                "https://api-futures.kucoin.com/api/v1/kline/query",
                params={
                    "symbol": symbol,
                    "granularity": interval,
                    "from": current_start,
                    "to": current_end
                },
                headers=HEADERS, timeout=30
            )
            if r.status_code != 200:
                print(f"    HTTP {r.status_code}")
                break
            data = r.json().get("data", [])
            if not data:
                print(f"    no data at {current_start}")
                break
            for c in data:
                all_candles.append({
                    "t": int(c[0]),
                    "o": float(c[1]), "h": float(c[2]),
                    "l": float(c[3]), "c": float(c[4]),
                    "v": float(c[5])
                })
            current_end = current_start - (4 * 3600 * 1000) - 1
            time.sleep(0.2)
        except Exception as e:
            print(f"    error: {e}")
            break
    
    # حذف تکراری‌ها
    unique = {c["t"]: c for c in all_candles}
    sorted_candles = [unique[t] for t in sorted(unique.keys())]
    
    print(f"  {symbol}: {len(sorted_candles)} unique candles")
    return sorted_candles

def save_symbol(symbol):
    """دریافت و ذخیره یک نماد (برای job موازی)"""
    candles = fetch_kucoin_klines(symbol, years_back=3)
    if not candles:
        print(f"❌ {symbol}: no data")
        return False
    
    # ذخیره در فایل
    path = f"exchanges/kucoin/data/{symbol}_4h.json"
    out = {
        "symbol": symbol,
        "interval": "4h",
        "source": "kucoin_futures_api",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "candles": candles
    }
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"✅ {symbol}: saved {len(candles)} candles to {path}")
    return True

if __name__ == "__main__":
    # اگر آرگومان داده شد، فقط همان نماد
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
        save_symbol(symbol)
    else:
        # همه نمادها
        for sym in ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]:
            save_symbol(sym)
