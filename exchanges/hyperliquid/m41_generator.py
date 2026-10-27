import json, os, requests, time

SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
SIGNAL_FILE = "exchanges/hyperliquid/state/m41_signals.json"
DATA_DIR = "data/hyperliquid"
BB_PERIOD = 20
EMA_PERIOD = 20
KC_MULT = 1.5
ATR_PERIOD = 14
VOL_SMA_PERIOD = 20
MIN_SQUEEZE_CANDLES = 4
SL_ATR = 2.0
TP_ATR = 4.0

def fetch_ohlcv(symbol, limit=100):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (limit * 4 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": "4h", "startTime": start_ms, "endTime": now_ms}}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return [{"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"]), "v": float(c["v"])} for c in r.json()]
    except: pass
    return []

def calc_ema(closes, period):
    if len(closes) < period: return None
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
    return e

def calc_bb(closes, period, std_mult):
    if len(closes) < period: return None, None
    window = closes[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std = variance ** 0.5
    return sma + (std_mult * std), sma - (std_mult * std)

def calc_atr(candles, period=14):
    if len(candles) < period + 1: return None
    trs = []
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs[-period:]) / period

def main():
    signals = []
    for sym in SYMBOLS:
        candles = fetch_ohlcv(sym, limit=50)
        if len(candles) < 30: continue
        
        closes = [c["c"] for c in candles]
        vols = [c["v"] for c in candles]
        
        # Use last closed candle (-2) for breakout, and prior 4 for squeeze
        idx = len(candles) - 2 
        
        bb_u, bb_l = calc_bb(closes[:idx+1], BB_PERIOD, 2.0)
        ema20 = calc_ema(closes[:idx+1], EMA_PERIOD)
        atr14 = calc_atr(candles[:idx+1], ATR_PERIOD)
        vol_sma = sum(vols[idx-VOL_SMA_PERIOD:idx]) / VOL_SMA_PERIOD
        
        if None in [bb_u, bb_l, ema20, atr14]: continue
        
        # Check squeeze in last 4 candles
        squeeze_active = True
        for k in range(1, MIN_SQUEEZE_CANDLES + 1):
            b_u, b_l = calc_bb(closes[:idx+1-k], BB_PERIOD, 2.0)
            e = calc_ema(closes[:idx+1-k], EMA_PERIOD)
            a = calc_atr(candles[:idx+1-k], ATR_PERIOD)
            if None in [b_u, b_l, e, a] or not (b_u < e + (KC_MULT * a) and b_l > e - (KC_MULT * a)):
                squeeze_active = False
                break
                
        if squeeze_active:
            c = candles[idx]
            side = None
            if c["c"] > bb_u and c["v"] > (1.2 * vol_sma): side = "LONG"
            elif c["c"] < bb_l and c["v"] > (1.2 * vol_sma): side = "SHORT"
            
            if side:
                tp = c["c"] + (TP_ATR * atr14) if side == "LONG" else c["c"] - (TP_ATR * atr14)
                sl = c["c"] - (SL_ATR * atr14) if side == "LONG" else c["c"] + (SL_ATR * atr14)
                signals.append({"symbol": sym, "action": f"OPEN_{side}", "price": c["c"], "sl": sl, "tp": tp})

    os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
    with open(SIGNAL_FILE, 'w') as f: json.dump({"signals": signals}, f, indent=2)
    print(f"M41 Generator: {len(signals)} signals.")

if __name__ == "__main__": main()
