import json, os, requests, time
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0
M31_PCT = 0.50
M35_PCT = 0.30
M40_PCT = 0.20
M31_LEVERAGE = 6
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

def main():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f: state = json.load(f)
    else:
        state = {
            "total_capital": INITIAL_CAPITAL,
            "m31_capital": INITIAL_CAPITAL * M31_PCT, "m35_capital": INITIAL_CAPITAL * M35_PCT, "m40_capital": INITIAL_CAPITAL * M40_PCT,
            "m31_pos": {}, "m35_pos": {}, "m40_pos": {}, "history": []
        }

    # 1. M31 Accrual
    for sym in list(state["m31_pos"].keys()):
        rate = fetch_funding(sym)
        earned = (state["m31_capital"] / len(SYMBOLS)) * rate * M31_LEVERAGE
        state["m31_capital"] += earned

    # 2. Process M31 Signals
    m31_sigs = json.load(open("exchanges/hyperliquid/state/m31_signals.json")).get("signals", []) if os.path.exists("exchanges/hyperliquid/state/m31_signals.json") else []
    for sig in m31_sigs:
        if sig["action"] == "OPEN" and sig["symbol"] not in state["m31_pos"]:
            cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
            state["m31_capital"] -= cost
            state["m31_pos"][sig["symbol"]] = {"entry_time": sig["time"]}
        elif sig["action"] == "CLOSE" and sig["symbol"] in state["m31_pos"]:
            cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
            state["m31_capital"] -= cost
            del state["m31_pos"][sig["symbol"]]

    # 3. Process M35 Signals
    m35_sigs = json.load(open("exchanges/hyperliquid/state/m35_signals.json")).get("signals", []) if os.path.exists("exchanges/hyperliquid/state/m35_signals.json") else []
    for sig in m35_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m35_pos"]:
            alloc = state["m35_capital"] * 0.20
            if alloc > 10 and state["m35_capital"] > alloc:
                state["m35_capital"] -= alloc
                state["m35_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "stop": sig["price"] - (3*sig["atr"]) if sig["action"]=="OPEN_LONG" else sig["price"] + (3*sig["atr"])}

    # 4. Process M40 Signals
    m40_sigs = json.load(open("exchanges/hyperliquid/state/m40_signals.json")).get("signals", []) if os.path.exists("exchanges/hyperliquid/state/m40_signals.json") else []
    for sig in m40_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m40_pos"]:
            if len(state["m40_pos"]) < 3:
                alloc = state["m40_capital"] * 0.10
                if alloc > 10 and state["m40_capital"] > alloc:
                    state["m40_capital"] -= alloc
                    state["m40_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "tp": sig["tp"], "sl": sig["sl"]}

    # Calculate Actual Total Equity (Free Cash + Invested Capital)
    m40_invested = sum(p["invested"] for p in state["m40_pos"].values())
    m35_invested = sum(p["invested"] for p in state["m35_pos"].values())
    total_equity = state["m31_capital"] + state["m35_capital"] + state["m40_capital"] + m40_invested + m35_invested

    state["total_capital"] = total_equity
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2)
    print(f"Allocator Updated. Total Equity: ${state['total_capital']:.2f}")
    print(f"  M31 Cash: ${state['m31_capital']:.2f} | Pos: {len(state['m31_pos'])}")
    print(f"  M35 Cash: ${state['m35_capital']:.2f} | Pos: {len(state['m35_pos'])}")
    print(f"  M40 Cash: ${state['m40_capital']:.2f} | Pos: {len(state['m40_pos'])}")

if __name__ == "__main__": main()
