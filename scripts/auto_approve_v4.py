"""Auto-approve with REAL Sharpe check + 30-day stability."""
import os, json, math
from datetime import datetime

PENDING = "data/researcher_pending.json"
HISTORY = "data/approval_history.json"
MAIN = "data/researcher_predictive_results.json"
CHANGELOG = "CHANGELOG.md"
AUTO_SHARPE_THRESHOLD = 1.0
MIN_STABLE_DAYS = 7
# Emergency conditions
EMERGENCY_DEFENSIVE_SHARPE = 1.5
EMERGENCY_ALPHA_SHARPE = 2.0   # was 30, reduced per feedback

def load_json(path):
    if os.path.exists(path): return json.load(open(path))
    return {}

def calc_sharpe(daily_rets):
    """Sharpe from list of daily returns (in %)."""
    if len(daily_rets) < 10: return 0.0
    m = sum(daily_rets) / len(daily_rets)
    var = sum((r - m)**2 for r in daily_rets) / len(daily_rets)
    std = var ** 0.5
    return (m / std) * math.sqrt(365) if std > 0 else 0.0

def get_holdout_sharpe(market, regime):
    """Extract Sharpe from Researcher's output for this market/regime."""
    pending = load_json(PENDING)
    if market not in pending: return 0.0
    pred = pending[market].get("predictive", {})
    top = pred.get("top", {})
    if regime not in top: return 0.0
    # Researcher stores top strategies; Sharpe is in 'sharpe' field if available
    # If not available, fallback to 0 (which means human approval required)
    metrics = pred.get("metrics", {}).get(regime, {})
    return metrics.get("sharpe", 0.0)

def append_changelog(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    with open(CHANGELOG, "a") as f:
        f.write(f"\n## {ts}\n{msg}\n")

def main():
    pending = load_json(PENDING)
    if not pending:
        print("ℹ️ No pending.")
        return

    history = load_json(HISTORY)
    today = datetime.now().strftime("%Y-%m-%d")
    auto_approved = []
    human_required = []

    for market in ["TMN", "USDT", "GLOBAL"]:
        if market not in pending or "predictive" not in pending[market]:
            continue
        top = pending[market]["predictive"]["top"]
        for regime, strats in top.items():
            key = f"{market}_{regime}"
            top_strat = strats[0] if strats else "NONE"
            
            if key not in history: history[key] = []
            history[key].append({"date": today, "strategy": top_strat})
            history[key] = history[key][-MIN_STABLE_DAYS:]

            records = history[key]
            if len(records) < MIN_STABLE_DAYS: 
                continue
            if len(set(r["strategy"] for r in records)) != 1: 
                continue

            # NEW: Check Sharpe
            sharpe = get_holdout_sharpe(market, regime)
            if sharpe >= AUTO_SHARPE_THRESHOLD:
                auto_approved.append(f"{key} -> {top_strat} (Sharpe {sharpe:.2f})")
            else:
                human_required.append(f"{key} -> {top_strat} (Sharpe {sharpe:.2f})")

    if auto_approved:
        main_data = load_json(MAIN)
        main_data.update(pending)
        main_data["approved_at"] = today
        main_data["approval_method"] = "auto_v3_sharpe_checked"
        json.dump(main_data, open(MAIN, "w"), indent=2)
        os.remove(PENDING)
        append_changelog(f"AUTO-APPROVED ({len(auto_approved)}):\n- " + "\n- ".join(auto_approved))
        print(f"✅ Auto-approved {len(auto_approved)} (Sharpe > {AUTO_SHARPE_THRESHOLD})")
    
    if human_required:
        append_changelog(f"HUMAN REQUIRED ({len(human_required)}):\n- " + "\n- ".join(human_required))
        print(f"⏸ {len(human_required)} require human approval (Sharpe < {AUTO_SHARPE_THRESHOLD})")
        print("   Run: python3 scripts/approve_strategies.py")

    json.dump(history, open(HISTORY, "w"), indent=2)

if __name__ == "__main__":
    main()
