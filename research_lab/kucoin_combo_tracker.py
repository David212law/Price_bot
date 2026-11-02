"""D-485: Shadow tracker for kucoin/NEUTRAL combo — actual vs hypothetical."""
import sys, os, json
from datetime import datetime, timezone
sys.path.insert(0, '.')

STATE_FILE = "exchanges/kucoin/state/m11_kucoin_shadow_combo_state.json"
PAPER_STATE = "exchanges/kucoin/state/m11_kucoin_paper_state.json"

# Combo weights from D-483
W_M31 = 0.9701
W_KELTNER = 0.0238
W_DUAL = 0.0062
INITIAL = 10000.0

def load_state(path):
    if os.path.exists(path):
        return json.load(open(path))
    return {}

def main():
    # Load existing tracker state
    state = load_state(STATE_FILE)
    if "history" not in state:
        state = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "initial_capital": INITIAL,
            "history": [],
            "last_run": None,
        }
    
    # Load current M31 Paper equity (real)
    paper = load_state(PAPER_STATE)
    if not paper:
        print("[D-485] WARN: kucoin paper state not found")
        return
    
    m31_real_eq = paper.get("total_equity", paper.get("equity", INITIAL))
    m31_real_ret = (m31_real_eq - INITIAL) / INITIAL
    
    # Load profiler data for Keltner/Dual (proxy from backtest)
    try:
        profiler = json.load(open("research_lab/logs/profiles/state.json"))
        def find_daily_ret(strategy, symbol):
            for k, v in profiler["done"].items():
                if not isinstance(v, dict): continue
                if v.get("strategy") != strategy: continue
                if v.get("symbol") != symbol: continue
                if v.get("exchange") != "kucoin": continue
                # calculate avg daily return from metrics
                m = v.get("metrics_by_regime", {}).get("NEUTRAL", {})
                if m and m.get("mean_pct"):
                    return m["mean_pct"] / 100.0
            return 0.0
        
        keltner_daily = find_daily_ret("KELTNER_REV", "ETHUSDTM")
        dual_daily = find_daily_ret("DUAL_MOMENTUM", "XBTUSDTM")
    except Exception as e:
        print(f"[D-485] profiler load err: {e}")
        keltner_daily = 0.0
        dual_daily = 0.0
    
    # Hypothetical: combo equity = weighted
    # Since M31 is real, others are daily-avg proxy
    # m31 contributes: W_M31 * m31_real_ret
    # keltner/dual contribute: W_X * (daily_avg * days_held)
    days_held = 1
    if state["history"]:
        last_ts = state["history"][-1].get("time_iso", "")
        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts.replace("Z","+00:00"))
                days_held = max(1, (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400)
            except: pass
    
    combo_ret = (
        W_M31 * m31_real_ret
        + W_KELTNER * (keltner_daily * days_held)
        + W_DUAL * (dual_daily * days_held)
    )
    combo_eq = INITIAL * (1 + combo_ret)
    
    # Snapshot
    snapshot = {
        "time_iso": datetime.now(timezone.utc).isoformat(),
        "m31_real_equity": round(m31_real_eq, 2),
        "m31_real_ret_pct": round(m31_real_ret * 100, 4),
        "combo_hypo_equity": round(combo_eq, 2),
        "combo_hypo_ret_pct": round(combo_ret * 100, 4),
        "diff_pct": round((combo_eq - m31_real_eq) / INITIAL * 100, 4),
        "keltner_daily_avg": round(keltner_daily * 100, 4),
        "dual_daily_avg": round(dual_daily * 100, 4),
    }
    state["history"].append(snapshot)
    state["last_run"] = snapshot["time_iso"]
    
    # Keep only last 200 snapshots
    if len(state["history"]) > 200:
        state["history"] = state["history"][-200:]
    
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    
    print(f"[D-485] M31 real: ${m31_real_eq:.2f} ({m31_real_ret*100:+.3f}%)")
    print(f"[D-485] Combo hypo: ${combo_eq:.2f} ({combo_ret*100:+.3f}%)")
    print(f"[D-485] Diff: {(combo_eq - m31_real_eq):+.2f} USD")

if __name__ == "__main__":
    main()
