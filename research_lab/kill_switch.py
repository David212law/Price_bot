import os, json
from research_lab.bale_notifier import send_bale

MODE = "ADVISORY"  # تغییر به "ACTIVE" فقط پس از ۲ هفته داده پایدار
MAX_DD_THRESHOLD = 0.15
CONSECUTIVE_LOSS_DAYS = 7

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

def check_drawdown(st):
    equity = st.get("total_equity", st.get("total_capital", 10000))
    peak = st.get("peak_equity", equity)
    dd = (peak - equity) / peak if peak > 0 else 0
    return dd

def main():
    alerts = []
    for name, path in EXCHANGES.items():
        st = load(path)
        if not st: continue
        dd = check_drawdown(st)
        if dd > MAX_DD_THRESHOLD:
            alerts.append(f"🛑 {name.upper()}: Drawdown = {dd*100:.1f}% (>{MAX_DD_THRESHOLD*100:.0f}%)")
    
    if alerts:
        msg = f"🚨 **Kill Switch ({MODE} mode)**\n\n" + "\n".join(alerts)
        if MODE == "ADVISORY":
            msg += "\n\n⚠️ ADVISORY: هیچ اقدامی انجام نشد. تصمیم با مدیر."
        print(msg)
        send_bale(msg)
    else:
        print("✅ All exchanges within limits (DD < 15%)")

if __name__ == "__main__":
    main()
