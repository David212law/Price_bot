"""D-522: HL Shadow MOM — M31_MOMENTUM strategy in Paper.

Same as M31 but with momentum filter:
  - Fetch funding history (12 periods = 96 hours)
  - Compute momentum (recent 6 vs older 6)
  - Enter only when momentum is positive AND funding is positive
  - Exit when funding goes negative
"""
import os as _os, sys as _sys
_project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _project_root not in _sys.path: _sys.path.insert(0, _project_root)

import json, os, requests, time
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0
M31_PCT = 0.80
M31_LEVERAGE = 3
KELTNER_PCT = 0.0
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005
STATE_FILE = "exchanges/hyperliquid/state/m11_hl_shadow_mom_portfolio.json"
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
LOOKBACK = 6  # periods for momentum (6 * 8h = 48h)


def fetch_funding_history(symbol, n_periods=12):
    """Fetch last N funding periods for momentum calc."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (n_periods * 8 * 3600 * 1000) - (2 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": now_ms}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return [{"t": int(x["time"]), "rate": float(x["fundingRate"])} for x in data]
    except Exception as e:
        print(f"[FETCH] {symbol}: {e}")
    return []


def compute_momentum(history, lookback=LOOKBACK):
    """Return (recent_avg, older_avg, latest_rate) or None if not enough data."""
    if len(history) < lookback * 2:
        return None
    recent = [r["rate"] for r in history[-lookback:]]
    older = [r["rate"] for r in history[:lookback]]
    return sum(recent)/len(recent), sum(older)/len(older), history[-1]["rate"]


def load_active_weights(exchange, regime=None):
    path = "exchanges/active_weights_shadow_hl_mom.json"
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        ex_data = data.get(exchange, {})
        if not ex_data:
            return None
        regime_keys = {"TREND","RANGE","NEUTRAL","UNKNOWN"}
        if any(k in regime_keys for k in ex_data.keys()):
            if regime and regime in ex_data:
                return ex_data[regime]
            for fb in ("UNKNOWN","TREND"):
                if fb in ex_data:
                    return ex_data[fb]
            return None
        return ex_data
    except Exception as _e:
        print(f"[SHADOW-HL-MOM-W] load error: {_e}")
        return None


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "m31_capital": INITIAL_CAPITAL * M31_PCT,
        "cash_capital": INITIAL_CAPITAL * (1 - M31_PCT),
        "m31_pos": {s: {"in_pos": False, "last_exit": 0, "history": []} for s in SYMBOLS},
        "history": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    # Regime detection
    try:
        from research_lab.regime_detector import get_current_regime
        regime, adx = get_current_regime()
        print(f"[SHADOW-HL-MOM] {regime} (ADX={adx:.2f})")
    except Exception as e:
        print(f"[SHADOW-HL-MOM] regime detection failed: {e}")
        regime = "UNKNOWN"

    # Load weights
    _w = load_active_weights("hyperliquid", regime=regime)
    m31_alloc = M31_PCT
    if _w:
        m31_alloc = _w.get("M31", M31_PCT)
        print(f"[CONFIG] M31={m31_alloc*100:.0f}%")

    state = load_state()
    print(f"=== M11-HL Shadow MOM ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    print(f"  Started with: ${state['m31_capital']:.2f} M31 + ${state['cash_capital']:.2f} cash")

    # Process each symbol
    total_funding = 0.0
    entered = exited = idle = 0

    for sym in SYMBOLS:
        history = fetch_funding_history(sym, n_periods=LOOKBACK*2)
        if len(history) < LOOKBACK * 2:
            print(f"[{sym}] insufficient history ({len(history)} periods)")
            idle += 1
            continue

        mom = compute_momentum(history, LOOKBACK)
        if mom is None:
            idle += 1
            continue

        recent_avg, older_avg, latest_rate = mom
        pos = state["m31_pos"].setdefault(sym, {"in_pos": False, "last_exit": 0, "history": []})
        pos["history"] = [r["rate"] for r in history[-LOOKBACK*2:]]

        momentum_up = recent_avg > older_avg
        funding_positive = latest_rate > 0

        if pos["in_pos"]:
            # Exit if funding turns negative
            if latest_rate < 0:
                pos["in_pos"] = False
                pos["last_exit"] = history[-1]["t"]
                exited += 1
                print(f"[{sym}] EXIT (funding negative: {latest_rate*100:+.4f}%)")
            else:
                # Capture funding
                alloc = state["m31_capital"] / len(SYMBOLS)
                income = alloc * M31_LEVERAGE * latest_rate
                state["m31_capital"] += income
                total_funding += income
                print(f"[{sym}] HOLD funding: +{income:.4f} USDT ({latest_rate*100:+.4f}%) | "
                      f"mom_recent={recent_avg*100:+.4f}% older={older_avg*100:+.4f}%")
        else:
            # Enter if momentum UP and funding positive
            hours_since_exit = (history[-1]["t"] - pos["last_exit"]) / 3600000
            if momentum_up and funding_positive and hours_since_exit >= 1:
                pos["in_pos"] = True
                entered += 1
                # Pay entry fee (0.02% maker)
                entry_fee = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * M31_LEVERAGE
                state["m31_capital"] -= entry_fee
                print(f"[{sym}] ENTER (mom up: {recent_avg*100:+.4f}% > {older_avg*100:+.4f}%) "
                      f"fee={entry_fee:.4f}")

    # Compute equity
    total_equity = state["m31_capital"] + state["cash_capital"]
    state["total_capital"] = total_equity
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    print(f"\n[SUMMARY] Entered={entered} Exited={exited} Idle={idle}")
    print(f"[EQUITY] ${total_equity:.2f} (M31: ${state['m31_capital']:.2f} + Cash: ${state['cash_capital']:.2f})")
    print(f"[FUNDING] This run: +{total_funding:.4f} USDT")

    save_state(state)
    print(f"[SAVE] {STATE_FILE}")


if __name__ == "__main__":
    main()
