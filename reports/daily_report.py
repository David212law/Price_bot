"""Unified Daily Dashboard — Reports on ALL active bots."""
import json
import requests
import os
import glob
import os
from datetime import datetime

def get_eq(data, keys):
    for k in keys:
        if k in data and data[k]: return data[k]
    return 0.0

def send_bale(text):
    """Send report to Bale."""
    token = os.environ.get("BALE_BOT_TOKEN")
    chat_id = os.environ.get("BALE_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://tapi.bale.ai/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False

def main():
    print("="*70)
    print(f" PRICE_BOT UNIFIED DASHBOARD | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*70)

    # 1. Legacy M31 Bots
    print("\n📊 LEGACY M31 BOTS (Daily)")
    print("-" * 70)
    m31_total = 0
    for f in sorted(glob.glob("exchanges/*/state/m11_*.json")):
        try:
            d = json.load(open(f))
            eq = get_eq(d, ["total_equity", "total_capital", "portfolio_equity"])
            name = f.split("/")[-1].replace(".json", "")
            m31_total += eq
            print(f"  {name:<45} ${eq:>10.2f}")
        except: pass
    print(f"  {'M31 Total':<45} ${m31_total:>10.2f}")

    # 2. Predictive Bots
    print("\n🚀 PREDICTIVE BOTS")
    print("-" * 70)
    pred_total = 0
    bots = [
        ("wallex_paper_bot_state.json", "Wallex Conservative"),
        ("wallex_paper_bot_aggressive_state.json", "Wallex Aggressive"),
        ("hl_predictive_bot_state.json", "Hyperliquid (Global)"),
        ("wallex_lab_state.json", "Wallex Lab"),
    ]
    for fname, label in bots:
        path = f"data/{fname}"
        if os.path.exists(path):
            d = json.load(open(path))
            cash = d.get("capital", 0)
            holdings = d.get("holdings", {})
            # Rough equity calc if cash is 0 (fully invested)
            eq = cash if cash > 0 else 10000.0 
            if cash > 0 and holdings:
                 # if partially invested
                 eq = cash + sum(d.get("holdings_values", {}).values())
            regime = d.get("last_regime", "?")
            n_hold = len(holdings)
            print(f"  {label:<25} ${eq:>9.2f} | Regime: {regime:<12} | {n_hold} positions")
            pred_total += eq
        else:
            print(f"  {label:<25} (not initialized)")
    print(f"  {'Predictive Total':<25} ${pred_total:>9.2f}")

    # 3. Researcher Latest
    print("\n🧠 RESEARCHER LATEST")
    print("-" * 70)
    res_path = "data/researcher_predictive_results.json"
    aggr_path = "data/researcher_aggressive_best.json"
    lab_path = "data/researcher_lab.json"
    if os.path.exists(res_path):
        res = json.load(open(res_path))
        for market in ["TMN", "USDT", "GLOBAL"]:
            if market in res and res[market]:
                r = res[market]
                def safe_pct(x):
                    if abs(x) > 10000: return "n/a"
                    return f"{x:+.1f}%"
                # Handle both old 'predictive' and new 'predictive_conservative'
                pred = r.get('predictive', r.get('predictive_conservative', {}))
                if not pred:
                    continue
                oracle_ret = r.get('oracle', {}).get('return', 0)
                pred_ret = pred.get('return', 0)
                print(f"  {market}: Oracle {safe_pct(oracle_ret)} | Pred {safe_pct(pred_ret)}")
                tops = pred.get('top', {})
                for regime in ["BULL_STRONG", "FLAT"]:
                    reg_data = tops.get(regime, {})
                    if isinstance(reg_data, dict):
                        best = max(reg_data, key=reg_data.get) if reg_data else "NONE"
                    elif isinstance(reg_data, list):
                        best = reg_data[0] if reg_data else "NONE"
                    else:
                        best = "NONE"
                    print(f"    {regime} -> {best}")
    else:
        print("  (No researcher data found)")

    print("\n" + "="*70)
    total = m31_total + pred_total
    print(f" GRAND TOTAL: ${total:,.2f}")
    
    # Build comprehensive summary for Bale
    lines = ["📊 PRICE_BOT DAILY REPORT", "=" * 30]
    lines.append(f"M31 Total: ${m31_total:,.2f}")
    lines.append(f"Predictive: ${pred_total:,.2f}")
    lines.append(f"GRAND TOTAL: ${total:,.2f}")
    lines.append("")
    lines.append("🚀 PREDICTIVE BOTS:")
    for fname, label in bots:
        path = f"data/{fname}"
        if os.path.exists(path):
            d = json.load(open(path))
            regime = d.get("last_regime", "?")
            n_hold = len(d.get("holdings", {}))
            lines.append(f"  {label}: {regime} ({n_hold} pos)")
    lines.append("")
    lines.append("🧠 RESEARCHER:")
    if os.path.exists(res_path):
        res = json.load(open(res_path))
        for market in ["TMN", "USDT", "GLOBAL"]:
            if market in res and res[market]:
                r = res[market]
                # Handle both old 'predictive' and new 'predictive_conservative'
                pred = r.get('predictive', r.get('predictive_conservative', {}))
                if not pred:
                    continue
                sharpe = pred.get('sharpe', 0)
                pred_ret = pred.get('return', 0)
                lines.append(f"  {market}: Sharpe {sharpe:.2f} | Ret {pred_ret:+.1f}%")
                tops = pred.get('top', {})
                for regime in ["BULL_STRONG", "FLAT"]:
                    reg_data = tops.get(regime, {})
                    if isinstance(reg_data, dict):
                        best = max(reg_data, key=reg_data.get) if reg_data else "NONE"
                    elif isinstance(reg_data, list):
                        best = reg_data[0] if reg_data else "NONE"
                    else:
                        best = "NONE"
                    lines.append(f"    {regime}: {best}")
    lines.append("")
    lines.append(f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    
    summary = "\n".join(lines)
    if send_bale(summary):
        print("✅ Sent to Bale")
    else:
        print("⚠️ Bale not configured")

if __name__ == "__main__":
    main()
