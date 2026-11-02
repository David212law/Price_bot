import os, json, base64, requests
from datetime import datetime, timezone
from research_lab.bale_notifier import send_bale

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")

# D-449: Track all 8 paper bots
EXCHANGES = {
    "HL Paper": "exchanges/hyperliquid/state/m11_hl_portfolio.json",
    "Aster Paper": "exchanges/aster/state/m11_aster_paper_state.json",
    "KuCoin Paper": "exchanges/kucoin/state/m11_kucoin_paper_state.json",
    "Aster COMBO": "exchanges/aster/state/m11_aster_combo_paper_state.json",
    "HL Shadow": "exchanges/hyperliquid/state/m11_hl_shadow_portfolio.json",
    "Aster Shadow TREND": "exchanges/aster/state/m11_aster_shadow_trend_state.json",
    "Aster Shadow Balanced": "exchanges/aster/state/m11_aster_shadow_balanced_state.json",
    "Aster Shadow RP": "exchanges/aster/state/m11_aster_shadow_rp_state.json",
    "Aster Shadow LV": "exchanges/aster/state/m11_aster_shadow_lv_state.json",
}

def load_state(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f: return json.load(f)
        except: pass
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
    
    # فیکس باگ: PF می‌تواند رشته باشد
    if gl > 0:
        pf = round(gp/gl, 2)
    elif gp > 0:
        pf = "N/A" if len(recent) < 3 else 99.99
    else:
        pf = 0
    
    return {"n": len(recent), "wr": round(wins/len(recent)*100, 1), "pf": pf, "pnl": round(gp-gl, 2)}

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
        
        # شمارش پوزیشن‌های باز
        open_count = 0
        for k in ["m31_pos", "m35_pos", "m40_pos", "m41_pos", "a8_positions", "a20_pos", "a20_positions", "m40_positions"]:
            if k not in st: continue
            positions = st[k]
            if isinstance(positions, dict):
                for pos in positions.values():
                    # اگر in_pos دارد، فقط فعال‌ها را بشمار
                    if isinstance(pos, dict) and 'in_pos' in pos:
                        if pos['in_pos']: open_count += 1
                    else:
                        open_count += 1
            elif isinstance(positions, list):
                open_count += len(positions)
                
        report.append(f"🌐 **{name.upper()}** — Equity: ${equity:.2f}")
        report.append(f"   Open Positions: {open_count}")
        
        if m:
            # هندل کردن pf رشته‌ای
            pf_val = m["pf"]
            warn = ""
            if isinstance(pf_val, (int, float)) and pf_val < 1.0 and m["n"] >= 10:
                warn = " ⚠️ PF<1.0"
            report.append(f"   Closed 30d: n={m['n']} | WR={m['wr']}% | PF={pf_val} | PnL=${m['pnl']}{warn}")
        else:
            report.append(f"   Closed 30d: No trades closed in last 30 days")
            
    msg = "\n".join(report)
    print(msg)
    send_bale(msg)

if __name__ == "__main__":
    main()
