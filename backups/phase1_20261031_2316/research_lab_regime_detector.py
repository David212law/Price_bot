"""Runtime Regime Detector — wrapper روی regime_core"""
import time, requests
from research_lab.regime_core import detect_regime, calc_adx, should_activate_strategy

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_btc_candles():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (100 * 4 * 3600 * 1000)
    try:
        r = requests.get(
            "https://api-futures.kucoin.com/api/v1/kline/query",
            params={"symbol": "XBTUSDTM", "granularity": 240, "from": start_ms, "to": now_ms},
            headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            return [{"t": int(c[0]), "o": float(c[1]), "h": float(c[2]),
                     "l": float(c[3]), "c": float(c[4]), "v": float(c[5])} for c in data]
    except: pass
    return []

def get_current_regime():
    """رژیم فعلی بازار — با استفاده از regime_core"""
    candles = fetch_btc_candles()
    if not candles or len(candles) < 30:
        return "UNKNOWN", 0.0
    regime = detect_regime(candles, i=len(candles)-1)
    adx = calc_adx(candles[-60:], 14) if len(candles) >= 30 else 0.0
    return regime, (adx or 0.0)
