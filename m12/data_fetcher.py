"""Live data from Aster, Hyperliquid, KuCoin, Wallex. Fallback to local JSON."""
import json, os, requests, time
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DATA_DIR = os.path.join(_ROOT, "data")
CACHE = os.path.join(_HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

def _cache_path(key): return os.path.join(CACHE, f"{key}.json")
def _read_cache(key, ttl=3600):
    p = _cache_path(key)
    if not os.path.exists(p): return None
    if time.time() - os.path.getmtime(p) > ttl: return None
    try: return json.load(open(p))
    except: return None
def _write_cache(key, data):
    try: json.dump(data, open(_cache_path(key), "w"))
    except: pass

def _to_candles(raw):
    """raw: list of {t, o, h, l, c} → normalized"""
    return [{"t": int(r["t"]), "o": float(r["o"]), "h": float(r["h"]),
             "l": float(r["l"]), "c": float(r["c"]), "v": 1.0} for r in raw]

# ─── Aster (public, no auth) ───
def fetch_aster(symbol="BTCUSDT", interval="1d", limit=500):
    key = f"aster_{symbol}_{interval}_{limit}"
    cached = _read_cache(key, ttl=3600)
    if cached: return cached
    try:
        r = requests.get("https://fapi.asterdex.com/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
        if r.status_code == 200:
            data = [{"t": int(k[0]), "o": k[1], "h": k[2], "l": k[3], "c": k[4]} for k in r.json()]
            _write_cache(key, data)
            return data
    except Exception as e: print(f"[aster] {symbol}: {e}")
    return []

# ─── Hyperliquid (public POST) ───
def fetch_hl(symbol="BTC", interval="1d", limit=500):
    key = f"hl_{symbol}_{interval}_{limit}"
    cached = _read_cache(key, ttl=3600)
    if cached: return cached
    try:
        end = int(time.time() * 1000)
        intervals = {"1d": 24*3600*1000, "4h": 4*3600*1000, "1h": 3600*1000}
        delta = intervals.get(interval, 24*3600*1000) * limit
        start = end - delta
        payload = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": interval, "startTime": start, "endTime": end}}
        r = requests.post("https://api.hyperliquid.xyz/info", json=payload, timeout=15)
        if r.status_code == 200:
            data = [{"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"])}
                    for c in r.json()]
            _write_cache(key, data)
            return data
    except Exception as e: print(f"[hl] {symbol}: {e}")
    return []

# ─── KuCoin (public) ───
def fetch_kucoin(symbol="XBTUSDTM", interval="1day", limit=500):
    key = f"kucoin_{symbol}_{interval}_{limit}"
    cached = _read_cache(key, ttl=3600)
    if cached: return cached
    try:
        to = int(time.time() * 1000)
        frm = to - limit * 86400 * 1000
        r = requests.get("https://api-futures.kucoin.com/api/v1/kline/query",
            params={"symbol": symbol, "granularity": 1440, "from": frm, "to": to}, timeout=15)
        if r.status_code == 200 and r.json().get("data"):
            data = [{"t": int(c[0]), "o": c[1], "h": c[2], "l": c[3], "c": c[4]}
                    for c in r.json()["data"]]
            _write_cache(key, data)
            return data
    except Exception as e: print(f"[kucoin] {symbol}: {e}")
    return []

# ─── Wallex (public, IR) ───
def fetch_wallex_prices():
    key = "wallex_prices"
    cached = _read_cache(key, ttl=300)
    if cached: return cached
    try:
        r = requests.get("https://api.wallex.ir/v1/markets", timeout=15)
        if r.status_code == 200:
            _write_cache(key, r.json())
            return r.json()
    except Exception as e: print(f"[wallex] {e}")
    return {}

def fetch_wallex_candles(symbol="BTCTMN", resolution="1D", limit=500):
    """Wallex public candles. Returns [] if not available."""
    key = f"wallex_c_{symbol}"
    cached = _read_cache(key, ttl=3600)
    if cached: return cached
    try:
        to = int(time.time())
        frm = to - limit * 86400
        r = requests.get(f"https://api.wallex.ir/v1/udf/history",
            params={"symbol": symbol, "resolution": resolution, "from": frm, "to": to}, timeout=15)
        if r.status_code == 200 and r.json().get("s") == "ok":
            j = r.json()
            data = [{"t": j["t"][i]*1000, "o": j["o"][i], "h": j["h"][i],
                     "l": j["l"][i], "c": j["c"][i]} for i in range(len(j["t"]))]
            _write_cache(key, data)
            return data
    except Exception as e: print(f"[wallex_c] {symbol}: {e}")
    return []

# ─── Unified loader for bot ───
def load_market(market, symbols, prefer_live=True):
    """market in {TMN, USDT, GLOBAL}. symbols: dict {sym: fallback_prices}
    If prefer_live and API returns data → use it. Else fallback to historical."""
    out = {}
    for sym in symbols:
        prices = None
        if prefer_live:
            if market in ("TMN", "USDT"):
                cd = fetch_wallex_candles(f"{sym}{market}")
                if cd and len(cd) >= 100: prices = [c["c"] for c in cd]
            elif market == "GLOBAL":
                cd = fetch_hl(sym, "1d", 500)
                if cd and len(cd) >= 100: prices = [c["c"] for c in cd]
        if prices is None:
            prices = symbols[sym]  # fallback
        out[sym] = prices
    return out

if __name__ == "__main__":
    print("Testing live fetch...")
    b = fetch_aster("BTCUSDT", "1d", 100)
    print(f"  Aster BTC: {len(b)} candles")
    h = fetch_hl("BTC", "1d", 100)
    print(f"  HL BTC: {len(h)} candles")
    k = fetch_kucoin("XBTUSDTM", "1day", 100)
    print(f"  KuCoin XBT: {len(k)} candles")
    w = fetch_wallex_candles("BTCTMN")
    print(f"  Wallex BTCTMN: {len(w)} candles")
