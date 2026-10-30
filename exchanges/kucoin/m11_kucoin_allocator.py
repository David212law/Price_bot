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

# Allocations
M31_ALLOC = 0.50
M35_ALLOC = 0.20 # D-163: Reduced to Diversifier level

# M31 Config
M31_LEVERAGE = 6
SMA_PERIODS = 12
ENTRY_THRESHOLD = 0.00005
EXIT_THRESHOLD = 0.00001
COOLDOWN_HOURS = 24

TAKER_FEE = 0.0006
MAKER_FEE = 0.0002

SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"]
HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT: 
        print(f"[BALE] Skipped: {msg[:80]}")
        return
    url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except Exception as e: print(f"[BALE] Error: {e}")

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
        if r.status_code not in [200, 201]:
            print(f"[GitHub Save Error] Status: {r.status_code}")
            send_bale(f"⚠️ STATE SAVE FAILED for {filename}: {r.status_code}")
        return r.status_code in [200, 201]
    except Exception as e: 
        print(f"[GitHub Save Error] {e}")
        return False

def fetch_funding_rate(symbol):
    url = f"https://api-futures.kucoin.com/api/v1/funding-rate/{symbol}/current"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", {})
            return float(data.get("value", 0)), data.get("timepoint", 0)
    except: pass
    return 0.0, 0


def fetch_current_price(symbol):
    url = f"https://api-futures.kucoin.com/api/v1/ticker?symbol={symbol}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return float(r.json()["data"]["price"])
    except: pass
    return 0.0


def calc_ema_local(closes, period):
    ema = [None] * len(closes)
    if len(closes) < period: return ema
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

def fetch_klines_4h(symbol):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (50 * 4 * 60 * 60 * 1000) # 50 کندل برای warmup
    url = f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=240&from={start_ms}&to={now_ms}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            return [{"t": c[0], "o": c[1], "h": c[2], "l": c[3], "c": c[4]} for c in data]
    except: pass
    return []

def main():


    print(f"=== M11-KuCoin Paper Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    
    state, sha = load_from_github(STATE_FILE)
    if not isinstance(state, dict) or "m35_capital" not in state:
        state = {
            "total_equity": INITIAL_CAPITAL,
            "m31_capital": INITIAL_CAPITAL * M31_ALLOC,
            "m35_capital": INITIAL_CAPITAL * M35_ALLOC,
            "m31_pos": {},
            "history": []
        }

    # ── M31 Funding Logic ──
    for sym in SYMBOLS:
        rate, timepoint = fetch_funding_rate(sym)
        if timepoint == 0: continue
        
        st = state["m31_pos"].get(sym, {"in_pos": False, "hist": [], "last_exit": 0, "funding_earned": 0.0, "fees": 0.0})
        
        st["hist"].append(rate)
        if len(st["hist"]) > SMA_PERIODS: st["hist"].pop(0)
        avg_rate = sum(st["hist"]) / len(st["hist"])
        
        # فقط اگر رویداد فاندینگ جدیدی رخ داده باشد (بر اساس timepoint)
        last_processed = st.get("last_processed", 0)
        if timepoint > last_processed:
            st["last_processed"] = timepoint
            
            if st["in_pos"]:
                # بررسی Stop-Loss (D-160)
                current_price = fetch_current_price(sym)
                if current_price > 0 and current_price > st.get("entry_price", float('inf')) * 1.05:
                    cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    state["m31_capital"] -= cost
                    st["in_pos"] = False
                    st["last_exit"] = timepoint
                    send_bale(f"🛑 M31 KuCoin STOP-LOSS HIT | {sym} | Price Jumped 5%!")
                    continue

                earned = (state["m31_capital"] / len(SYMBOLS)) * M31_LEVERAGE * rate
                st["funding_earned"] += earned
                state["m31_capital"] += earned
                
                if avg_rate < EXIT_THRESHOLD:
                    cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    state["m31_capital"] -= cost
                    st["in_pos"] = False
                    st["last_exit"] = timepoint
                    send_bale(f"🔴 M31 KuCoin CLOSED | {sym} | Total Funding: ${st['funding_earned']:.2f}")
            else:
                time_since_exit = (timepoint - st["last_exit"]) / (3600 * 1000)
                if avg_rate > ENTRY_THRESHOLD and rate > 0 and time_since_exit >= COOLDOWN_HOURS:
                    cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
                    st["fees"] += cost
                    state["m31_capital"] -= cost
                    st["in_pos"] = True
                    st["entry_price"] = fetch_current_price(sym)
                    send_bale(f"🟢 M31 KuCoin OPENED | {sym} | Avg Rate: {avg_rate*100:.4f}% | Entry: {st['entry_price']}")
                    
        state["m31_pos"][sym] = st


    # ── M35 Logic (EMA Crossover) ──
    for sym in SYMBOLS:
        candles = fetch_klines_4h(sym)
        if len(candles) < 200: continue
        
        closes = [c["c"] for c in candles]
        ema_f = calc_ema_local(closes, 50)
        ema_s = calc_ema_local(closes, 200)
        
        if None in [ema_f[-1], ema_s[-1], ema_f[-2], ema_s[-2]]: continue
        
        # وضعیت پوزیشن M35
        if "m35_pos" not in state: state["m35_pos"] = {}
        pos = state["m35_pos"].get(sym)
        
        # بررسی خروج
        if pos:
            exit_triggered = False
            if pos["side"] == "LONG" and ema_f[-1] < ema_s[-1] and ema_f[-2] >= ema_s[-2]:
                exit_triggered = True
            elif pos["side"] == "SHORT" and ema_f[-1] > ema_s[-1] and ema_f[-2] <= ema_s[-2]:
                exit_triggered = True
                
            if exit_triggered:
                pnl_pct = (closes[-1] - pos["entry"]) / pos["entry"] if pos["side"] == "LONG" else (pos["entry"] - closes[-1]) / pos["entry"]
                pnl = pos["invested"] * pnl_pct
                state["m35_capital"] += (pos["invested"] + pnl)
                del state["m35_pos"][sym]
                send_bale(f"🟢 M35 KuCoin CLOSED | {sym} | PnL: {pnl:+.2f}")
                
        # بررسی ورود
        elif len(state.get("m35_pos", {})) < 3:
            side = None
            if ema_f[-1] > ema_s[-1] and ema_f[-2] <= ema_s[-2]: side = "LONG"
            elif ema_f[-1] < ema_s[-1] and ema_f[-2] >= ema_s[-2]: side = "SHORT"
            
            if side:
                alloc = state["m35_capital"] * 0.10 # 10% از سرمایه M35
                if alloc > 10 and state["m35_capital"] >= alloc:
                    state["m35_capital"] -= alloc
                    if "m35_pos" not in state: state["m35_pos"] = {}
                    state["m35_pos"][sym] = {"side": side, "entry": closes[-1], "invested": alloc}
                    send_bale(f"🟢 M35 KuCoin OPENED {side} | {sym} at {closes[-1]}")

    # ── Calculate Equity ──
    state["total_equity"] = state["m31_capital"] + state.get("m35_capital", 0)

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    
    if save_to_github(STATE_FILE, state, sha):
        roi = ((state["total_equity"] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
        print(f"✅ State saved. Equity: {state['total_equity']:.2f} USDT (ROI: {roi:+.2f}%)")

if __name__ == "__main__":
    main()
