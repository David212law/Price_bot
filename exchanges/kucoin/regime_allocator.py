"""Regime-Aware Capital Allocator for KuCoin (D-332)"""
import os, sys, json, base64, requests, time
from datetime import datetime, timezone
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_a20, calc_atr

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

STATE_FILE = "exchanges/kucoin/state/m11_kucoin_regime_state.json"
INITIAL_CAPITAL = 10000.0

# تخصیص
M31_ALLOC = 0.70
A20_RANGE_ALLOC = 0.15
CASH_ALLOC = 0.15

SYMBOLS = ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]
HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT: 
        print(f"[BALE] {msg[:80]}")
        return
    try: requests.post(f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage", json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except: pass

def load_state(filename):
    try:
        r = requests.get(f"https://api.github.com/repos/{GH_REPO}/contents/{filename}", headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            d = r.json()
            return json.loads(base64.b64decode(d["content"]).decode("utf-8")), d["sha"]
    except: pass
    return {}, None

def save_state(filename, data, sha=None):
    try:
        if not sha: _, sha = load_state(filename)
        payload = {"message": f"Update {filename}", "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()}
        if sha: payload["sha"] = sha
        r = requests.put(f"https://api.github.com/repos/{GH_REPO}/contents/{filename}", headers={"Authorization": f"token {GH_TOKEN}"}, json=payload, timeout=15)
        return r.status_code in [200, 201]
    except: return False

def fetch_klines(symbol, limit=300):
    now = int(time.time() * 1000)
    start = now - (limit * 4 * 3600 * 1000)
    try:
        r = requests.get(f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=240&from={start}&to={now}", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return [{"t": int(c[0]), "o": float(c[1]), "h": float(c[2]), "l": float(c[3]), "c": float(c[4]), "v": float(c[5])} for c in r.json().get("data", [])]
    except: pass
    return []

def calc_adx_simple(candles, period=14):
    if len(candles) < period * 2: return None
    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, len(candles)):
        h, l, ph, pl, pc = candles[i]["h"], candles[i]["l"], candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        tr = max(h-l, abs(h-pc), abs(l-pc))
        up = h - ph
        down = pl - l
        trs.append(tr); plus_dm.append(up if (up > down and up > 0) else 0); minus_dm.append(down if (down > up and down > 0) else 0)
    if len(trs) < period: return None
    atr = sum(trs[:period]) / period
    pdi_sum = sum(plus_dm[:period]); mdi_sum = sum(minus_dm[:period])
    dxs = []
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        pdi_sum = pdi_sum - pdi_sum/period + plus_dm[i]
        mdi_sum = mdi_sum - mdi_sum/period + minus_dm[i]
        if atr == 0: dx = 0
        else:
            pdi = 100 * pdi_sum / (atr * period)
            mdi = 100 * mdi_sum / (atr * period)
            dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0
        dxs.append(dx)
    if len(dxs) < period: return None
    adx = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        adx = (adx * (period - 1) + dxs[i]) / period
    return adx

def get_market_regime(btc_candles):
    """محاسبه رژیم با ADX"""
    adx = calc_adx_simple(btc_candles, 14)
    if adx is None: return "UNKNOWN", 0
    if adx > 25: return "TREND", adx
    if adx < 20: return "RANGE", adx
    return "NEUTRAL", adx

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== 🎯 Regime-Aware KuCoin Allocator ({now}) ===")
    
    state, sha = load_state(STATE_FILE)
    if not state or "capital" not in state:
        state = {"capital": INITIAL_CAPITAL, "m31_pos": {}, "a20_pos": {}, "cash": INITIAL_CAPITAL, "history": []}
    
    # تشخیص رژیم از BTC
    btc = fetch_klines("XBTUSDTM", 300)
    if not btc:
        print("❌ Cannot fetch BTC, aborting")
        return
    regime, adx = get_market_regime(btc)
    print(f"Market Regime: {regime} (ADX={adx:.1f})")
    
    # M31 همیشه فعال
    m31_capital = state["capital"] * M31_ALLOC
    # A20-RANGE فقط اگر RANGE
    a20_capital = state["capital"] * A20_RANGE_ALLOC if regime == "RANGE" else 0
    cash = state["capital"] * CASH_ALLOC if regime == "RANGE" else state["capital"] * (1 - M31_ALLOC)
    
    if regime == "RANGE":
        send_bale(f"🎯 Market RANGE detected (ADX={adx:.1f})")
        send_bale(f"   M31: 70%, A20: 15%, Cash: 15%")
    else:
        send_bale(f"📊 Market {regime} (ADX={adx:.1f})")
        send_bale(f"   M31: 70%, Cash: {100-M31_ALLOC*100:.0f}%, A20: OFF")
    
    # (پیاده‌سازی کامل M31 و A20-RANGE در گام بعد)
    state["last_regime"] = regime
    state["last_adx"] = adx
    state["capital_alloc"] = {"M31": M31_ALLOC, "A20_RANGE": A20_RANGE_ALLOC if regime=="RANGE" else 0, "Cash": CASH_ALLOC if regime=="RANGE" else 1-M31_ALLOC}
    
    save_state(STATE_FILE, state, sha)
    print(f"✅ State saved")

if __name__ == "__main__":
    main()
