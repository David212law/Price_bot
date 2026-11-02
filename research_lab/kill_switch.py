"""
Multi-Layer Kill Switch (D-378)
- Per-Leg DD & Total DD
- Consecutive Losses
- Funding Direction
- Wilson Breach
- Data Freshness
- Fail-Safe Regime
"""
import os, json, base64, requests
from datetime import datetime, timezone
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

MODE = "ADVISORY"
LEG_DD_LIMIT = 0.15
TOTAL_DD_LIMIT = 0.25
MAX_CONSECUTIVE_LOSSES = 8
FUNDING_FLIP_PERIODS = 4
DATA_STALE_HOURS = 9

EXCHANGES = {
    # D-449: kill_switch tracks main 4 bots (not shadows — those are experimental)
    "hyperliquid": "exchanges/hyperliquid/state/m11_hl_portfolio.json",
    "aster": "exchanges/aster/state/m11_aster_paper_state.json",
    "kucoin": "exchanges/kucoin/state/m11_kucoin_paper_state.json",
    "aster_combo": "exchanges/aster/state/m11_aster_combo_paper_state.json",
}

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT:
        print(f"[BALE] {msg[:80]}"); return
    try: requests.post(f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage", json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except: pass

def load_state(path):
    if os.path.exists(path):
        try:
            with open(path) as f: return json.load(f)
        except: pass
    try:
        r = requests.get(f"https://api.github.com/repos/{GH_REPO}/contents/{path}", headers={"Authorization": f"token {GH_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except: pass
    return None

def check_leg_dd(st):
    equity = st.get("total_equity", st.get("total_capital", 10000))
    peak = st.get("peak_equity", equity)
    dd = (peak - equity) / peak if peak > 0 else 0
    return dd, equity

def check_consecutive_losses(history):
    if not history: return 0
    losses = 0
    for t in reversed(history[-20:]):
        if t.get("pnl", 0) < 0: losses += 1
        else: break
    return losses

def check_funding_direction(st):
    """If funding flipped against position for N periods, exit"""
    positions = st.get("m31_pos", {})
    flipped_count = 0
    for sym, pos in positions.items():
        if isinstance(pos, dict) and pos.get("in_pos"):
            hist = pos.get("hist", [])
            if len(hist) >= FUNDING_FLIP_PERIODS:
                recent = hist[-FUNDING_FLIP_PERIODS:]
                if all(r < 0 for r in recent):
                    flipped_count += 1
    return flipped_count

def check_data_freshness(st, path=None):
    """Check state file age. Uses last_run field if present, else file mtime."""
    last_run = st.get("last_run", "")
    if last_run:
        try:
            t = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            hours_old = (datetime.now(timezone.utc) - t).total_seconds() / 3600
            return hours_old > DATA_STALE_HOURS
        except: pass
    # Fallback: file mtime
    if path and os.path.exists(path):
        mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        hours_old = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
        return hours_old > DATA_STALE_HOURS
    return True

def check_wilson(st):
    """Approx: rolling WR in last 20 trades vs backtest baseline"""
    hist = st.get("history", [])
    if len(hist) < 20: return False
    recent = hist[-20:]
    wins = sum(1 for t in recent if t.get("pnl", 0) > 0)
    return (wins / len(recent)) < 0.20

def main():
    alerts = []
    total_equity = 0
    total_peak = 0

    for ex, path in EXCHANGES.items():
        st = load_state(path)
        if not st: continue

        dd, equity = check_leg_dd(st)
        total_equity += equity
        total_peak += st.get("peak_equity", equity)

        # Layer 1: Leg DD
        if dd > LEG_DD_LIMIT:
            alerts.append(f"🛑 {ex.upper()}: Leg DD={dd*100:.1f}% > {LEG_DD_LIMIT*100:.0f}%")

        # Layer 2: Consecutive losses
        losses = check_consecutive_losses(st.get("history", []))
        if losses >= MAX_CONSECUTIVE_LOSSES:
            alerts.append(f"🛑 {ex.upper()}: {losses} consecutive losses")

        # Layer 3: Funding flip
        flipped = check_funding_direction(st)
        if flipped > 0:
            alerts.append(f"⚠️ {ex.upper()}: {flipped} positions with flipped funding")

        # Layer 4: Data freshness
        if check_data_freshness(st, path):
            alerts.append(f"⚠️ {ex.upper()}: Data stale > {DATA_STALE_HOURS}h")

        # Layer 5: Wilson breach
        if check_wilson(st):
            alerts.append(f"⚠️ {ex.upper()}: Rolling WR < 20% (Wilson breach)")

    # Layer 6: Total DD
    if total_peak > 0:
        total_dd = (total_peak - total_equity) / total_peak
        if total_dd > TOTAL_DD_LIMIT:
            alerts.append(f"🛑 TOTAL DD={total_dd*100:.1f}% > {TOTAL_DD_LIMIT*100:.0f}%")

    if alerts:
        msg = f"🚨 **Multi-Layer Kill Switch ({MODE})**\n\n" + "\n".join(alerts)
        if MODE == "ADVISORY":
            msg += "\n\n⚠️ ADVISORY: هیچ اقدامی اعمال نشد."
        print(msg)
        send_bale(msg)
    else:
        print(f"✅ All Kill Switch layers passed. Equity=${total_equity:,.2f}")

if __name__ == "__main__":
    main()
