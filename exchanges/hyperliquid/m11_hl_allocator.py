import json, os, requests, time
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0
M31_PCT = 0.80  # D-313  # D-306: 100%
M35_PCT = 0.0  # D-306  # D-286
M40_PCT = 0.0  # D-306  # D-286
M41_PCT = 0.0  # D-306  # D-286 # تخصیص جدید برای Diversifier
M31_LEVERAGE = 3  # D-310
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005
STATE_FILE = "exchanges/hyperliquid/state/m11_hl_portfolio.json"
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]

def fetch_funding(symbol):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (4 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": now_ms}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return sum(float(rec["fundingRate"]) for rec in r.json())
    except: pass
    return 0.0

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f: return json.load(f)
    return {"signals": []}


def _log_close(state, sym, strat, pnl_val):
    if "history" not in state: state["history"] = []
    state["history"].append({"time": int(time.time() * 1000), "strat": strat, "symbol": sym, "pnl": round(pnl_val, 4)})


def load_active_weights(exchange):
    import json, os
    path = "exchanges/active_weights.json"
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
            return data.get(exchange, None)
    except:
        return None

def main():
    # RUNTIME-REGIME-CHECK (D-356)
    try:
        from research_lab.regime_detector import get_current_regime, should_activate_strategy
        _regime, _adx = get_current_regime()
        print(f"[REGIME] {_regime} (ADX={_adx:.2f})")
        globals()['_CURRENT_REGIME'] = _regime
    except Exception as _e:
        print(f"[REGIME] detection failed: {_e}")
        globals()['_CURRENT_REGIME'] = 'UNKNOWN'

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f: state = json.load(f)
        if "m41_capital" not in state: state["m41_capital"] = INITIAL_CAPITAL * M41_PCT
        if "m41_pos" not in state: state["m41_pos"] = {}
    else:
        state = {
            "total_capital": INITIAL_CAPITAL,
            "m31_capital": INITIAL_CAPITAL * M31_PCT, "m35_capital": INITIAL_CAPITAL * M35_PCT, 
            "m40_capital": INITIAL_CAPITAL * M40_PCT, "m41_capital": INITIAL_CAPITAL * M41_PCT,
            "m31_pos": {}, "m35_pos": {}, "m40_pos": {}, "m41_pos": {}, "history": []
        }

    # 1. M31 Accrual & Signals (بدون تغییر)
    for sym in list(state["m31_pos"].keys()):
        rate = fetch_funding(sym)
        earned = (state["m31_capital"] / len(SYMBOLS)) * rate * M31_LEVERAGE
        state["m31_capital"] += earned

    m31_sigs = load_json("exchanges/hyperliquid/state/m31_signals.json").get("signals", [])
    for sig in m31_sigs:
        if sig["action"] == "OPEN" and sig["symbol"] not in state["m31_pos"]:
            cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
            state["m31_capital"] -= cost
            state["m31_pos"][sig["symbol"]] = {"entry_time": sig["time"]}
        elif sig["action"] == "CLOSE" and sig["symbol"] in state["m31_pos"]:
            cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
            state["m31_capital"] -= cost
            del state["m31_pos"][sig["symbol"]]

    # 2. M35 Signals
    m35_sigs = load_json("exchanges/hyperliquid/state/m35_signals.json").get("signals", [])
    for sig in m35_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m35_pos"]:
            alloc = state["m35_capital"] * 0.20
            if alloc > 10 and state["m35_capital"] > alloc:
                state["m35_capital"] -= alloc
                state["m35_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "stop": sig["price"] - (3*sig["atr"]) if sig["action"]=="OPEN_LONG" else sig["price"] + (3*sig["atr"])}

    # 3. M40 Signals
    m40_sigs = load_json("exchanges/hyperliquid/state/m40_signals.json").get("signals", [])
    for sig in m40_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m40_pos"]:
            if len(state["m40_pos"]) < 3:
                alloc = state["m40_capital"] * 0.10
                if alloc > 10 and state["m40_capital"] > alloc:
                    state["m40_capital"] -= alloc
                    state["m40_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "tp": sig["tp"], "sl": sig["sl"]}

    # 4. M41 Signals (Diversifier)
    m41_sigs = load_json("exchanges/hyperliquid/state/m41_signals.json").get("signals", [])
    for sig in m41_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m41_pos"]:
            # برای M41 از ریسک 0.5% استفاده می‌کنیم (طبق پیش‌ثبت نام)
            alloc = state["m41_capital"] * 0.05 # 5% از سرمایه M41
            if alloc > 10 and state["m41_capital"] > alloc:
                state["m41_capital"] -= alloc
                state["m41_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "tp": sig["tp"], "sl": sig["sl"]}

    # 5. محاسبه سرمایه کل
    total_invested = sum(p["invested"] for pos in [state["m35_pos"], state["m40_pos"], state["m41_pos"]] for p in pos.values())
    total_equity = state["m31_capital"] + state["m35_capital"] + state["m40_capital"] + state["m41_capital"] + total_invested
    state["total_capital"] = total_equity
    
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2)
    print(f"Allocator Updated. Total Equity: ${state['total_capital']:.2f}")
    print(f"  M31: ${state['m31_capital']:.2f} | M35: ${state['m35_capital']:.2f} | M40: ${state['m40_capital']:.2f} | M41: ${state['m41_capital']:.2f}")

    _w = load_active_weights("hyperliquid")
    if _w:
        globals()["M31_ALLOC"] = _w.get("M31", globals().get("M31_ALLOC", 0.5))
        globals()["M35_ALLOC"] = _w.get("M35", globals().get("M35_ALLOC", 0.0))
        globals()["M40_ALLOC"] = _w.get("M40", globals().get("M40_ALLOC", 0.0))
        globals()["M41_ALLOC"] = _w.get("M41", globals().get("M41_ALLOC", 0.0))
        globals()["A20_ALLOC"] = _w.get("A20", globals().get("A20_ALLOC", 0.0))
        globals()["A8_ALLOC"] = _w.get("A8", globals().get("A8_ALLOC", 0.0))
        print(f"[CONFIG] Loaded weights from active_weights.json for hyperliquid")
if __name__ == "__main__": main()
