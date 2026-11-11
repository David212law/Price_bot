"""Auto-approve strategies if they are stable for 3 consecutive days."""
import os, json
from datetime import datetime, timedelta

PENDING = "data/researcher_pending.json"
HISTORY = "data/approval_history.json"
MAIN = "data/researcher_predictive_results.json"

def load_json(path):
    if os.path.exists(path):
        return json.load(open(path))
    return {}

def main():
    pending = load_json(PENDING)
    if not pending:
        print("ℹ️ No pending strategies. Nothing to approve.")
        return

    history = load_json(HISTORY)
    today = datetime.now().strftime("%Y-%m-%d")

    # Track today's top strategies per market/regime
    for market in ["TMN", "USDT", "GLOBAL"]:
        if market not in pending or "predictive" not in pending[market]:
            continue
        top = pending[market]["predictive"]["top"]
        for regime, strats in top.items():
            key = f"{market}_{regime}"
            top_strat = strats[0] if strats else "NONE"
            
            if key not in history:
                history[key] = []
            history[key].append({"date": today, "strategy": top_strat})
            # Keep only last 3 days
            history[key] = history[key][-3:]

    # Check stability: if last 3 records have same strategy -> approve
    stable_markets = set()
    for key, records in history.items():
        if len(records) == 3 and len(set(r["strategy"] for r in records)) == 1:
            market = key.split("_")[0]
            stable_markets.add(market)

    if stable_markets:
        print(f"✅ Auto-approving strategies for markets: {stable_markets}")
        main_data = load_json(MAIN)
        main_data.update(pending)
        main_data["approved_at"] = today
        json.dump(main_data, open(MAIN, "w"), indent=2)
        os.remove(PENDING)
        print("✅ Pending merged into Main.")
    else:
        print("⏳ Strategies not stable for 3 days yet. Still pending.")

    json.dump(history, open(HISTORY, "w"), indent=2)

if __name__ == "__main__":
    main()
