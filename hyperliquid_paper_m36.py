import json
import os
import base64
import requests
import time
from datetime import datetime, timezone

# ─── Configuration ───
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

STATE_FILE = "hyperliquid_m36_state.json"
INITIAL_CAPITAL = 10000.0

TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

M31_CAPITAL_PCT = 0.60
M31_LEVERAGE = 6
M31_SMA_PERIODS = 12
M31_ENTRY_THRESHOLD = 0.00005
M31_EXIT_THRESHOLD = 0.00001
M31_COOLDOWN = 3
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]

M35_CAPITAL_PCT = 0.40
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14
ATR_MULTIPLIER = 3.0
M35_RISK_PER_TRADE = 0.20

# ─── Helpers ───
def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT: return
    url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except: pass

def load_from_github(filename):
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{filename}"
        r = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return json.loads(base64.b64decode(data["content"]).decode("utf-8")), data["sha"]
        return {}, None
    except: return {}, None

def save_to_github(filename, data, sha=None):
    try:
        if not sha: _, sha = load_from_github(filename)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{filename}"
        payload = {"message": f"Update {filename}", "content": content_b64}
        if sha: payload["sha"] = sha
        r = requests.put(url, headers={"Authorization": f"token {GH_TOKEN}"}, json=payload, timeout=15)
        return r.status_code in [200, 201]
    except: return False

def fetch_ohlcv(symbol, interval="1d", limit=300):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (limit * 24 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": interval, "startTime": start_ms, "endTime": now_ms}}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            raw = r.json()
            return [{"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"]), "v": float(c["v"])} for c in raw]
    except: pass
    return []

def fetch_funding(symbol, limit=50):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (limit * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": now_ms}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return [{"t": int(rec["time"]), "rate": float(rec["fundingRate"])} for rec in r.json()]
    except: pass
    return []

def calc_ema(closes, period):
    ema = [None] * len(closes)
    if len(closes) < period: return ema
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

def calc_atr(candles, period=14):
    atr = [None] * len(candles)
    if len(candles) < period + 1: return atr
    trs = [0] * len(candles)
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs[i] = max(h - l, abs(h - prev_c), abs(l - prev_c))
    first_atr = sum(trs[1:period+1]) / period
    atr[period] = first_atr
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i]) / period
    return atr

