import os, json, base64, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone

def get_session():
    session = requests.Session()
    retry = Retry(total=5, read=5, connect=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

session = get_session()
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT: return
    url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    try: session.post(url, json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except: pass

def load_from_github(filename):
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{filename}"
        r = session.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        return {}
    except: return {}

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = [f"📊 **Daily Project Report** ({now})\n"]
    alerts = []

    # ─── Hyperliquid M11-HL ───
    report.append("🌐 **Hyperliquid M11-HL (Global DEX)**")
    hl_data = load_from_github("exchanges/hyperliquid/state/m11_hl_portfolio.json")
    if hl_data:
        total_cap = hl_data.get("total_capital", 10000.0)
        roi = ((total_cap - 10000.0) / 10000.0) * 100
        m31_open = len(hl_data.get("m31_pos", {}))
        m35_open = len(hl_data.get("m35_pos", {}))
        m40_open = len(hl_data.get("m40_pos", {}))
        m41_open = len(hl_data.get("m41_pos", {}))

        report.append(f"   Equity: ${total_cap:.2f} (ROI: {roi:+.2f}%)")
        report.append(f"   Open Pos: M31={m31_open} | M35={m35_open} | M40={m40_open} | M41={m41_open}")

        if roi < -3: alerts.append(f"⚠️ M11-HL Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 M11-HL: State not found.")

    report.append("")

    # ─── Aster M11-Aster ───
    report.append("🌟 **Aster (M11-Aster Portfolio)**")
    aster_data = load_from_github("exchanges/aster/state/m11_aster_paper_state.json")
    if aster_data:
        eq = aster_data.get("total_equity", 10000.0)
        cash = aster_data.get("cash", 10000.0)
        a8_pos = len(aster_data.get("a8_positions", {}))
        a20_pos = len(aster_data.get("a20_positions", {}))
        roi = ((eq - 10000.0) / 10000.0) * 100
        
        report.append(f"   Equity: ${eq:.2f} (ROI: {roi:+.2f}%)")
        report.append(f"   Cash: ${cash:.2f} | Open Pos: A8={a8_pos} | A20={a20_pos}")
        
        if roi < -3: alerts.append(f"⚠️ Aster Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 Aster: State not found.")

    final_report = "\n".join(report)
    print(final_report)

    if alerts:
        final_report += "\n\n🚨 **ALERTS:**\n" + "\n".join(alerts)

    send_bale(final_report)

if __name__ == "__main__":
    main()
