import os, json, base64, requests
from datetime import datetime, timezone
from research_lab.bale_notifier import send_bale

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")

EXCHANGES = {
    "hyperliquid": "exchanges/hyperliquid/state/m11_hl_portfolio.json",
    "aster": "exchanges/aster/state/m11_aster_paper_state.json",
    "kucoin": "exchanges/kucoin/state/m11_kucoin_paper_state.json"
}

def load_state(path):
    # 1. تلاش برای خواندن از فایل محلی (چون actions/checkout فایل را دارد)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except: pass
    # 2. اگر نبود، از API گیت‌هاب بخوان
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
        r = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except: pass
    return None

def metrics(history, days=30):
    cutoff = (datetime.now(timezone.utc).timestamp() - days*86400) * 1000
    recent = [h for h in history if h.get("time", 0) >= cutoff]
    if not recent: return None
    wins = sum(1 for h in recent if h.get("pnl", 0) > 0)
    gp = sum(h.get("pnl", 0) for h in recent if h.get("pnl", 0) > 0)
    gl = abs(sum(h.get("pnl", 0) for h in recent if h.get("pnl", 0) <= 0))
    pf = (gp/gl) if gl > 0 else (99.99 if gp > 0 else 0)
    return {"n": len(recent), "wr": round(wins/len(recent)*100, 1), "pf": round(pf, 2), "pnl": round(gp-gl, 2)}

def main():
    report = ["📊 **Performance Monitor (30-day rolling)**\n"]
    for name, path in EXCHANGES.items():
        st = load_state(path)
        if not st:
            report.append(f"🔹 {name}: State not found")
            continue
        equity = st.get("total_equity", st.get("total_capital", 0))
        history = st.get("history", [])
        m = metrics(history)
        report.append(f"🌐 **{name.upper()}** — Equity: ${equity:.2f}")
        if m:
            warn = " ⚠️ PF<1.0" if m["pf"] < 1.0 and m["n"] >= 10 else ""
            report.append(f"   30d: n={m['n']} | WR={m['wr']}% | PF={m['pf']} | PnL=${m['pnl']}{warn}")
        else:
            report.append(f"   No trades in last 30 days")
    msg = "\n".join(report)
    print(msg)
    send_bale(msg)

if __name__ == "__main__":
    main()
