import os
import json
import base64
import requests
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")

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
    print("\n=== 🌟 Aster (M11-Aster Portfolio) Deep Analytics ===")
    state = load_data("exchanges/aster/state/m11_aster_paper_state.json")
    if not state:
        print("No state found.")
        return

    total_eq = state.get("total_equity", 10000.0)
    m31_cap = state.get("m31_capital", 5000.0)
    a8_cap = state.get("a8_capital", 2500.0)
    a20_cap = state.get("a20_capital", 2500.0)
    
    roi = ((total_eq - 10000.0) / 10000.0) * 100
    print(f"Total Equity: ${total_eq:.2f} (ROI: {roi:+.2f}%)")
    print(f"\n  [M31 Funding] Cash: ${m31_cap:.2f}")
    print(f"  [A8 Grid] Cash: ${a8_cap:.2f} | Open: {len(state.get('a8_positions', {}))}")
    print(f"  [A20 SuperTrend] Cash: ${a20_cap:.2f} | Open: {len(state.get('a20_positions', {}))}")

    history = state.get("history", [])
    if history:
        net_pnl = sum(h.get("pnl", 0) for h in history)
        print(f"\n  Closed Trades: {len(history)} | Realized PnL: ${net_pnl:+.2f}")

def analyze_bot_generic(name, path):
    """D-449: Generic bot analyzer — equity, positions."""
    print(f"=== 🌐 {name} Analytics ===")
    state = load_data(path)
    if not state:
        print("  No state found.")
        return
    eq = state.get("total_equity", state.get("total_capital", 10000.0))
    print(f"  Equity: ${eq:.2f}")
    if "keltner_capital" in state:
        print(f"  Keltner Capital: ${state['keltner_capital']:.2f}")
        print(f"  Keltner Positions: {len(state.get('keltner_pos', {}))}")
    if "m31_capital" in state:
        print(f"  M31 Capital: ${state['m31_capital']:.2f}")
    if "history" in state:
        print(f"  History: {len(state['history'])} closed trades")
    print()

def main():
    print(f"=== Project Deep Analytics Engine ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===\n")
    analyze_m11_hl_hyperliquid()
    analyze_aster_m11_aster()
    # D-449: 5 new bots
    analyze_bot_generic("Aster COMBO", "exchanges/aster/state/m11_aster_combo_paper_state.json")
    analyze_bot_generic("HL Shadow", "exchanges/hyperliquid/state/m11_hl_shadow_portfolio.json")
    analyze_bot_generic("Aster Shadow TREND", "exchanges/aster/state/m11_aster_shadow_trend_state.json")
    analyze_bot_generic("Aster Shadow Balanced", "exchanges/aster/state/m11_aster_shadow_balanced_state.json")
    analyze_bot_generic("Aster Shadow RP", "exchanges/aster/state/m11_aster_shadow_rp_state.json")

if __name__ == "__main__":
    main()
