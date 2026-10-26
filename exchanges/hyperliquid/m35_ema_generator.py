import json, os, requests, time

SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
SIGNAL_FILE = "exchanges/hyperliquid/state/m35_signals.json"
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14

def fetch_ohlcv(symbol):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (300 * 24 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": "1d", "startTime": start_ms, "endTime": now_ms}}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return [{"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"])} for c in r.json()]
    except: pass
    return []

def calc_ema(closes, period):
    if len(closes) < period: return None
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
    return e

def calc_atr(candles, period=14):
    if len(candles) < period + 1: return None
    trs = []
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs[-period:]) / period

def main():
    os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
    signals = []
    for sym in SYMBOLS:
        candles = fetch_ohlcv(sym)
        if len(candles) < EMA_SLOW + 2: continue
        
        closes = [c["c"] for c in candles]
        ef = calc_ema(closes[:-1], EMA_FAST)
        es = calc_ema(closes[:-1], EMA_SLOW)
        ef_prev = calc_ema(closes[:-2], EMA_FAST)
        es_prev = calc_ema(closes[:-2], EMA_SLOW)
        atr_val = calc_atr(candles[:-1], ATR_PERIOD)
        current_price = candles[-2]["c"]
        
        if None in [ef, es, ef_prev, es_prev, atr_val]: continue
        
        if ef > es and ef_prev <= es_prev:
            signals.append({"symbol": sym, "action": "OPEN_LONG", "price": current_price, "atr": atr_val})
        elif ef < es and ef_prev >= es_prev:
            signals.append({"symbol": sym, "action": "OPEN_SHORT", "price": current_price, "atr": atr_val})
            
    with open(SIGNAL_FILE, 'w') as f: json.dump({"signals": signals}, f, indent=2)
    print(f"M35 Generator: {len(signals)} signals generated.")

if __name__ == "__main__": main()
