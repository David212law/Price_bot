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

    report.append("🌐 **Hyperliquid M11-HL (Global DEX)**")
    hl_data = load_from_github("exchanges/hyperliquid/state/m11_hl_portfolio.json")
    if hl_data:
        total_cap = hl_data.get("total_capital", 10000.0)
        roi = ((total_cap - 10000.0) / 10000.0) * 100
        
        m31_open = len(hl_data.get("m31_pos", {}))
        m35_open = len(hl_data.get("m35_pos", {}))
        m40_open = len(hl_data.get("m40_pos", {}))
        
        report.append(f"   Equity: ${total_cap:.2f} (ROI: {roi:+.2f}%)")
        report.append(f"   M31: {m31_open} | M35: {m35_open} | M40: {m40_open} open positions")
        
        if roi < -3: alerts.append(f"⚠️ M11-HL Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 M11-HL: State not found.")

    report.append("")

    report.append("🇺🇸 **Crypto (Binance M11-V2)**")
    m11_data = load_from_github("exchanges/binance/state/m11_v2_portfolio.json")
    if m11_data:
        cap = m11_data.get("capital", 10000.0)
        open_pos = m11_data.get("open_positions", [])
        regime = m11_data.get("regime", "UNKNOWN")
        total_risk = sum(p.get("risk_amount", 0) for p in open_pos)
        roi = ((cap - 10000.0) / 10000.0) * 100

        report.append(f"   Equity: ${cap:.2f} (ROI: {roi:+.2f}%)")
        report.append(f"   Regime: {regime} | Open Pos: {len(open_pos)} | Risk: ${total_risk:.2f}")

        if roi < -5: alerts.append(f"⚠️ M11-V2 Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 M11-V2: State not found.")

    final_report = "\n".join(report)
    print(final_report)

    if alerts:
        final_report += "\n\n🚨 **ALERTS:**\n" + "\n".join(alerts)

    send_bale(final_report)

if __name__ == "__main__":
    main()
