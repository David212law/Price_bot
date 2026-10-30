import sys, os, json, requests, time
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_batch(symbol, from_ms, to_ms):
    """دریافت یک batch از KuCoin"""
    try:
        r = requests.get(
            "https://api-futures.kucoin.com/api/v1/kline/query",
            params={"symbol": symbol, "granularity": 240, "from": from_ms, "to": to_ms},
            headers=HEADERS, timeout=30
        )
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}")
            return []
        data = r.json().get("data", [])
        return [{"t": int(c[0]), "o": float(c[1]), "h": float(c[2]),
                 "l": float(c[3]), "c": float(c[4]), "v": float(c[5])} for c in data]
    except Exception as e:
        print(f"    error: {e}")
        return []

def fetch_full_history(symbol, years_back=3):
    """دریافت تاریخچه کامل با batch 400 کندلی و تایید"""
    end_ms = int(time.time() * 1000)
    start_target_ms = end_ms - (years_back * 365 * 24 * 3600 * 1000)
    batch_ms = 400 * 4 * 3600 * 1000  # 400 کندل × 4 ساعت
    
    all_candles = []
    current_to = end_ms
    iteration = 0
    max_iterations = 100  # ایمنی
    
    print(f"  {symbol}: from {datetime.fromtimestamp(end_ms/1000, tz=timezone.utc).strftime('%Y-%m-%d')} backward...")
    
    while current_to > start_target_ms and iteration < max_iterations:
        iteration += 1
        current_from = max(current_to - batch_ms, start_target_ms)
        
        batch = fetch_batch(symbol, current_from, current_to)
        
        if not batch:
            print(f"    iter {iteration}: no data, stopping")
            break
        
        first_t = datetime.fromtimestamp(batch[0]['t']/1000, tz=timezone.utc).strftime('%Y-%m-%d')
        last_t = datetime.fromtimestamp(batch[-1]['t']/1000, tz=timezone.utc).strftime('%Y-%m-%d')
        print(f"    iter {iteration}: {len(batch)} candles | {first_t} → {last_t}")
        
        all_candles.extend(batch)
        # حرکت عقب‌تر: تا اولین کندل دریافتی منهای ۱
        current_to = batch[0]['t'] - 1
        time.sleep(0.3)
    
    # حذف تکراری‌ها و مرتب‌سازی
    unique = {c["t"]: c for c in all_candles}
    sorted_candles = [unique[t] for t in sorted(unique.keys())]
    
    return sorted_candles

def save_symbol(symbol):
    candles = fetch_full_history(symbol, years_back=3)
    if not candles:
        print(f"❌ {symbol}: no data")
        return False
    
    path = f"exchanges/kucoin/data/{symbol}_4h.json"
    out = {"symbol": symbol, "interval": "4h",
           "source": "kucoin_futures_api",
           "fetched_at": datetime.now(timezone.utc).isoformat(),
           "candles": candles}
    with open(path, "w") as f:
        json.dump(out, f)
    
    start = datetime.fromtimestamp(candles[0]['t']/1000, tz=timezone.utc).strftime('%Y-%m-%d')
    end = datetime.fromtimestamp(candles[-1]['t']/1000, tz=timezone.utc).strftime('%Y-%m-%d')
    days = (candles[-1]['t'] - candles[0]['t']) / (24*3600*1000)
    print(f"✅ {symbol}: {len(candles)} candles | {days:.0f} days | {start} → {end}\n")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        save_symbol(sys.argv[1])
    else:
        for sym in ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]:
            save_symbol(sym)
