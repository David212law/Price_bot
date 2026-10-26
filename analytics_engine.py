import os
import json
import base64
import requests
import math
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")

def load_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f: return json.load(f)
        except: pass
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{filename}"
        headers = {"Authorization": f"token {GH_TOKEN}"} if GH_TOKEN else {}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    except: pass
    return {}

def analyze_m36_hyperliquid():
    print("=== 🌐 Hyperliquid M36 (Global DEX) Deep Analytics ===")
    state = load_data("m11_hl_portfolio.json") # به‌روزرسانی به فایل جدید تخصیص‌دهنده
    if not state:
        print("No state found.")
        return
    
    total_cap = state.get("total_capital", 10000.0)
    m31_cap = state.get("m31_capital", 6000.0)
    m35_cap = state.get("m35_capital", 4000.0)
    
    roi = ((total_cap - 10000.0) / 10000.0) * 100
    
    m31_open = len(state.get("m31_pos", {}))
    m35_open = len(state.get("m35_pos", {}))
    
    print(f"Total Equity: ${total_cap:.2f} (ROI: {roi:+.2f}%)")
    print(f"\n  [M31 Funding Arb]")
    print(f"    Capital: ${m31_cap:.2f} | Open Positions: {m31_open}")
    print(f"\n  [M35 EMA Crossover]")
    print(f"    Capital: ${m35_cap:.2f} | Open Positions: {m35_open}")
    
    history = state.get("history", [])
    if history:
        m35_trades = [h for h in history if h.get("strat") == "M35" and h.get("action") == "STOP_LOSS"]
        if m35_trades:
            pnl = sum(t.get("pnl", 0) for t in m35_trades)
            print(f"    M35 Closed Trades: {len(m35_trades)} | Net PnL: ${pnl:+.2f}")

def analyze_crypto_m11_v2():
    print("\n=== 🇺🇸 Crypto Market (M11-V2) Deep Analytics ===")
    state = load_data("m11_v2_portfolio.json")
    if not state:
        print("No state found.")
        return
        
    print(f"Current Regime: {state.get('regime', 'UNKNOWN')} (ADX: {state.get('adx', 0)})")
    print(f"Open Positions: {len(state.get('open_positions', []))}")
    print(f"Total Portfolio Risk: ${state.get('total_portfolio_risk', 0):.2f}")
    
    recon = state.get("reconciliation_history", [])
    if recon:
        wins = [t for t in recon if t["pnl"] > 0]
        wr = (len(wins) / len(recon)) * 100
        net_pnl = sum(t["pnl"] for t in recon)
        print(f"Reconciled Trades: {len(recon)} (WR: {wr:.1f}%)")
        print(f"Net Reconciled PnL: ${net_pnl:+.2f}")
        
        strategies = {}
        for t in recon:
            strat = t["strategy"]
            if strat not in strategies:
                strategies[strat] = {"wins": 0, "total": 0, "pnl": 0}
            strategies[strat]["total"] += 1
            strategies[strat]["pnl"] += t["pnl"]
            if t["pnl"] > 0: strategies[strat]["wins"] += 1
        
        print("Strategy Breakdown:")
        for strat, data in strategies.items():
            wr = (data["wins"] / data["total"]) * 100
            print(f"  - {strat}: {data['total']} trades | WR: {wr:.1f}% | PnL: ${data['pnl']:+.2f}")

def main():
    print(f"=== Project Deep Analytics Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    analyze_m36_hyperliquid()
    analyze_crypto_m11_v2()

if __name__ == "__main__":
    main()
