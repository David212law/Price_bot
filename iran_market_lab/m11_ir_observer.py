import json
import os
import requests
import base64
from datetime import datetime, timezone

# ─── Configuration (Grid-Only Mode) ───
INITIAL_CAPITAL_USDT = 10000.0
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"
STATE_FILE = "iran_market_lab/m11_ir_state.json"

# Only Grid-approved assets
ASSETS = ["BTCUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"]
ALLOC_PCT_PER_TRADE = 0.05 # 5% of equity per Grid basket

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT:
        print(f"[BALE] Skipped: {msg[:80]}")
        return
    try:
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except Exception as e:
        print(f"[BALE] Error: {e}")

def load_from_github(filename):
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{filename}"
        r = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return json.loads(base64.b64decode(data["content"]).decode("utf-8")), data["sha"]
        elif r.status_code != 404:
            print(f"[GitHub Load Error] Status: {r.status_code} | Response: {r.text}")
        return {}, None
    except Exception as e:
        print(f"[GitHub Load Exception] {e}")
        return {}, None

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
            print(f"[GitHub Save Error] Status: {r.status_code} | Response: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[GitHub Save Exception] {e}")
        return False

def load_candles(symbol):
    path = f"{DATA_DIR}/{symbol}_4h.json"
    if not os.path.exists(path): return None
    with open(path, 'r') as f: return json.load(f)

# ─── Indicators for Grid ───
def calc_sma(closes, period):
    sma = [None] * len(closes)
    s = 0
    for i in range(len(closes)):
        s += closes[i]
        if i >= period: s -= closes[i - period]
        if i >= period - 1: sma[i] = s / period
    return sma

def calc_std(closes, period, sma):
    std = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        mean = sma[i]
        variance = sum((x - mean) ** 2 for x in closes[i - period + 1:i + 1]) / period
        std[i] = variance ** 0.5
    return std

def calc_rsi(closes, period=14):
    rsi = [None] * len(closes)
    if len(closes) < period + 1: return rsi
    gains, losses = 0, 0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    rsi[period] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi[i] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    return rsi

def calculate_total_equity(state, current_prices):
    total = state["capital"]
    for pos in state["positions"]:
        sym = pos["symbol"]
        if sym in current_prices:
            total += pos["units"] * current_prices[sym]
    return total

