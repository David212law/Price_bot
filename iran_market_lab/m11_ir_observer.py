import json
import os
import requests
import base64
from datetime import datetime, timezone

# ─── Configuration ───
INITIAL_CAPITAL_USDT = 10000.0
MAKER_FEE = 0.0010  # 0.10%
TAKER_FEE = 0.0013  # 0.13%
DATA_DIR = "data_tetri"
STATE_FILE = "iran_market_lab/m11_ir_state.json"
COOLDOWN_PERIOD = 6  # 6 * 4h = 24 hours wait after exit

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", 
    "DOGEUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"
]

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

# ─── Indicators ───
def calc_sma(closes, period):
    sma = [None] * len(closes)
    s = 0
    for i in range(len(closes)):
        s += closes[i]
        if i >= period: s -= closes[i - period]
        if i >= period - 1: sma[i] = s / period
    return sma

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

def calc_atr(candles, period=14):
    atr = [None] * len(candles)
    if len(candles) < period + 1: return atr
    trs = []
    for i in range(1, len(candles)):
        h, l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    first_atr = sum(trs[:period]) / period
    atr[period] = first_atr
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i - 1]) / period
    return atr

def calc_adx(candles, period=14):
    adx = [0.0] * len(candles)
    if len(candles) < period * 2: return adx
    trs, plus_dms, minus_dms = [0], [0], [0]
    for i in range(1, len(candles)):
        h, l, prev_h, prev_l, prev_c = candles[i]["h"], candles[i]["l"], candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        up = h - prev_h
        down = prev_l - l
        plus_dms.append(up if (up > down and up > 0) else 0)
        minus_dms.append(down if (down > up and down > 0) else 0)
    smooth_tr = sum(trs[1:period+1])
    smooth_plus = sum(plus_dms[1:period+1])
    smooth_minus = sum(minus_dms[1:period+1])
    dxs = []
    for i in range(period, len(candles)):
        if i > period:
            smooth_tr = smooth_tr - (smooth_tr / period) + trs[i]
            smooth_plus = smooth_plus - (smooth_plus / period) + plus_dms[i]
            smooth_minus = smooth_minus - (smooth_minus / period) + minus_dms[i]
        if smooth_tr == 0: dx = 0
        else:
            di_plus = 100 * smooth_plus / smooth_tr
            di_minus = 100 * smooth_minus / smooth_tr
            if (di_plus + di_minus) == 0: dx = 0
            else: dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
        dxs.append(dx)
    first_adx = sum(dxs[:period]) / period
    adx[period * 2 - 1] = first_adx
    for i in range(period * 2, len(candles)):
        adx[i] = (adx[i-1] * (period - 1) + dxs[i - period]) / period
    return adx

def calculate_total_equity(state, current_prices):
    total = state["capital"]
    for pos in state["positions"]:
        sym = pos["symbol"]
        if sym in current_prices:
            total += pos["units"] * current_prices[sym]
    return total

