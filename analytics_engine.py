import os
import json
import base64
import requests
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "Ali212law/Price_bot")

def load_data(filename):
    # 1. Try to load locally first (For Termux testing)
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except Exception:
            pass
            
    # 2. Fallback to GitHub API (For cloud execution)
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{filename}"
        headers = {"Authorization": f"token {GH_TOKEN}"} if GH_TOKEN else {}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    except Exception:
        pass
        
    return {}

def analyze_iran_m11():
    print("=== 🇮🇷 Iran Market (M11-IR Grid) Analytics ===")
    state = load_data("iran_market_lab/m11_ir_state.json")
    if not state:
        print("No state found.")
        return
        
    history = state.get("history", [])
    closed_trades = [t for t in history if t.get("action") == "CLOSE"]
    
    if not closed_trades:
        print("No closed trades yet. Awaiting Grid signals.")
        return
        
    wins = [t for t in closed_trades if t["pnl"] > 0]
    losses = [t for t in closed_trades if t["pnl"] <= 0]
    
    win_rate = (len(wins) / len(closed_trades)) * 100
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else 99.9
    
    print(f"Total Closed Trades: {len(closed_trades)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Total Net PnL: {gross_profit - gross_loss:.2f} USDT")
    
    avg_pnl_pct = sum(t["pnl_pct"] for t in closed_trades) / len(closed_trades)
    print(f"Average Trade PnL: {avg_pnl_pct:.2f}%")

def analyze_crypto_m11_v2():
    print("\n=== 🇺🇸 Crypto Market (M11-V2) Analytics ===")
    state = load_data("m11_v2_portfolio.json")
    if not state:
        print("No state found.")
        return
        
    positions = state.get("open_positions", [])
    rejected = state.get("rejected_signals", [])
    recon_history = state.get("reconciliation_history", [])
    
    print(f"Current Regime: {state.get('regime', 'UNKNOWN')} (ADX: {state.get('adx', 0)})")
    print(f"Open Positions: {len(positions)}")
    print(f"Total Portfolio Risk: {state.get('total_portfolio_risk', 0)} USDT")
    print(f"Rejected Signals (Cap): {len(rejected)}")
    
    if recon_history:
        wins = [t for t in recon_history if t["pnl"] > 0]
        losses = [t for t in recon_history if t["pnl"] <= 0]
        win_rate = (len(wins) / len(recon_history)) * 100
        net_pnl = sum(t["pnl"] for t in recon_history)
        
        print(f"Reconciled Trades: {len(recon_history)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Net Reconciled PnL: {net_pnl:.2f} USDT")
        
        strategies = {}
        for t in recon_history:
            strat = t["strategy"]
            if strat not in strategies:
                strategies[strat] = {"wins": 0, "total": 0, "pnl": 0}
            strategies[strat]["total"] += 1
            strategies[strat]["pnl"] += t["pnl"]
            if t["pnl"] > 0: strategies[strat]["wins"] += 1
            
        print("Strategy Breakdown:")
        for strat, data in strategies.items():
            wr = (data["wins"] / data["total"]) * 100
            print(f"  - {strat}: Trades={data['total']}, WR={wr:.1f}%, PnL={data['pnl']:.2f}")

def main():
    print(f"=== Project Analytics Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    analyze_iran_m11()
    analyze_crypto_m11_v2()

if __name__ == "__main__":
    main()