def main():
    print(f"=== M11-IR Observer (Grid-Only Mode) ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    
    state, sha = load_from_github(STATE_FILE)
    if not isinstance(state, dict) or "capital" not in state:
        state = {
            "capital": INITIAL_CAPITAL_USDT,
            "positions": [],
            "history": [],
            "equity_curve": [INITIAL_CAPITAL_USDT],
            "last_run": None
        }

    data = {}
    ind = {}
    current_prices = {}
    
    for sym in ASSETS:
        candles = load_candles(sym)
        if not candles: continue
        data[sym] = candles
        current_prices[sym] = candles[-1]["c"]
        
        closes = [x["c"] for x in candles]
        sma20 = calc_sma(closes, 20)
        std20 = calc_std(closes, 20, sma20)
        
        lower_bb = [None] * len(closes)
        for i in range(len(closes)):
            if sma20[i] and std20[i]:
                lower_bb[i] = sma20[i] - (2 * std20[i])
                
        ind[sym] = {
            "rsi": calc_rsi(closes, 14),
            "lower_bb": lower_bb
        }

    total_equity = calculate_total_equity(state, current_prices)
    print(f"Starting equity: {total_equity:,.2f} USDT\n")

    # ─── 1. Manage Existing Grid Positions ───
    for pos in state["positions"][:]:
        sym = pos["symbol"]
        if sym not in data: continue
        c = data[sym][-1]
        current_time = c["t"]
        
        exit_triggered = False
        exit_fee = TAKER_FEE
        exit_price = c["c"]
        
        # Check SL (Low) BEFORE TP (High)
        if c["l"] <= pos["initial"] * 0.90:
            exit_triggered = True
            exit_price = pos["initial"] * 0.90
        elif c["h"] >= pos["avg_entry"] * 1.02:
            exit_triggered = True
            exit_price = pos["avg_entry"] * 1.02
            exit_fee = MAKER_FEE
        else:
            # DCA Levels (Maker)
            if pos["levels"] == 1 and c["l"] <= pos["initial"] * 0.97:
                add_val = pos["initial_val"]
                if state["capital"] >= add_val:
                    pos["levels"] = 2
                    state["capital"] -= add_val
                    pos["invested"] += add_val
                    pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.97)
                    pos["avg_entry"] = pos["invested"] / pos["units"]
                    print(f"  {sym}: Grid Level 2 added at {pos['initial']*0.97:,.2f}")
                    send_bale(f"Grid Level 2: {sym} at {pos['initial']*0.97:,.2f}")
            elif pos["levels"] == 2 and c["l"] <= pos["initial"] * 0.94:
                add_val = pos["initial_val"]
                if state["capital"] >= add_val:
                    pos["levels"] = 3
                    state["capital"] -= add_val
                    pos["invested"] += add_val
                    pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.94)
                    pos["avg_entry"] = pos["invested"] / pos["units"]
                    print(f"  {sym}: Grid Level 3 added at {pos['initial']*0.94:,.2f}")
                    send_bale(f"Grid Level 3: {sym} at {pos['initial']*0.94:,.2f}")

        if exit_triggered:
            exit_val = pos["units"] * exit_price * (1 - exit_fee)
            state["capital"] += exit_val
            pnl = exit_val - pos["invested"]
            pnl_pct = (pnl / pos["invested"]) * 100
            
            state["history"].append({
                "time": current_time, "action": "CLOSE", "symbol": sym,
                "strategy": "Grid", "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2)
            })
            state["positions"].remove(pos)
            
            emoji = "🟢" if pnl > 0 else "🔴"
            send_bale(f"{emoji} M11-IR CLOSED\n{sym} | Grid\nPnL: {pnl:+,.2f} USDT ({pnl_pct:+.2f}%)")
            print(f"  {sym}: CLOSED | Grid | PnL={pnl:+,.2f} USDT")

    # ─── 2. Open New Grid Positions ───
    for sym in ASSETS:
        if sym not in data or sym not in ind: continue
        
        if any(p["symbol"] == sym for p in state["positions"]): continue
        
        c = data[sym][-1]
        current_time = c["t"]
        
        alloc_amt = total_equity * ALLOC_PCT_PER_TRADE
        if alloc_amt > state["capital"] * 0.95: alloc_amt = state["capital"] * 0.95
        if alloc_amt < 10: continue

        entry_triggered = False
        entry_price = c["c"]

        lower_bb = ind[sym]["lower_bb"][-1]
        rsi_val = ind[sym]["rsi"][-1]
        if lower_bb and rsi_val:
            if c["c"] <= lower_bb and rsi_val < 35:
                entry_triggered = True

        if entry_triggered:
            state["capital"] -= alloc_amt
            units = (alloc_amt * (1 - MAKER_FEE)) / entry_price
            
            new_pos = {
                "symbol": sym, "strategy": "Grid",
                "entry_price": entry_price, "entry_time": current_time,
                "units": units, "invested": alloc_amt,
                "initial": entry_price, "avg_entry": entry_price,
                "levels": 1, "initial_val": alloc_amt
            }
            state["positions"].append(new_pos)
            state["history"].append({
                "time": current_time, "action": "OPEN", "symbol": sym,
                "strategy": "Grid", "price": entry_price, "invested": round(alloc_amt, 2)
            })
            
            send_bale(f"🔵 M11-IR OPENED (Grid)\n{sym}\nPrice: {entry_price:,.2f}\nSize: {alloc_amt:,.2f} USDT")
            print(f"  {sym}: OPENED Grid at {entry_price:,.2f} ({alloc_amt:,.2f} USDT)")

    # ─── 3. Finalize and Save State ───
    total_equity = calculate_total_equity(state, current_prices)
    state["equity_curve"].append(round(total_equity, 2))
    if len(state["equity_curve"]) > 500:
        state["equity_curve"] = state["equity_curve"][-500:]
    
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    
    if save_to_github(STATE_FILE, state, sha):
        print("\nState saved to GitHub successfully.")
    else:
        print("\nFailed to save state to GitHub.")

    roi = ((total_equity - INITIAL_CAPITAL_USDT) / INITIAL_CAPITAL_USDT) * 100
    print(f"\n=== Summary ===")
    print(f"  Equity: {total_equity:,.2f} USDT (ROI: {roi:+.2f}%)")
    print(f"  Cash: {state['capital']:,.2f} USDT")
    print(f"  Open positions: {len(state['positions'])}")

if __name__ == "__main__":
    main()