def main():
    print(f"=== M11-IR Observer (Global Strategies on Wallex USDT) ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    
    state, sha = load_from_github(STATE_FILE)
    if not isinstance(state, dict) or "capital" not in state:
        state = {
            "capital": INITIAL_CAPITAL_USDT,
            "positions": [],
            "history": [],
            "equity_curve": [INITIAL_CAPITAL_USDT],
            "cooldowns": {},
            "last_run": None
        }
        
    if "cooldowns" not in state: state["cooldowns"] = {}

    data = {}
    ind = {}
    current_prices = {}
    
    for sym in ASSETS:
        candles = load_candles(sym)
        if not candles: continue
        data[sym] = candles
        current_prices[sym] = candles[-1]["c"]
        
        closes = [x["c"] for x in candles]
        vols = [x["v"] for x in candles]
        
        sma20 = calc_sma(closes, 20)
        std20 = calc_std(closes, 20, sma20)
        ema20 = calc_ema(closes, 20)
        atr14 = calc_atr(candles, 14)
        vol_sma = calc_sma(vols, 20)
        
        upper_bb = [None] * len(closes)
        lower_bb = [None] * len(closes)
        upper_kc = [None] * len(closes)
        lower_kc = [None] * len(closes)
        squeeze = [False] * len(closes)
        
        for i in range(len(closes)):
            if sma20[i] and std20[i]:
                upper_bb[i] = sma20[i] + (2 * std20[i])
                lower_bb[i] = sma20[i] - (2 * std20[i])
            if ema20[i] and atr14[i]:
                upper_kc[i] = ema20[i] + (1.5 * atr14[i])
                lower_kc[i] = ema20[i] - (1.5 * atr14[i])
            if all(x is not None for x in [lower_bb[i], lower_kc[i], upper_bb[i], upper_kc[i]]):
                squeeze[i] = (lower_bb[i] > lower_kc[i]) and (upper_bb[i] < upper_kc[i])
                
        ind[sym] = {
            "rsi": calc_rsi(closes, 14),
            "atr": atr14,
            "adx": calc_adx(candles, 14),
            "upper_bb": upper_bb,
            "lower_bb": lower_bb,
            "squeeze": squeeze,
            "vol_sma": vol_sma
        }

    if "BTCUSDT" not in ind:
        print("BTCUSDT data missing. Aborting.")
        return

    total_equity = calculate_total_equity(state, current_prices)
    print(f"Starting equity: {total_equity:,.2f} USDT\n")

    btc_adx = ind["BTCUSDT"]["adx"][-1]
    
    if btc_adx > 25:
        w_m9, w_vsb, w_grid = 0.2, 0.3, 0.5
        regime = "TREND"
    elif btc_adx < 20:
        w_m9, w_vsb, w_grid = 0.5, 0.3, 0.2
        regime = "RANGE"
    else:
        w_m9, w_vsb, w_grid = 0.33, 0.33, 0.34
        regime = "NEUTRAL"

    print(f"Regime: {regime} (BTC ADX: {btc_adx:.2f})\n")

    # ─── 1. Manage Existing Positions ───
    for pos in state["positions"][:]:
        sym = pos["symbol"]
        if sym not in data: continue
        c = data[sym][-1]
        current_time = c["t"]
        
        exit_triggered = False
        exit_fee = TAKER_FEE
        exit_price = c["c"]
        
        if pos["strategy"] in ["M9", "VSB"]:
            if c["l"] <= pos["sl"]:
                exit_triggered = True
                exit_price = pos["sl"]
            elif c["h"] >= pos["tp"]:
                exit_triggered = True
                exit_price = pos["tp"]
                
        elif pos["strategy"] == "Grid":
            if c["l"] <= pos["initial"] * 0.90:
                exit_triggered = True
                exit_price = pos["initial"] * 0.90
            elif c["h"] >= pos["avg_entry"] * 1.02:
                exit_triggered = True
                exit_price = pos["avg_entry"] * 1.02
                exit_fee = MAKER_FEE
            else:
                if pos["levels"] == 1 and c["l"] <= pos["initial"] * 0.97:
                    pos["levels"] = 2
                    add_val = pos["initial_val"]
                    state["capital"] -= add_val
                    pos["invested"] += add_val
                    pos["units"] += (add_val * (1 - MAKER_FEE)) / (pos["initial"] * 0.97)
                    pos["avg_entry"] = pos["invested"] / pos["units"]
                    print(f"  {sym}: Grid Level 2 added at {pos['initial']*0.97:,.2f}")
                    send_bale(f"Grid Level 2: {sym} at {pos['initial']*0.97:,.2f}")
                elif pos["levels"] == 2 and c["l"] <= pos["initial"] * 0.94:
                    pos["levels"] = 3
                    add_val = pos["initial_val"]
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
                "strategy": pos["strategy"], "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2)
            })
            state["positions"].remove(pos)
            state["cooldowns"][sym] = current_time + (COOLDOWN_PERIOD * 4 * 3600 * 1000)
            
            emoji = "🟢" if pnl > 0 else "🔴"
            send_bale(f"{emoji} M11-IR CLOSED\n{sym} | {pos['strategy']}\nPnL: {pnl:+,.2f} USDT ({pnl_pct:+.2f}%)")
            print(f"  {sym}: CLOSED | {pos['strategy']} | PnL={pnl:+,.2f} USDT")

    # ─── 2. Open New Positions ───
    for sym in ASSETS:
        if sym not in data or sym not in ind: continue
        
        if any(p["symbol"] == sym for p in state["positions"]): continue
        
        c = data[sym][-1]
        current_time = c["t"]
        
        if current_time <= state["cooldowns"].get(sym, 0): continue

        if btc_adx > 25:
            strat = "VSB" if sym in ["ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"] else "M9"
        elif btc_adx < 20:
            strat = "Grid" if sym in ["BTCUSDT", "BNBUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"] else "M9"
        else:
            strat = "M9"

        if strat == "M9": alloc_pct = w_m9 / 5
        elif strat == "VSB": alloc_pct = w_vsb / 5
        else: alloc_pct = w_grid / 5

        alloc_amt = total_equity * alloc_pct
        if alloc_amt > state["capital"] * 0.95: alloc_amt = state["capital"] * 0.95
        if alloc_amt < 10: continue

        entry_triggered = False
        entry_price = c["c"]
        fee = TAKER_FEE
        sl, tp = 0, 0

        if strat == "M9":
            lower_bb = ind[sym]["lower_bb"][-1]
            rsi_val = ind[sym]["rsi"][-1]
            atr_val = ind[sym]["atr"][-1]
            if lower_bb and rsi_val and atr_val:
                if c["c"] <= lower_bb and rsi_val < 35:
                    entry_triggered = True
                    sl = entry_price - (2 * atr_val)
                    tp = entry_price + (4 * atr_val)

        elif strat == "VSB":
            squeeze = ind[sym]["squeeze"][-1]
            vol_sma = ind[sym]["vol_sma"][-1]
            upper_bb = ind[sym]["upper_bb"][-1]
            atr_val = ind[sym]["atr"][-1]
            if squeeze and vol_sma and upper_bb and atr_val:
                if c["c"] > upper_bb and c["v"] > (1.2 * vol_sma):
                    entry_triggered = True
                    sl = entry_price - (2 * atr_val)
                    tp = entry_price + (4 * atr_val)

        elif strat == "Grid":
            lower_bb = ind[sym]["lower_bb"][-1]
            rsi_val = ind[sym]["rsi"][-1]
            if lower_bb and rsi_val:
                if c["c"] <= lower_bb and rsi_val < 35:
                    entry_triggered = True
                    fee = MAKER_FEE

        if entry_triggered:
            state["capital"] -= alloc_amt
            units = (alloc_amt * (1 - fee)) / entry_price
            
            new_pos = {
                "symbol": sym, "strategy": strat,
                "entry_price": entry_price, "entry_time": current_time,
                "units": units, "invested": alloc_amt,
                "sl": sl, "tp": tp,
                "initial": entry_price, "avg_entry": entry_price,
                "levels": 1, "initial_val": alloc_amt
            }
            state["positions"].append(new_pos)
            state["history"].append({
                "time": current_time, "action": "OPEN", "symbol": sym,
                "strategy": strat, "price": entry_price, "invested": round(alloc_amt, 2)
            })
            
            send_bale(f"🔵 M11-IR OPENED\n{sym} | {strat}\nPrice: {entry_price:,.2f}\nSize: {alloc_amt:,.2f} USDT")
            print(f"  {sym}: OPENED {strat} at {entry_price:,.2f} ({alloc_amt:,.2f} USDT)")

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
