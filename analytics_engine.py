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

def analyze_iran_m11():
    print("=== 🇮🇷 Iran Market (M11-IR Grid) Deep Analytics ===")
    state = load_data("iran_market_lab/m11_ir_state.json")
    if not state:
        print("No state found.")
        return
        
    equity_curve = state.get("equity_curve", [])
    if len(equity_curve) < 2:
        print("Not enough equity data. Awaiting more trades.")
        return
        
    start_cap = equity_curve[0]
    end_cap = equity_curve[-1]
    
    # Calculate exact return
    total_ret = ((end_cap - start_cap) / start_cap) * 100
    
    # Calculate MaxDD from Equity Curve
    peak = start_cap
    max_dd = 0.0
    for val in equity_curve:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
        
    # Estimate CAGR (Assuming each point in equity curve is 4 hours apart, 
    # but we'll estimate based on last run time vs start)
    # For a more accurate CAGR, we need timestamps of equity points.
    # For now, let's assume the equity curve array represents 4-hour intervals.
    # Note: This is an approximation if there are gaps.
    total_periods = len(equity_curve) - 1
    days_elapsed = total_periods * 4 / 24
    if days_elapsed > 0:
        cagr = (((end_cap / start_cap) ** (365 / days_elapsed)) - 1) * 100
    else:
        cagr = 0
        
    calmar = cagr / (max_dd * 100) if max_dd > 0 else 0
    
    print(f"Initial Capital: {start_cap:.2f} USDT")
    print(f"Current Equity: {end_cap:.2f} USDT")
    print(f"Total Return: {total_ret:.2f}%")
    print(f"Estimated CAGR (based on {days_elapsed:.1f} days): {cagr:.2f}%")
    print(f"Max Drawdown: {max_dd*100:.2f}%")
    print(f"Standard Calmar (CAGR / MaxDD): {calmar:.2f}")

    # Trade analysis
    history = state.get("history", [])
    closed_trades = [t for t in history if t.get("action") == "CLOSE"]
    if closed_trades:
        wins = [t for t in closed_trades if t["pnl"] > 0]
        win_rate = (len(wins) / len(closed_trades)) * 100
        print(f"Total Trades: {len(closed_trades)} | Win Rate: {win_rate:.2f}%")

def analyze_crypto_m11_v2():
    print("\n=== 🇺🇸 Crypto Market (M11-V2) Deep Analytics ===")
    state = load_data("m11_v2_portfolio.json")
    if not state:
        print("No state found.")
        return
        
    print(f"Current Regime: {state.get('regime', 'UNKNOWN')} (ADX: {state.get('adx', 0)})")
    print(f"Open Positions: {len(state.get('open_positions', []))}")
    print(f"Total Portfolio Risk: {state.get('total_portfolio_risk', 0)} USDT")
    
    recon_history = state.get("reconciliation_history", [])
    if recon_history:
        wins = [t for t in recon_history if t["pnl"] > 0]
        win_rate = (len(wins) / len(recon_history)) * 100
        net_pnl = sum(t["pnl"] for t in recon_history)
        print(f"Reconciled Trades: {len(recon_history)} | Win Rate: {win_rate:.2f}% | Net PnL: {net_pnl:.2f} USDT")

def main():
    print(f"=== Project Deep Analytics Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    analyze_iran_m11()
    analyze_crypto_m11_v2()

if __name__ == "__main__":
    main()
