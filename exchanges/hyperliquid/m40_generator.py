import json, os, requests, time

SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
SIGNAL_FILE = "exchanges/hyperliquid/state/m40_signals.json"
DATA_DIR = "data/hyperliquid"
EMA_TREND = 200
RSI_PERIOD = 14
RSI_LONG = 35
RSI_SHORT = 65
ATR_PERIOD = 14
TP_ATR = 4.0
SL_ATR = 2.0

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

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains, losses = 0, 0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    return 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0

def main():
    signals = []
    for sym in SYMBOLS:
        path = f"{DATA_DIR}/{sym}_4h.json"
        if not os.path.exists(path): continue
        with open(path, 'r') as f: candles = json.load(f)
        
        if len(candles) < EMA_TREND + 2: continue
        closes = [c["c"] for c in candles]
        
        # Use last closed candle (-2)
        ema_val = calc_ema(closes[:-1], EMA_TREND)
        rsi_val = calc_rsi(closes[:-1], RSI_PERIOD)
        atr_val = calc_atr(candles[:-1], ATR_PERIOD)
        current_price = candles[-2]["c"]
        
        if None in [ema_val, rsi_val, atr_val]: continue
        
        side = None
        if current_price > ema_val and rsi_val < RSI_LONG: side = "LONG"
        elif current_price < ema_val and rsi_val > RSI_SHORT: side = "SHORT"
        
        if side:
            signals.append({
                "symbol": sym, "action": f"OPEN_{side}", "price": current_price, 
                "atr": atr_val, "tp": current_price + (TP_ATR * atr_val) if side == "LONG" else current_price - (TP_ATR * atr_val),
                "sl": current_price - (SL_ATR * atr_val) if side == "LONG" else current_price + (SL_ATR * atr_val)
            })

    os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
    with open(SIGNAL_FILE, 'w') as f: json.dump({"signals": signals}, f, indent=2)
    print(f"M40 Generator: {len(signals)} signals.")

if __name__ == "__main__": main()
