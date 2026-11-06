"""D-558: Data Hub — Live fetch from all exchanges."""
import os, json, urllib.request
from datetime import datetime, timezone, timedelta


def _fetch(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def fetch_hl(symbol="BTC"):
    """Fetch HL prices + funding. Returns dict {date: price} + current funding."""
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(days=30)).timestamp() * 1000)
    end = int(now.timestamp() * 1000)
    url = "https://api.hyperliquid.xyz/info"
    try:
        req = urllib.request.Request(url, data=json.dumps({
            "type": "candleSnapshot",
            "req": {"coin": symbol, "interval": "1d",
                    "startTime": start, "endTime": end}
        }).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            candles = json.loads(r.read())
        prices = {}
        for c in candles:
            ts = int(c.get("t", c.get("T", 0))) // 1000
            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[d] = float(c.get("c", c.get("close", 0)))
        return {"prices": prices, "exchange": "hyperliquid", "symbol": symbol}
    except Exception as e:
        return {"error": str(e)[:100], "exchange": "hyperliquid", "symbol": symbol}


def fetch_aster(symbol="BTCUSDT"):
    """Fetch Aster prices."""
    url = f"https://fapi.asterdex.com/fapi/v1/klines?symbol={symbol}&interval=1d&limit=30"
    data = _fetch(url)
    if not data: return {"error": "no data", "exchange": "aster", "symbol": symbol}
    prices = {}
    try:
        for c in data:
            ts = int(c[0]) // 1000
            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[d] = float(c[4])
        return {"prices": prices, "exchange": "aster", "symbol": symbol}
    except Exception as e:
        return {"error": str(e)[:100], "exchange": "aster", "symbol": symbol}


def fetch_kucoin(symbol="XBTUSDTM"):
    """Fetch KuCoin prices."""
    url = f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=1440"
    data = _fetch(url)
    if not data or data.get("code") != "200000": 
        return {"error": "no data", "exchange": "kucoin", "symbol": symbol}
    prices = {}
    try:
        for c in data["data"][-30:]:
            ts = int(c[0]) // 1000
            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[d] = float(c[4])
        return {"prices": prices, "exchange": "kucoin", "symbol": symbol}
    except Exception as e:
        return {"error": str(e)[:100], "exchange": "kucoin", "symbol": symbol}


def fetch_wallex(symbol="USDTTMN"):
    """Fetch Wallex prices."""
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(days=30)).timestamp())
    end = int(now.timestamp())
    url = f"https://api.wallex.ir/v1/udf/history?symbol={symbol}&resolution=1D&from={start}&to={end}"
    data = _fetch(url)
    if not data or data.get("s") != "ok":
        return {"error": "no data", "exchange": "wallex", "symbol": symbol}
    prices = {}
    try:
        for t, c in zip(data["t"], data["c"]):
            d = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[d] = float(c)
        return {"prices": prices, "exchange": "wallex", "symbol": symbol}
    except Exception as e:
        return {"error": str(e)[:100], "exchange": "wallex", "symbol": symbol}


def fetch_all():
    """Fetch live data from all exchanges."""
    results = {
        "hyperliquid": fetch_hl("BTC"),
        "aster": fetch_aster("BTCUSDT"),
        "kucoin": fetch_kucoin("XBTUSDTM"),
        "wallex": fetch_wallex("USDTTMN"),
    }
    return results


if __name__ == "__main__":
    data = fetch_all()
    for exch, d in data.items():
        if "error" in d:
            print(f"{exch}: ERROR — {d['error']}")
        else:
            prices = d["prices"]
            print(f"{exch}: {len(prices)} days, last={prices[max(prices)]:.2f}")
