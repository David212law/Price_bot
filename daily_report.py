import os, json, base64, requests, math
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

def get_local_current_price(symbol):
    path = f"iran_market_lab/data_tetri/{symbol}_4h.json"
    if not os.path.exists(path): return 0.0
    try:
        with open(path, 'r') as f:
            candles = json.load(f)
            if candles: return float(candles[-1]["c"])
    except: pass
    return 0.0

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = [f"📊 **Daily Project Report** ({now})\n"]
    alerts = []

    # ─── 1. HYPERLIQUID M36 ───
    report.append("🌐 **Hyperliquid M36 (Global DEX)**")
    hl_data = load_from_github("hyperliquid_m36_state.json")
    if hl_data:
        total_cap = hl_data.get("total_capital", 10000.0)
        roi = ((total_cap - 10000.0) / 10000.0) * 100
        
        m31_open = sum(1 for s in hl_data.get("m31", {}).values() if s.get("in_pos"))
        m35_open = len(hl_data.get("m35", {}))
        
        m35_history = [h for h in hl_data.get("history", []) if h.get("strat") == "M35"]
        m35_pnl = sum(h["pnl"] for h in m35_history)
        m35_wr = (sum(1 for h in m35_history if h["pnl"] > 0) / len(m35_history) * 100) if m35_history else 0
        
        report.append(f"   Equity: ${total_cap:.2f} (ROI: {roi:+.2f}%)")
        report.append(f"   M31 Open: {m31_open} | M35 Open: {m35_open}")
        report.append(f"   M35 Closed: {len(m35_history)} (WR: {m35_wr:.1f}% | PnL: ${m35_pnl:+.2f})")
        
        if roi < -5: alerts.append(f"⚠️ M36 Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 M36: State not found or empty.")

    report.append("")

    # ─── 2. CRYPTO M11-V2 ───
    report.append("🇺🇸 **Crypto (Binance M11-V2)**")
    m11_data = load_from_github("m11_v2_portfolio.json")
    if m11_data:
        cap = m11_data.get("capital", 10000.0)
        open_pos = m11_data.get("open_positions", [])
        regime = m11_data.get("regime", "UNKNOWN")
        adx = m11_data.get("adx", 0)
        total_risk = sum(p.get("risk_amount", 0) for p in open_pos)
        roi = ((cap - 10000.0) / 10000.0) * 100

        report.append(f"   Equity: ${cap:.2f} (ROI: {roi:+.2f}%)")
        report.append(f"   Regime: {regime} (ADX: {adx})")
        report.append(f"   Open Pos: {len(open_pos)} | Risk: ${total_risk:.2f}")

        if roi < -5: alerts.append(f"⚠️ M11-V2 Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 M11-V2: State not found.")

    report.append("")

    # ─── 3. IRAN M11-IR ───
    report.append("🇮🇷 **Iran Market (Wallex M11-IR)**")
    ir_data = load_from_github("iran_market_lab/m11_ir_state.json")
    if ir_data:
        ir_cap = ir_data.get("capital", 10000.0)
        ir_positions = ir_data.get("positions", [])

        total_unrealized_pnl = 0
        invested_val = 0

        for p in ir_positions:
            current_price = get_local_current_price(p["symbol"])
            invested = p.get("invested", 0)
            if current_price > 0:
                current_val = p["units"] * current_price
                total_unrealized_pnl += (current_val - invested)
                invested_val += current_val
            else:
                invested_val += invested

        current_equity = ir_cap + invested_val
        roi = ((current_equity - 10000.0) / 10000.0) * 100

        report.append(f"   Equity: {current_equity:,.2f} USDT (ROI: {roi:+.2f}%)")
        report.append(f"   Open Pos: {len(ir_positions)} | Unrealized PnL: {total_unrealized_pnl:+,.2f} USDT")

        if roi < -5: alerts.append(f"⚠️ M11-IR Drawdown Alert: ROI is {roi:.2f}%")
    else:
        report.append("🔹 M11-IR: State not found.")

    final_report = "\n".join(report)
    print(final_report)

    if alerts:
        final_report += "\n\n🚨 **ALERTS:**\n" + "\n".join(alerts)

    send_bale(final_report)

if __name__ == "__main__":
    main()
