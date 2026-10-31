"""Unified Master v2 — reads validation survivors, proposes weights (no auto-apply)."""
import sys, os, json
sys.path.append(os.getcwd())
from datetime import datetime, timezone
from research_lab.bale_notifier import send_bale

M31_BASE = 0.65
CASH_BASE = 0.20
DIVERSIFIER_BUDGET = 0.15

def build_portfolio(survivors):
    """M31 + Cash + up to 2 survivors (equal weight)."""
    weights = {"M31": M31_BASE, "Cash": CASH_BASE}
    if not survivors:
        weights["Cash"] = 1.0 - M31_BASE
        return weights
    # Pick top 2 survivors by PF
    top = sorted(survivors, key=lambda x: -x["pf"])[:2]
    per = DIVERSIFIER_BUDGET / len(top)
    for s in top:
        key = f"{s['strategy']}_{s['params'].get('period', s['params'].get('fast', 'x'))}"
        weights[key] = round(per, 4)
    # Normalize
    total = sum(weights.values())
    return {k: round(v/total, 4) for k, v in weights.items()}

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== 🤖 Unified Master v2 ({now}) ===\n")
    
    val_file = "research_lab/logs/validation_results.json"
    if not os.path.exists(val_file):
        print(f"❌ No validation results. Run validation_v2.py first.")
        return
    
    with open(val_file) as f:
        validation = json.load(f)
    
    proposed = {}
    report = [f"🤖 **Unified Master v2** ({now})\n"]
    
    for exchange, survivors in validation.items():
        weights = build_portfolio(survivors)
        proposed[exchange] = weights
        report.append(f"\n**{exchange.upper()}** — {len(survivors)} survivors")
        for name, w in sorted(weights.items(), key=lambda x: -x[1]):
            report.append(f"  • {name}: {w*100:.1f}%")
    
    # Save proposal (NOT active_weights.json)
    with open("exchanges/proposed_weights.json", "w") as f:
        json.dump(proposed, f, indent=2)
    print("✅ proposed_weights.json saved (requires AI3 approval to apply)")
    
    msg = "\n".join(report)
    msg += "\n\n⚠️ این پیشنهاد است، نه اعمال. برای اعمال، تأیید AI3 الزامی است."
    print(msg)
    send_bale(msg)

if __name__ == "__main__":
    main()
