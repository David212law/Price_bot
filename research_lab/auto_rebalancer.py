import os, json
from datetime import datetime, timezone
from research_lab.bale_notifier import send_bale

MODE = "ADVISORY"  # تغییر به "ACTIVE" فقط با تایید AI3
MIN_PF_TO_KEEP = 1.0
MAX_WEIGHT_CHANGE_PCT = 10  # حداکثر تغییر هر بار

EXCHANGES = {
    "hyperliquid": "exchanges/hyperliquid/state/m11_hl_portfolio.json",
    "aster": "exchanges/aster/state/m11_aster_paper_state.json",
    "kucoin": "exchanges/kucoin/state/m11_kucoin_paper_state.json"
}

def load(path):
    if not os.path.exists(path): return None
    try:
        with open(path) as f: return json.load(f)
    except: return None

def metrics(history, days=30):
    cutoff = (datetime.now(timezone.utc).timestamp() - days*86400) * 1000
    recent = [h for h in history if h.get("time", 0) >= cutoff]
    if not recent: return None
    wins = sum(1 for h in recent if h.get("pnl", 0) > 0)
    gp = sum(h.get("pnl", 0) for h in recent if h.get("pnl", 0) > 0)
    gl = abs(sum(h.get("pnl", 0) for h in recent if h.get("pnl", 0) <= 0))
    pf = gp/gl if gl > 0 else 0
    return {"n": len(recent), "pf": round(pf, 2)}

def main():
    report = [f"⚖️ **Auto-Rebalancer ({MODE} mode)**\n"]
    for name, path in EXCHANGES.items():
        st = load(path)
        if not st: continue
        history = st.get("history", [])
        m = metrics(history)
        if not m or m["n"] < 10:
            report.append(f"🌐 {name.upper()}: Insufficient data (n<10) — no action")
            continue
        report.append(f"🌐 {name.upper()}: 30d PF={m['pf']} n={m['n']}")
        if m["pf"] < MIN_PF_TO_KEEP:
            report.append(f"   ⚠️ PF<{MIN_PF_TO_KEEP} — پیشنهاد: کاهش وزن تا {MAX_WEIGHT_CHANGE_PCT}٪")
        else:
            report.append(f"   ✅ عملکرد قابل قبول — بدون تغییر")
    report.append(f"\n⚠️ {MODE}: پیشنهادها اعمال نشدند. تصمیم با مدیر + AI3.")
    msg = "\n".join(report)
    print(msg)
    send_bale(msg)

if __name__ == "__main__":
    main()
