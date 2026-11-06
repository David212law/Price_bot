"""D-569: Paper bot for testing researcher combos.

Creates 5 variants based on current researcher output:
  A: Researcher role-based (D-568)
  B: M31 alone (baseline)
  C: Static 90/10 (old)
  D: Flawed 45%+supporting (D-567)
  E: Cash only (null baseline)

Each has $1000 separate capital. Compares in Paper over time.
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


STATE_DIR = Path("exchanges/regime_combo_test/state")
CONFIGS = {
    "A_researcher": {"type": "researcher_role_based", "capital": 1000.0},
    "B_m31_alone": {"type": "static_m31", "capital": 1000.0},
    "C_static_90_10": {"type": "static_90_10", "capital": 1000.0},
    "D_flawed_45": {"type": "flawed_45", "capital": 1000.0},
    "E_cash_only": {"type": "cash_only", "capital": 1000.0},
}


def fetch_btc_prices():
    """Fetch recent BTC prices from HL."""
    end = int(datetime.now().timestamp())
    start = end - 30 * 86400
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "candleSnapshot",
               "req": {"coin": "BTC", "interval": "1d",
                       "startTime": start*1000, "endTime": end*1000}}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        prices = {}
        for c in data:
            ts = int(c.get("t", 0)) // 1000
            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            prices[d] = float(c.get("c", 0))
        return prices
    except: return {}


def detect_regime(prices):
    """Detect current regime from prices."""
    dates = sorted(prices.keys())
    if len(dates) < 25: return "UNKNOWN"
    rets = []
    for i in range(1, len(dates)):
        p0, p1 = prices[dates[i-1]], prices[dates[i]]
        if p0 > 0: rets.append((p1-p0)/p0)
    if len(rets) < 20: return "UNKNOWN"
    recent = rets[-20:]
    m = sum(recent)/len(recent)
    var = sum((r-m)**2 for r in recent)/len(recent)
    vol = var**0.5
    trend = sum(rets[-7:]) if len(rets) >= 7 else 0
    if vol > 0.045: return "CRISIS_VOL"
    if trend > 0.08: return "TREND_UP"
    if trend < -0.08: return "TREND_DOWN"
    if vol < 0.02: return "RANGE_LOW"
    if vol < 0.04: return "RANGE_MED"
    return "RANGE_HIGH"


def load_researcher_combos():
    p = Path("research_lab/logs/researcher_v3/role_combos.json")
    if not p.exists(): return {}
    try:
        data = json.loads(p.read_text())
        return data.get("combos", {})
    except: return {}


def get_combo_for_bot(bot_name, regime, researcher_combos):
    """Return combo dict based on bot type."""
    cfg = CONFIGS.get(bot_name, {})
    btype = cfg.get("type", "cash_only")
    
    if btype == "cash_only":
        return {"CASH": 1.0}
    if btype == "static_m31":
        return {"M31": 1.0}
    if btype == "static_90_10":
        return {"M31": 0.90, "Keltner": 0.10}
    if btype == "flawed_45":
        return {"M31": 0.45, "Keltner": 0.20, "Supporting": 0.20, "CASH": 0.15}
    if btype == "researcher_role_based":
        combo = researcher_combos.get(regime, {})
        components = combo.get("components", [])
        if not components:
            return {"CASH": 1.0}
        weights = {}
        for c in components:
            weights[c["strategy"]] = c["weight"]
        return weights
    return {"CASH": 1.0}


def load_state(bot_name):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    f = STATE_DIR / f"{bot_name}.json"
    if f.exists():
        try: return json.loads(f.read_text())
        except: pass
    return {
        "bot_name": bot_name,
        "initial_capital": CONFIGS[bot_name]["capital"],
        "equity": CONFIGS[bot_name]["capital"],
        "current_combo": {},
        "history": [],
        "last_run": None,
    }


def save_state(state):
    f = STATE_DIR / f"{state['bot_name']}.json"
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    f.write_text(json.dumps(state, indent=2))


def get_btc_return(prices):
    """Return of BTC over the last day (proxy for M31/Keltner)."""
    dates = sorted(prices.keys())
    if len(dates) < 2: return 0
    p0 = prices[dates[-2]]
    p1 = prices[dates[-1]]
    return (p1-p0)/p0 if p0 > 0 else 0


def main():
    print(f"=== Regime Combo Test — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")
    prices = fetch_btc_prices()
    if not prices:
        print("[ABORT] no prices")
        return
    current_price = prices[max(prices.keys())]
    regime = detect_regime(prices)
    print(f"BTC: {current_price:.0f} | Regime: {regime}")
    
    combos = load_researcher_combos()
    print(f"Researcher combos: {list(combos.keys())}")
    print()
    
    # Simulate daily return (proxy: BTC return for M31, small fraction for Keltner, 0 for cash)
    btc_ret = get_btc_return(prices)
    # M31 hedged = funding only (~0.15%/day proxy) - not BTC return
    m31_daily = 0.0015  # 0.15% per 4h = ~0.15%/day conservative
    keltner_daily = btc_ret * 0.5  # Keltner partial exposure
    
    print(f"{'Bot':<20} {'Regime':<15} {'Equity':>10} {'Combo'}")
    print("-" * 70)
    
    for bot_name in CONFIGS:
        state = load_state(bot_name)
        combo = get_combo_for_bot(bot_name, regime, combos)
        
        # Compute daily return based on combo
        daily_ret = 0
        for strat, weight in combo.items():
            if strat == "CASH":
                continue
            elif "M31" in strat:
                daily_ret += weight * m31_daily
            elif "Keltner" in strat or "KELTNER" in strat:
                daily_ret += weight * keltner_daily
            elif "Supporting" in strat:
                daily_ret += weight * btc_ret * 0.3
            else:
                daily_ret += weight * btc_ret * 0.5
        
        state["equity"] *= (1 + daily_ret)
        state["current_combo"] = combo
        state["history"].append({
            "time": datetime.now(timezone.utc).isoformat(),
            "regime": regime,
            "combo": combo,
            "daily_ret": round(daily_ret, 6),
            "equity": round(state["equity"], 2),
        })
        state["history"] = state["history"][-100:]
        save_state(state)
        
        combo_str = ", ".join(f"{k}@{v:.0%}" for k, v in combo.items())
        print(f"{bot_name:<20} {regime:<15} ${state['equity']:>9.2f} {combo_str[:40]}")
    
    print()
    print("Next run in 4h. Compare equity after 30/60/90 days.")


if __name__ == "__main__":
    main()
