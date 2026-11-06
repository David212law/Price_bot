"""D-528: HL Shadow MLP — Multi-Layer Portfolio Paper tracker.

Tracks the D-528 portfolio in forward time:
  - M31_HL (62.34%): HL funding across 6 symbols
  - M31_EMA_BTC (19.99%): Aster BTC funding with momentum filter
  - M31_QUANTILE_ETH (8.81%): Aster ETH funding (base M31 approx)
  - M31_THRESHOLD_AVAX (6.32%): Aster AVAX funding (base M31 approx)
  - Cash (2.54%)

Compares against M31-only baseline (also tracked here).

Limitations (documented for honesty):
  - M31_QUANTILE/THRESHOLD: base M31 approximation (exact params unknown)
  - Keltner excluded (would need 5th component bot)
"""
import os as _os, sys as _sys
_project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _project_root not in _sys.path: _sys.path.insert(0, _project_root)

import json, os, requests, time
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0
M31_LEVERAGE = 0.45  # D-557: hedged (45% spot + 45% perp + 10% cash) migrated_D557
STATE_FILE = "exchanges/hyperliquid/state/m11_hl_shadow_mlp_portfolio.json"
HL_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
LOOKBACK = 6

# Component weights (from D-528)
COMPONENTS = [
    {"name": "M31_HL", "exchange": "hl", "weight": 0.6234,
     "strategy": "M31", "symbols": HL_SYMBOLS},
    {"name": "M31_EMA_BTC", "exchange": "aster", "weight": 0.1999,
     "strategy": "M31_EMA", "symbol": "BTCUSDT"},
    {"name": "M31_ETH", "exchange": "aster", "weight": 0.0881,
     "strategy": "M31", "symbol": "ETHUSDT"},
    {"name": "M31_AVAX", "exchange": "aster", "weight": 0.0632,
     "strategy": "M31", "symbol": "AVAXUSDT"},
]
CASH_WEIGHT = 0.0254


def fetch_hl_funding(symbol):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (4 * 3600 * 1000)
    try:
        r = requests.post("https://api.hyperliquid.xyz/info",
                          json={"type": "fundingHistory", "coin": symbol,
                                "startTime": start_ms, "endTime": now_ms}, timeout=15)
        if r.status_code == 200:
            return sum(float(x["fundingRate"]) for x in r.json())
    except Exception as e:
        print(f"[HL {symbol}] {e}")
    return 0.0


def fetch_aster_funding_history(symbol, n_periods=12):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (n_periods * 8 * 3600 * 1000) - (2 * 3600 * 1000)
    try:
        r = requests.get(f"https://fapi.asterdex.com/fapi/v1/fundingRate?symbol={symbol}&limit=20", timeout=15)
        if r.status_code == 200:
            data = r.json()
            return [{"t": int(x["fundingTime"]), "rate": float(x["fundingRate"])} for x in data]
    except Exception as e:
        print(f"[Aster {symbol}] {e}")
    return []


def compute_momentum(history, lookback=LOOKBACK):
    if len(history) < lookback * 2:
        return None
    recent = [r["rate"] for r in history[-lookback:]]
    older = [r["rate"] for r in history[:lookback]]
    return sum(recent) / len(recent), sum(older) / len(older), history[-1]["rate"]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "components": {
            c["name"]: {
                "equity": INITIAL_CAPITAL * c["weight"],
                "weight": c["weight"],
                "positions": {},
            } for c in COMPONENTS
        },
        "cash": INITIAL_CAPITAL * CASH_WEIGHT,
        "baseline_m31_only_equity": INITIAL_CAPITAL,
        "baseline_m31_positions": {s: {"in_pos": False} for s in HL_SYMBOLS},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def process_hl_component(comp_state, symbols):
    """M31 on HL: capture funding on all symbols."""
    income_total = 0.0
    for sym in symbols:
        rate = fetch_hl_funding(sym)
        if rate > 0:
            alloc = comp_state["equity"] / len(symbols)
            income = alloc * M31_LEVERAGE * rate
            comp_state["equity"] += income
            income_total += income
            print(f"  [HL/{sym}] funding +{income:.4f} ({rate*100:+.4f}%)")
    return income_total


