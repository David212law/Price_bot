"""Runtime Regime Detector — KuCoin primary, Hyperliquid fallback."""
import time, requests
from research_lab.regime_core import detect_regime, calc_adx, should_activate_strategy

HEADERS = {"User-Agent": "Mozilla/5.0"}

def _fetch_kucoin():
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

def _fetch_hyperliquid():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (100 * 4 * 3600 * 1000)
    try:
        r = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "candleSnapshot",
                  "req": {"coin": "BTC", "interval": "4h",
                          "startTime": start_ms, "endTime": now_ms}},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            # HL candle: {"t":..., "T":..., "s":"BTC", "i":"4h", "o":"...", "c":"...", "h":"...", "l":"...", "v":"..."}
            return [{"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]),
                     "l": float(c["l"]), "c": float(c["c"]), "v": float(c["v"])} for c in data]
    except: pass
    return []

def fetch_btc_candles():
    """Try KuCoin first, then Hyperliquid. Returns [] if both fail."""
    c = _fetch_kucoin()
    if c and len(c) >= 30:
        return c
    c = _fetch_hyperliquid()
    return c if c else []

def get_current_regime():
    """Current market regime — KuCoin primary, HL fallback."""
    candles = fetch_btc_candles()
    if not candles or len(candles) < 30:
        return "UNKNOWN", 0.0
    regime = detect_regime(candles, i=len(candles)-1)
    adx = calc_adx(candles[-60:], 14) if len(candles) >= 30 else 0.0
    return regime, (adx or 0.0)