# ─── Main Engine ───
def main():
    print(f"=== M36 Hyperliquid Paper Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}) ===")
    
    state, sha = load_from_github(STATE_FILE)
    
    # FIX D-114: Start with clean separate capital buckets
    if not isinstance(state, dict) or "m31_capital" not in state:
        state = {
            "m31_capital": INITIAL_CAPITAL * M31_CAPITAL_PCT,
            "m35_capital": INITIAL_CAPITAL * M35_CAPITAL_PCT,
            "total_capital": INITIAL_CAPITAL,
            "m31": {sym: {"in_pos": False, "funding": 0.0, "fees": 0.0, "last_exit": 0, "hist": [], "last_processed_time": 0} for sym in SYMBOLS},
            "m35": {},
            "history": []
        }

    # ─── 1. M31 Logic (Funding Arb) ───
    for sym in SYMBOLS:
        funding_records = fetch_funding(sym, limit=24)
        if not funding_records: continue
        
        st = state["m31"][sym]
        last_processed = st.get("last_processed_time", 0)
        new_records = [r for r in funding_records if r["t"] > last_processed]
        
        for rec in new_records:
            rate = rec["rate"]
            st["hist"].append(rate)
            if len(st["hist"]) > M31_SMA_PERIODS: st["hist"].pop(0)
            avg_rate = sum(st["hist"]) / len(st["hist"])
            
            if st["in_pos"]:
                # FIX D-115: Unconditional funding addition (negative rates subtract)
                earned = (state["m31_capital"] / len(SYMBOLS)) * rate * M31_LEVERAGE
                st["funding"] += earned
                state["m31_capital"] += earned
                
                if avg_rate < M31_EXIT_THRESHOLD:
                    cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    state["m31_capital"] -= cost
                    st["in_pos"] = False
                    st["last_exit"] = rec["t"]
                    send_bale(f"🟡 M31 CLOSED\n{sym} | Funding: {st['funding']:.2f}")
            else:
                time_since_exit = (rec["t"] - st["last_exit"]) / (3600 * 1000)
                if avg_rate > M31_ENTRY_THRESHOLD and rate > 0 and time_since_exit >= M31_COOLDOWN:
                    cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    state["m31_capital"] -= cost
                    st["in_pos"] = True
                    send_bale(f"🟢 M31 OPENED\n{sym} | Avg Rate: {avg_rate*100:.4f}%")
                    
        if new_records:
            st["last_processed_time"] = new_records[-1]["t"]

    # ─── 2. M35 Logic (EMA 1D) ───
    for sym in SYMBOLS:
        side = None # FIX D-116: Reset side for every symbol loop
        
        candles = fetch_ohlcv(sym, "1d", 300)
        if len(candles) < EMA_SLOW + 2: continue
        
        closes = [c["c"] for c in candles]
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        atr = calc_atr(candles, ATR_PERIOD)
        
        idx = len(candles) - 2 
        prev_idx = idx - 1
        
        ef, es = ema_fast[idx], ema_slow[idx]
        ef_prev, es_prev = ema_fast[prev_idx], ema_slow[prev_idx]
        atr_val = atr[idx]
        current_price = candles[idx]["c"]
        
        if None in [ef, es, ef_prev, es_prev, atr_val]: continue
        
        pos = state["m35"].get(sym)
        
        if pos:
            exit_triggered = False
            exit_price = current_price
            
            if pos["side"] == "LONG":
                new_stop = candles[idx]["h"] - (ATR_MULTIPLIER * atr_val)
                if new_stop > pos["stop"]: pos["stop"] = new_stop
                if candles[idx]["l"] <= pos["stop"]:
                    exit_triggered, exit_price = True, pos["stop"]
                elif ef < es:
                    exit_triggered = True
            elif pos["side"] == "SHORT":
                new_stop = candles[idx]["l"] + (ATR_MULTIPLIER * atr_val)
                if new_stop < pos["stop"]: pos["stop"] = new_stop
                if candles[idx]["h"] >= pos["stop"]:
                    exit_triggered, exit_price = True, pos["stop"]
                elif ef > es:
                    exit_triggered = True
                    
            if exit_triggered:
                if pos["side"] == "LONG":
                    ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                else:
                    ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
                
                # FIX D-117: Return principal + PnL to M35 capital
                pnl = pos["invested"] * ret
                state["m35_capital"] += pos["invested"] + pnl
                
                state["history"].append({"time": datetime.now(timezone.utc).isoformat(), "strat": "M35", "symbol": sym, "side": pos["side"], "ret": ret, "pnl": pnl})
                del state["m35"][sym]
                send_bale(f"🔵 M35 CLOSED ({pos['side']})\n{sym} | PnL: {pnl:+.2f} USDT ({ret*100:+.2f}%)")
                
        # Entry
        elif ef > es and ef_prev <= es_prev:
            side = "LONG"
        elif ef < es and ef_prev >= es_prev:
            side = "SHORT"
            
        if side and sym not in state["m35"]:
            alloc_amt = state["m35_capital"] * M35_RISK_PER_TRADE
            if alloc_amt > 10:
                state["m35_capital"] -= alloc_amt # Deduct principal on entry
                stop = current_price - (ATR_MULTIPLIER * atr_val) if side == "LONG" else current_price + (ATR_MULTIPLIER * atr_val)
                state["m35"][sym] = {"side": side, "entry_price": current_price, "invested": alloc_amt, "stop": stop}
                send_bale(f"🔵 M35 OPENED ({side})\n{sym} at {current_price:,.2f}\nSize: {alloc_amt:.2f} USDT")

    # ─── 3. Final State Update ───
    state["total_capital"] = state["m31_capital"] + state["m35_capital"]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    
    if save_to_github(STATE_FILE, state, sha):
        print(f"✅ State saved. Equity: {state['total_capital']:.2f} USDT")
        print(f"   M31 Capital: {state['m31_capital']:.2f} | M35 Capital: {state['m35_capital']:.2f}")

if __name__ == "__main__":
    main()