def process_aster_m31_component(comp_state, symbol):
    """Base M31 on Aster: capture all positive funding."""
    history = fetch_aster_funding_history(symbol)
    if not history:
        return 0.0
    rate = history[-1]["rate"]
    if rate > 0:
        income = comp_state["equity"] * M31_LEVERAGE * rate
        comp_state["equity"] += income
        print(f"  [Aster/{symbol}] funding +{income:.4f} ({rate*100:+.4f}%)")
        return income
    return 0.0


def process_aster_m31_ema_component(comp_state, symbol):
    """M31_EMA: capture funding only when momentum positive."""
    history = fetch_aster_funding_history(symbol)
    if len(history) < LOOKBACK * 2:
        return 0.0
    mom = compute_momentum(history)
    if not mom:
        return 0.0
    recent_avg, older_avg, latest_rate = mom
    pos = comp_state["positions"].get(symbol, {"in_pos": False, "last_exit": 0})

    if pos["in_pos"]:
        if latest_rate < 0:
            pos["in_pos"] = False
            pos["last_exit"] = history[-1]["t"]
            print(f"  [Aster/{symbol}] EXIT (negative funding)")
        else:
            income = comp_state["equity"] * M31_LEVERAGE * latest_rate
            comp_state["equity"] += income
            print(f"  [Aster/{symbol}] HOLD +{income:.4f} (mom={recent_avg*100:+.4f}%>{older_avg*100:+.4f}%)")
            comp_state["positions"][symbol] = pos
            return income
    else:
        hours_since = (history[-1]["t"] - pos["last_exit"]) / 3600000
        if recent_avg > older_avg and latest_rate > 0 and hours_since >= 1:
            pos["in_pos"] = True
            print(f"  [Aster/{symbol}] ENTER (mom up)")
    comp_state["positions"][symbol] = pos
    return 0.0


def process_baseline_m31(state):
    """Track M31-only baseline on HL."""
    total = 0.0
    for sym in HL_SYMBOLS:
        rate = fetch_hl_funding(sym)
        if rate > 0:
            alloc = state["baseline_m31_only_equity"] / len(HL_SYMBOLS)
            income = alloc * M31_LEVERAGE * rate
            state["baseline_m31_only_equity"] += income
            total += income
    return total


def main():
    try:
        from research_lab.regime_detector import get_current_regime
        regime, adx = get_current_regime()
        print(f"[MLP] {regime} (ADX={adx:.2f})")
    except Exception:
        regime = "UNKNOWN"
        print("[MLP] regime detection failed")

    state = load_state()
    print(f"=== MLP Shadow ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")

    print("\n[Components]")
    for c in COMPONENTS:
        comp = state["components"][c["name"]]
        print(f"  {c['name']}: ${comp['equity']:.2f} ({c['weight']*100:.1f}%)")

    print("\n[Processing]")
    for c in COMPONENTS:
        comp = state["components"][c["name"]]
        if c["exchange"] == "hl":
            process_hl_component(comp, c["symbols"])
        elif c["strategy"] == "M31":
            process_aster_m31_component(comp, c["symbol"])
        elif c["strategy"] == "M31_EMA":
            process_aster_m31_ema_component(comp, c["symbol"])

    process_baseline_m31(state)

    # Compute totals
    portfolio_total = sum(c["equity"] for c in state["components"].values()) + state["cash"]
    m31_only_total = state["baseline_m31_only_equity"]

    state["portfolio_equity"] = portfolio_total
    state["baseline_m31_only_equity"] = m31_only_total
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    portfolio_ret = (portfolio_total / INITIAL_CAPITAL - 1) * 100
    m31_ret = (m31_only_total / INITIAL_CAPITAL - 1) * 100
    diff = portfolio_ret - m31_ret

    print(f"\n[SUMMARY]")
    print(f"  Portfolio:  ${portfolio_total:.2f} ({portfolio_ret:+.2f}%)")
    print(f"  M31-only:   ${m31_only_total:.2f} ({m31_ret:+.2f}%)")
    print(f"  Difference: {diff:+.2f}%")

    save_state(state)
    print(f"[SAVE] {STATE_FILE}")


if __name__ == "__main__":
    main()
