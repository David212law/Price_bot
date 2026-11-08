"""Approve strategies from pending JSON and move to main."""
import os, json
from datetime import datetime

PENDING = "data/researcher_pending.json"
MAIN = "data/researcher_predictive_results.json"

def main():
    if not os.path.exists(PENDING):
        print("❌ No pending strategies to approve.")
        return
    pending = json.load(open(PENDING))
    if os.path.exists(MAIN):
        main_data = json.load(open(MAIN))
    else:
        main_data = {}
    # Merge pending into main
    main_data.update(pending)
    main_data["approved_at"] = datetime.now().isoformat()
    json.dump(main_data, open(MAIN, "w"), indent=2)
    os.remove(PENDING)
    print("✅ Strategies approved and moved to main JSON.")

if __name__ == "__main__":
    main()
