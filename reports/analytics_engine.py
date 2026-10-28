import os
import json
import base64
import requests
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

def analyze_m11_hl_hyperliquid():
    print("=== 🌐 Hyperliquid M11-HL (Global DEX) Deep Analytics ===")
    state = load_data("exchanges/hyperliquid/state/m11_hl_portfolio.json")
    if not state:
        print("No state found.")
        return

    total_cap = state.get("total_capital", 10000.0)
    m31_cap = state.get("m31_capital", 5000.0)
    m35_cap = state.get("m35_capital", 2000.0)
    m40_cap = state.get("m40_capital", 2000.0)
    m41_cap = state.get("m41_capital", 1000.0)

    roi = ((total_cap - 10000.0) / 10000.0) * 100

    print(f"Total Equity: ${total_cap:.2f} (ROI: {roi:+.2f}%)")
    print(f"\n  [M31 Funding Arb] Cash: ${m31_cap:.2f} | Open: {len(state.get('m31_pos', {}))}")
    print(f"  [M35 EMA Crossover] Cash: ${m35_cap:.2f} | Open: {len(state.get('m35_pos', {}))}")
    print(f"  [M40 Trend Pullback] Cash: ${m40_cap:.2f} | Open: {len(state.get('m40_pos', {}))}")
    print(f"  [M41 Volatility Breakout] Cash: ${m41_cap:.2f} | Open: {len(state.get('m41_pos', {}))}")

def analyze_aster_m11_aster():
    # بخش جدید برای Aster
    print("\n=== 🌟 Aster (M11-Aster Portfolio) Deep Analytics ===")
    state = load_data("exchanges/aster/state/m11_aster_paper_state.json")
    if not state:
        print("No state found.")
        return

    total_eq = state.get("total_equity", 10000.0)
    cash = state.get("cash", 10000.0)
    a8_pos = state.get("a8_positions", {})
    a20_pos = state.get("a20_positions", {})
    history = state.get("history", [])
    
    roi = ((total_eq - 10000.0) / 10000.0) * 100
    print(f"Total Equity: ${total_eq:.2f} (ROI: {roi:+.2f}%)")
    print(f"Cash Available: ${cash:.2f}")
    print(f"A8 (Grid) Open: {len(a8_pos)}")
    print(f"A20 (SuperTrend) Open: {len(a20_pos)}")
    
    if history:
        net_pnl = sum(h.get("pnl", 0) for h in history)
        print(f"Closed Trades: {len(history)} | Realized PnL: ${net_pnl:+.2f}")

def analyze_crypto_m11_v2():
    print("\n=== 🇺🇸 Crypto Market (M11-V2) Deep Analytics ===")
    state = load_data("exchanges/binance/state/m11_v2_portfolio.json")
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
        print(f"Reconciled Trades: {len(recon)} (WR: {wr:.1f}%) | Net PnL: ${net_pnl:+.2f}")

def main():
    print(f"=== Project Deep Analytics Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    analyze_m11_hl_hyperliquid()
    analyze_crypto_m11_v2()
    analyze_aster_m11_aster() # فراخوانی تابع جدید

if __name__ == "__main__":
    main()
