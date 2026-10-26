import os
import json
import base64
import requests
import math
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")

def load_data(filename):
    # Try local first
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except: pass
    # Fallback to GitHub
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
    state = load_data("hyperliquid_m36_state.json")
    if not state:
        print("No state found.")
        return
    
    total_cap = state.get("total_capital", 10000.0)
    m31_cap = state.get("m31_capital", 6000.0)
    m35_cap = state.get("m35_capital", 4000.0)
    
    roi = ((total_cap - 10000.0) / 10000.0) * 100
    
    # M31 Analysis
    m31_open = sum(1 for s in state.get("m31", {}).values() if s.get("in_pos"))
    m31_funding = sum(s.get("funding", 0) for s in state.get("m31", {}).values())
    m31_fees = sum(s.get("fees", 0) for s in state.get("m31", {}).values())
    m31_net = m31_funding - m31_fees
    
    print(f"Total Equity: ${total_cap:.2f} (ROI: {roi:+.2f}%)")
    print(f"\n  [M31 Funding Arb]")
    print(f"    Capital: ${m31_cap:.2f} | Open Positions: {m31_open}")
    print(f"    Funding Earned: ${m31_funding:+.2f} | Fees: ${m31_fees:.2f}")
    print(f"    Net Profit: ${m31_net:+.2f}")
    
    # M35 Analysis
    m35_open = len(state.get("m35", {}))
    m35_history = [h for h in state.get("history", []) if h.get("strat") == "M35"]
    m35_pnl = sum(h["pnl"] for h in m35_history)
    m35_wins = sum(1 for h in m35_history if h["pnl"] > 0)
    m35_wr = (m35_wins / len(m35_history) * 100) if m35_history else 0
    
    print(f"\n  [M35 EMA Crossover]")
    print(f"    Capital: ${m35_cap:.2f} | Open Positions: {m35_open}")
    print(f"    Closed Trades: {len(m35_history)} (Wins: {m35_wins}, WR: {m35_wr:.1f}%)")
    print(f"    Net PnL: ${m35_pnl:+.2f}")
    
    if m35_history:
        best = max(m35_history, key=lambda x: x["pnl"])
        worst = min(m35_history, key=lambda x: x["pnl"])
        print(f"    Best Trade: ${best['pnl']:+.2f} | Worst Trade: ${worst['pnl']:+.2f}")

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
        
        # Per-strategy breakdown
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

def analyze_iran_m11():
    print("\n=== 🇮🇷 Iran Market (M11-IR Grid) Deep Analytics ===")
    state = load_data("iran_market_lab/m11_ir_state.json")
    if not state:
        print("No state found.")
        return
    
    equity_curve = state.get("equity_curve", [])
    if len(equity_curve) < 2:
        print("Not enough data yet.")
        return
    
    start_cap = equity_curve[0]
    end_cap = equity_curve[-1]
    roi = ((end_cap - start_cap) / start_cap) * 100
    
    print(f"Initial Capital: ${start_cap:.2f}")
    print(f"Current Equity: ${end_cap:.2f}")
    print(f"ROI: {roi:+.2f}%")
    print(f"Open Positions: {len(state.get('positions', []))}")
    
    # Trade analysis
    history = state.get("history", [])
    closed = [t for t in history if t.get("action") == "CLOSE"]
    if closed:
        wins = [t for t in closed if t.get("pnl", 0) > 0]
        wr = (len(wins) / len(closed)) * 100
        net_pnl = sum(t.get("pnl", 0) for t in closed)
        print(f"Closed Trades: {len(closed)} (WR: {wr:.1f}%)")
        print(f"Net PnL: ${net_pnl:+.2f}")

def main():
    print(f"=== Project Deep Analytics Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    analyze_m36_hyperliquid()
    analyze_crypto_m11_v2()
    analyze_iran_m11()

if __name__ == "__main__":
    main()
