import json
import os
import base64
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (Hyperliquid) ───
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

STATE_FILE = "hyperliquid_paper_state.json"
INITIAL_CAPITAL = 10000.0
TAKER_FEE = 0.0005  # 0.05% Hyperliquid Taker
MAKER_FEE = 0.0002  # 0.02% Hyperliquid Maker
SYMBOLS = ["BTC", "ETH", "SOL"]
INTERVAL = "4h"
LOOKBACK = 100 # for indicators

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

def fetch_hyperliquid_data(symbol, limit=100):
    """Fetch data and convert strings to floats."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (limit * 4 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {
        "type": "candleSnapshot",
        "req": {"coin": symbol, "interval": INTERVAL, "startTime": start_ms, "endTime": now_ms}
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            raw_data = r.json()
            # ─── FIX: Convert strings to floats ───
            candles = []
            for c in raw_data:
                candles.append({
                    "t": int(c["t"]),
                    "o": float(c["o"]),
                    "h": float(c["h"]),
                    "l": float(c["l"]),
                    "c": float(c["c"]),
                    "v": float(c["v"])
                })
            return candles
    except: pass
    return []

# ─── Indicators (Pure Python) ───
def calc_bb_rsi_atr(candles, period=20):
    closes = [c["c"] for c in candles]
    if len(closes) < period + 1: return None, None, None
    
    # BB
    window = closes[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std = variance ** 0.5
    lower_bb = sma - (2 * std)
    
    # RSI (14)
    rsi_period = 14
    gains, losses = 0, 0
    for i in range(1, rsi_period + 1):
        change = closes[-i] - closes[-i-1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain = gains / rsi_period
    avg_loss = losses / rsi_period
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    
    # ATR (14)
    trs = []
    for i in range(1, 15):
        h, l, prev_c = candles[-i]["h"], candles[-i]["l"], candles[-i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    atr = sum(trs) / 14
    
    return lower_bb, rsi, atr

# ─── Main Engine ───
def main():
    print(f"=== Hyperliquid Paper Trading Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    
    state, sha = load_from_github(STATE_FILE)
    if not isinstance(state, dict) or "capital" not in state:
        state = {"capital": INITIAL_CAPITAL, "positions": [], "history": []}
        
    # 1. Manage Existing Positions
    for pos in state["positions"][:]:
        candles = fetch_hyperliquid_data(pos["symbol"], limit=10)
        if not candles: continue
        
        c = candles[-1] # Latest candle
        current_price = c["c"]
        
        exit_triggered = False
        exit_price = current_price
        reason = ""
        exit_fee = TAKER_FEE
        
        if c["l"] <= pos["sl"]:
            exit_triggered = True
            exit_price = pos["sl"]
            reason = "SL"
        elif c["h"] >= pos["tp"]:
            exit_triggered = True
            exit_price = pos["tp"]
            reason = "TP"
            exit_fee = MAKER_FEE
            
        if exit_triggered:
            exit_val = pos["units"] * exit_price * (1 - exit_fee)
            pnl = exit_val - pos["invested"]
            pnl_pct = (pnl / pos["invested"]) * 100
            state["capital"] += exit_val
            
            state["history"].append({
                "time": datetime.now(timezone.utc).isoformat(), "action": "CLOSE",
                "symbol": pos["symbol"], "exit_price": exit_price, "reason": reason,
                "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2)
            })
            state["positions"].remove(pos)
            
            emoji = "🟢" if pnl > 0 else "🔴"
            send_bale(f"{emoji} HL Paper CLOSED ({reason})\n{pos['symbol']}\nPnL: {pnl:+,.2f} USDT ({pnl_pct:+.2f}%)")
            print(f"[{pos['symbol']}] CLOSED ({reason}) | PnL: {pnl:+.2f} USDT")

    # 2. Find New Signals
    for sym in SYMBOLS:
        if any(p["symbol"] == sym for p in state["positions"]): continue
        
        candles = fetch_hyperliquid_data(sym, limit=LOOKBACK)
        if len(candles) < 50: continue
        
        lower_bb, rsi, atr = calc_bb_rsi_atr(candles)
        if lower_bb is None: continue
        
        current_candle = candles[-1]
        current_price = current_candle["c"]
        
        # M9 Strategy Logic
        if current_price <= lower_bb and rsi < 35:
            sl = current_price - (2 * atr)
            tp = current_price + (4 * atr)
            
            alloc_amt = state["capital"] * 0.05
            if alloc_amt > state["capital"] * 0.95: alloc_amt = state["capital"] * 0.95
            if alloc_amt < 10: continue
            
            entry_val = alloc_amt * (1 - TAKER_FEE)
            units = entry_val / current_price
            
            new_pos = {
                "symbol": sym, "entry_price": current_price, "units": units,
                "invested": alloc_amt, "sl": sl, "tp": tp,
                "entry_time": datetime.now(timezone.utc).isoformat()
            }
            state["positions"].append(new_pos)
            state["capital"] -= alloc_amt
            
            state["history"].append({
                "time": datetime.now(timezone.utc).isoformat(), "action": "OPEN",
                "symbol": sym, "entry_price": current_price, "invested": round(alloc_amt, 2)
            })
            
            send_bale(f"🔵 HL Paper OPENED\n{sym}\nPrice: {current_price:,.2f}\nSize: {alloc_amt:,.2f} USDT")
            print(f"[{sym}] OPENED at {current_price:,.2f} (Size: {alloc_amt:,.2f})")

    # 3. Save State
    if save_to_github(STATE_FILE, state, sha):
        total_equity = state["capital"] + sum(p["invested"] for p in state["positions"])
        print(f"\nState saved. Equity: {total_equity:,.2f} USDT | Open Pos: {len(state['positions'])}")
    else:
        print("\nFailed to save state.")

if __name__ == "__main__":
    main()
