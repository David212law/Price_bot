import json, os, requests, time

SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
STATE_FILE = "exchanges/hyperliquid/state/m31_generator_state.json"
SIGNAL_FILE = "exchanges/hyperliquid/state/m31_signals.json"
M31_SMA_PERIODS = 12
M31_ENTRY_THRESHOLD = 0.00001   # D-390: reduced from 5 bps to 1 bps for Paper data collection
M31_EXIT_THRESHOLD = 0.000005   # D-390: reduced from 1 bps to 0.5 bps
M31_COOLDOWN = 3

def fetch_funding(symbol):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (50 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": now_ms}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return [{"t": int(rec["time"]), "rate": float(rec["fundingRate"])} for rec in r.json()]
    except: pass
    return []

def main():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f: state = json.load(f)
    else:
        state = {sym: {"in_pos": False, "last_exit": 0, "hist": [], "last_processed_time": 0} for sym in SYMBOLS}

    signals = []
    for sym in SYMBOLS:
        recs = fetch_funding(sym)
        if not recs: continue
        st = state[sym]
        new_recs = [r for r in recs if r["t"] > st["last_processed_time"]]
        
        for rec in new_recs:
            rate = rec["rate"]
            st["hist"].append(rate)
            if len(st["hist"]) > M31_SMA_PERIODS: st["hist"].pop(0)
            avg_rate = sum(st["hist"]) / len(st["hist"])
            
            if st["in_pos"]:
                if avg_rate < M31_EXIT_THRESHOLD:
                    st["in_pos"] = False
                    st["last_exit"] = rec["t"]
                    signals.append({"symbol": sym, "action": "CLOSE", "time": rec["t"]})
            else:
                time_since_exit = (rec["t"] - st["last_exit"]) / (3600 * 1000)
                if avg_rate > M31_ENTRY_THRESHOLD and rate > 0 and time_since_exit >= M31_COOLDOWN:
                    st["in_pos"] = True
                    signals.append({"symbol": sym, "action": "OPEN", "time": rec["t"]})
                    
        if new_recs:
            st["last_processed_time"] = new_recs[-1]["t"]

    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2)
    with open(SIGNAL_FILE, 'w') as f: json.dump({"signals": signals}, f, indent=2)
    print(f"M31 Generator: {len(signals)} signals generated.")

if __name__ == "__main__": main()
