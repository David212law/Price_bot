import json, os
from datetime import datetime, timezone

LEDGER_PATH = "research_lab/logs/trial_ledger.json"
MONTHLY_BUDGET = 20

def load_ledger():
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    if not os.path.exists(LEDGER_PATH): return []
    with open(LEDGER_PATH, "r") as f:
        try: return json.load(f)
        except: return []

def check_budget():
    ledger = load_ledger()
    cm = datetime.now(timezone.utc).strftime("%Y-%m")
    used = sum(1 for e in ledger if e.get("timestamp","").startswith(cm))
    if used >= MONTHLY_BUDGET:
        print(f"❌ BUDGET EXCEEDED: {used}/{MONTHLY_BUDGET}")
        return False
    print(f"✅ Budget OK: {used}/{MONTHLY_BUDGET}")
    return True

def log_test(strategy, metrics, exchange="kucoin"):
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    ledger = load_ledger()
    ledger.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "exchange": exchange,
        "metrics": metrics
    })
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)
