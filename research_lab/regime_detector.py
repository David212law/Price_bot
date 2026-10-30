"""Runtime Regime Detection — مشترک بین allocatorها"""
import os, sys, time, requests
sys.path.append(os.getcwd())

HEADERS = {"User-Agent": "Mozilla/5.0"}

def calc_adx(candles, period=14):
    """محاسبه ADX از کندل‌ها"""
    if len(candles) < period * 2:
        return None
    trs, pdms, mdms = [], [], []
    for i in range(1, len(candles)):
        h, l = candles[i]["h"], candles[i]["l"]
        ph, pl, pc = candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
        up, dn = h - ph, pl - l
        pdms.append(up if (up > dn and up > 0) else 0)
        mdms.append(dn if (dn > up and dn > 0) else 0)
    if len(trs) < period: return None
    atr = sum(trs[:period]) / period
    ps, ms = sum(pdms[:period]), sum(mdms[:period])
    dxs = []
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        ps = ps - ps/period + pdms[i]
        ms = ms - ms/period + mdms[i]
        if atr == 0:
            dx = 0
        else:
            pdi = 100 * ps / (atr * period)
            mdi = 100 * ms / (atr * period)
            dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0
        dxs.append(dx)
    if len(dxs) < period: return None
    adx = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        adx = (adx * (period - 1) + dxs[i]) / period
    return adx

def fetch_btc_candles_for_regime():
    """دریافت BTC از KuCoin (معیار جهانی)"""
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
    """رژیم فعلی بازار: TREND / RANGE / NEUTRAL / UNKNOWN"""
    candles = fetch_btc_candles_for_regime()
    if not candles or len(candles) < 30:
        return "UNKNOWN", 0.0
    adx = calc_adx(candles, 14)
    if adx is None:
        return "UNKNOWN", 0.0
    if adx > 25:
        return "TREND", adx
    if adx < 20:
        return "RANGE", adx
    return "NEUTRAL", adx

def should_activate_strategy(strategy_name, regime):
    """آیا استراتژی در این رژیم مجاز است؟"""
    rules = {
        "M31": {"TREND", "RANGE", "NEUTRAL"},  # همیشه فعال
        "M62_PriceMomentum": {"TREND"},        # فقط روند
        "M40_Pullback": {"RANGE"},              # فقط رنج
        "A20_SuperTrend": {"TREND", "RANGE"},  # روند و رنج
        "A8_Grid": {"RANGE"},                   # فقط رنج
    }
    allowed = rules.get(strategy_name, {"TREND", "RANGE", "NEUTRAL"})
    return regime in allowed
