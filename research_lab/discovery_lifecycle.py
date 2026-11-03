"""D-507: Discovery lifecycle — Candidate → Confirmed → Paper-Ready → Paper-Active."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
LIFECYCLE_FILE = ROOT / "research_lab" / "logs" / "discovery_lifecycle.json"

STATES = ["candidate", "confirmed", "paper_ready", "paper_active"]

def load_lifecycle():
    if LIFECYCLE_FILE.exists():
        try: return json.loads(LIFECYCLE_FILE.read_text())
        except: pass
    return {"strategies": {}}

def save_lifecycle(data):
    LIFECYCLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIFECYCLE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def transition(strategy_key, new_state, reason=""):
    if new_state not in STATES:
        raise ValueError(f"Invalid state: {new_state}")
    data = load_lifecycle()
    entry = data["strategies"].get(strategy_key, {})
    old = entry.get("state", "none")
    entry["state"] = new_state
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    entry.setdefault("transitions", []).append({
        "from": old, "to": new_state, "at": entry["updated_at"], "reason": reason
    })
    data["strategies"][strategy_key] = entry
    save_lifecycle(data)
    print(f"[LIFECYCLE] {strategy_key}: {old} → {new_state} ({reason})")

def list_by_state(state):
    data = load_lifecycle()
    return [k for k, v in data["strategies"].items() if v.get("state") == state]
