import os
import json
import base64
import requests
import time
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

STATE_FILE = "exchanges/kucoin/state/m11_kucoin_paper_state.json"
INITIAL_CAPITAL = 10000.0

# Allocations (D-218)
M31_ALLOC = 0.50  # Funding
A20_ALLOC = 0.25  # SuperTrend (50% of directional bucket)
M40_ALLOC = 0.25  # Pullback (50% of directional bucket)

# M31 Params
M31_LEVERAGE = 6
SMA_PERIODS = 12
ENTRY_THRESHOLD = 0.00005
EXIT_THRESHOLD = 0.00001
COOLDOWN_HOURS = 24

# Trading Fees
TAKER_FEE = 0.0006
MAKER_FEE = 0.0002

SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT: 
        print(f"[BALE] {msg[:80]}")
        return
    try: requests.post(f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage", json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except: pass

def load_from_github(filename):
    try:
        r = requests.get(f"https://api.github.com/repos/{GH_REPO}/contents/{filename}", headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            d = r.json()
            return json.loads(base64.b64decode(d["content"]).decode("utf-8")), d["sha"]
    except: pass
    return {}, None

def save_to_github(filename, data, sha=None):
    try:
        if not sha: _, sha = load_from_github(filename)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {"message": f"Update {filename}", "content": base64.b64encode(content.encode()).decode()}
        if sha: payload["sha"] = sha
        r = requests.put(f"https://api.github.com/repos/{GH_REPO}/contents/{filename}", headers={"Authorization": f"token {GH_TOKEN}"}, json=payload, timeout=15)
        return r.status_code in [200, 201]
    except: return False

def fetch_funding_rate(symbol):
    try:
        r = requests.get(f"https://api-futures.kucoin.com/api/v1/funding-rate/{symbol}/current", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            d = r.json().get("data", {})
            return float(d.get("value", 0)), d.get("timepoint", 0)
    except: pass
    return 0.0, 0

def fetch_klines(symbol, limit=300):
    now = int(time.time() * 1000)
    start = now - (limit * 4 * 3600 * 1000)
    try:
        r = requests.get(f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=240&from={start}&to={now}", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return [{"t": int(c[0]), "o": float(c[1]), "h": float(c[2]), "l": float(c[3]), "c": float(c[4]), "v": float(c[5])} for c in r.json().get("data", [])]
    except: pass
    return []

def calc_atr(candles, period=14):
    atr = [None]*len(candles)
    if len(candles) < period+1: return atr
    trs = [0]*len(candles)
    for i in range(1, len(candles)):
        trs[i] = max(candles[i]["h"]-candles[i]["l"], abs(candles[i]["h"]-candles[i-1]["c"]), abs(candles[i]["l"]-candles[i-1]["c"]))
    atr[period] = sum(trs[1:period+1])/period
    for i in range(period+1, len(candles)):
        atr[i] = (atr[i-1]*(period-1)+trs[i])/period
    return atr

def calc_supertrend(candles, period=10, mult=3.0):
    atr = calc_atr(candles, period)
    st, dirs = [None]*len(candles), [1]*len(candles)
    for i in range(period, len(candles)):
        if atr[i] is None: continue
        hl2 = (candles[i]["h"]+candles[i]["l"])/2
        ub, lb = hl2+mult*atr[i], hl2-mult*atr[i]
        if i == period: st[i], dirs[i] = ub, 1; continue
        if candles[i]["c"] > st[i-1]:
            dirs[i] = 1; st[i] = max(lb, st[i-1]) if dirs[i-1]==1 else lb
        else:
            dirs[i] = -1; st[i] = min(ub, st[i-1]) if dirs[i-1]==-1 else ub
    return st, dirs

def calc_ema(closes, period):
    ema = [None]*len(closes)
    if len(closes) < period: return ema
    k = 2/(period+1); e = sum(closes[:period])/period; ema[period-1] = e
    for i in range(period, len(closes)):
        e = closes[i]*k + e*(1-k); ema[i] = e
    return ema

def calc_rsi(closes, period=14):
    rsi = [None]*len(closes)
    if len(closes) < period+1: return rsi
    gains = losses = 0
    for i in range(1, period+1):
        ch = closes[i]-closes[i-1]
        if ch > 0: gains += ch
        else: losses += abs(ch)
    ag, al = gains/period, losses/period
    rsi[period] = 100 - 100/(1+ag/al) if al else 100
    for i in range(period+1, len(closes)):
        ch = closes[i]-closes[i-1]
        ag = (ag*(period-1)+max(ch,0))/period; al = (al*(period-1)+max(-ch,0))/period
        rsi[i] = 100 - 100/(1+ag/al) if al else 100
    return rsi

def main():
    print(f"=== M11-KuCoin Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    
    state, sha = load_from_github(STATE_FILE)
    
    # پاکسازی: اگر فایل State قدیمی ناقص بود، کلیدهای جدید اضافه شوند
    if isinstance(state, dict) and "m31_capital" in state:
        if "a20_pos" not in state: state["a20_pos"] = {}
        if "m40_pos" not in state: state["m40_pos"] = {}
        if "a20_capital" not in state: state["a20_capital"] = state.get("total_equity", 10000) * A20_ALLOC
        if "m40_capital" not in state: state["m40_capital"] = state.get("total_equity", 10000) * M40_ALLOC
        if "m35_pos" in state: del state["m35_pos"]
        if "m35_capital" in state:
            # انتقال M35 قدیمی به M40 جدید
            old_m35 = state.pop("m35_capital", 0)
            state["m40_capital"] = state.get("m40_capital", 0) + old_m35
    
    if not isinstance(state, dict) or "m31_capital" not in state:
        state = {
            "total_equity": INITIAL_CAPITAL,
            "m31_capital": INITIAL_CAPITAL * M31_ALLOC,
            "a20_capital": INITIAL_CAPITAL * A20_ALLOC,
            "m40_capital": INITIAL_CAPITAL * M40_ALLOC,
            "m31_pos": {}, "a20_pos": {}, "m40_pos": {},
            "history": []
        }

    # ── M31 Funding ──
    for sym in SYMBOLS:
        rate, tp = fetch_funding_rate(sym)
        if tp == 0: continue
        st = state["m31_pos"].get(sym, {"in_pos": False, "hist": [], "last_exit": 0, "last_processed": 0})
        st["hist"].append(rate)
        if len(st["hist"]) > SMA_PERIODS: st["hist"].pop(0)
        avg = sum(st["hist"]) / len(st["hist"])
        
        if tp > st.get("last_processed", 0):
            st["last_processed"] = tp
            if st["in_pos"]:
                income = (state["m31_capital"] / len(SYMBOLS)) * M31_LEVERAGE * rate
                state["m31_capital"] += income
                if avg < EXIT_THRESHOLD:
                    cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                    state["m31_capital"] -= cost
                    st["in_pos"] = False; st["last_exit"] = tp
                    send_bale(f"🔴 M31 CLOSED | {sym}")
            elif avg > ENTRY_THRESHOLD and rate > 0 and (tp - st["last_exit"])/(3600*1000) >= COOLDOWN_HOURS:
                cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                state["m31_capital"] -= cost
                st["in_pos"] = True
                send_bale(f"🟢 M31 OPENED | {sym}")
        state["m31_pos"][sym] = st

    # ── A20 (SuperTrend) ──
    for sym in SYMBOLS:
        k = fetch_klines(sym, 300)
        if len(k) < 20: continue
        st, dirs = calc_supertrend(k)
        if st[-1] is None: continue
        
        pos = state["a20_pos"].get(sym)
        if pos:
            exit_ = (pos["side"]=="LONG" and (k[-1]["c"] < st[-1] or dirs[-1]==-1)) or \
                    (pos["side"]=="SHORT" and (k[-1]["c"] > st[-1] or dirs[-1]==1))
            if exit_:
                pnl = pos["invested"] * ((k[-1]["c"]-pos["entry"])/pos["entry"] if pos["side"]=="LONG" else (pos["entry"]-k[-1]["c"])/pos["entry"])
                state["a20_capital"] += pos["invested"] + pnl
                del state["a20_pos"][sym]
                send_bale(f"🔵 A20 CLOSED | {sym} | PnL: {pnl:+.2f}")
        elif len(state["a20_pos"]) < 3:
            side = "LONG" if (dirs[-1]==1 and dirs[-2]==-1) else "SHORT" if (dirs[-1]==-1 and dirs[-2]==1) else None
            if side:
                alloc = state["a20_capital"] * 0.10
                if alloc > 10 and state["a20_capital"] >= alloc:
                    state["a20_capital"] -= alloc
                    state["a20_pos"][sym] = {"side": side, "entry": k[-1]["c"], "invested": alloc}
                    send_bale(f"🟢 A20 OPENED {side} | {sym} @ {k[-1]['c']}")

    # ── M40 (Pullback) ──
    for sym in SYMBOLS:
        k = fetch_klines(sym, 300)
        if len(k) < 200: continue
        closes = [c["c"] for c in k]
        ema200 = calc_ema(closes, 200)
        rsi = calc_rsi(closes, 14)
        atr = calc_atr(k, 14)
        if None in [ema200[-1], rsi[-1], atr[-2]]: continue
        
        pos = state["m40_pos"].get(sym)
        if pos:
            exit_ = (pos["side"]=="LONG" and (k[-1]["l"] <= pos["sl"] or k[-1]["h"] >= pos["tp"])) or \
                    (pos["side"]=="SHORT" and (k[-1]["h"] >= pos["sl"] or k[-1]["l"] <= pos["tp"]))
            if exit_:
                exit_p = pos["sl"] if (pos["side"]=="LONG" and k[-1]["l"]<=pos["sl"]) or (pos["side"]=="SHORT" and k[-1]["h"]>=pos["sl"]) else pos["tp"]
                pnl = pos["invested"] * ((exit_p-pos["entry"])/pos["entry"] if pos["side"]=="LONG" else (pos["entry"]-exit_p)/pos["entry"])
                state["m40_capital"] += pos["invested"] + pnl
                del state["m40_pos"][sym]
                send_bale(f"🔵 M40 CLOSED | {sym} | PnL: {pnl:+.2f}")
        elif len(state["m40_pos"]) < 3:
            side = None
            if closes[-1] > ema200[-1] and rsi[-1] < 40 and k[-1]["c"] > k[-1]["o"]: side = "LONG"
            elif closes[-1] < ema200[-1] and rsi[-1] > 60 and k[-1]["c"] < k[-1]["o"]: side = "SHORT"
            if side:
                alloc = state["m40_capital"] * 0.10
                if alloc > 10 and state["m40_capital"] >= alloc:
                    sl = k[-1]["c"] - 1.5*atr[-2] if side=="LONG" else k[-1]["c"] + 1.5*atr[-2]
                    tp = k[-1]["c"] + 3*atr[-2] if side=="LONG" else k[-1]["c"] - 3*atr[-2]
                    state["m40_capital"] -= alloc
                    state["m40_pos"][sym] = {"side": side, "entry": k[-1]["c"], "invested": alloc, "sl": sl, "tp": tp}
                    send_bale(f"🟢 M40 OPENED {side} | {sym} @ {k[-1]['c']}")

    # ── Equity ──
    state["total_equity"] = state["m31_capital"] + state["a20_capital"] + state["m40_capital"]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    
    if save_to_github(STATE_FILE, state, sha):
        roi = ((state["total_equity"] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
        print(f"✅ Equity: {state['total_equity']:.2f} USDT | ROI: {roi:+.2f}%")
        print(f"   M31: ${state['m31_capital']:.2f} | A20: ${state['a20_capital']:.2f} | M40: ${state['m40_capital']:.2f}")

if __name__ == "__main__":
    main()
