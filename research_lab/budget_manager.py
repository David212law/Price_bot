import json
import os
from datetime import datetime, timezone

LEDGER_PATH = "research_lab/logs/trial_ledger.json"
MONTHLY_BUDGET = 20

def load_ledger():
    if not os.path.exists(LEDGER_PATH):
        return []
    with open(LEDGER_PATH, "r") as f:
        try: return json.load(f)
        except: return []

def check_budget():
    ledger = load_ledger()
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    tests_this_month = sum(1 for entry in ledger if entry["timestamp"].startswith(current_month))
    
    if tests_this_month >= MONTHLY_BUDGET:
        print(f"❌ BUDGET EXCEEDED: {tests_this_month}/{MONTHLY_BUDGET} tests used this month.")
        return False
    print(f"✅ Budget OK: {tests_this_month}/{MONTHLY_BUDGET} tests used.")
    return True

def log_test(strategy, metrics):
    ledger = load_ledger()
    ledger.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "metrics": metrics
    })
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)
