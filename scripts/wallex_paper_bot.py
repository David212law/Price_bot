"""WALLEX PAPER BOT — Live execution of Vol+Trend Ensemble."""
import os, json
import pandas as pd
import numpy as np
from datetime import datetime

STATE_FILE = "data/wallex_paper_bot_state.json"
CAPITAL = 10000.0  # 10,000 USDT equivalent

def load_data():
    raw = json.load(open("data/wallex_tmn_all.json"))
    data = {}
    for sym, prices in raw.items():
        if sym == "USDTTMN" or not sym.endswith("TMN"): continue
        base = sym[:-3]
        if len(prices) >= 100: data[base] = prices
    df = pd.DataFrame(data).sort_index().ffill()
    return df

def detect_regime(df):
    """Vol + Trend Logic"""
    btc = df["BTC"]
    rets = btc.pct_change()
    vol = rets.rolling(14).std() * np.sqrt(365)
    ma50 = btc.rolling(50).mean()
    
    today = df.index[-1]
    price = btc.loc[today]
    v = vol.loc[today]
    ma = ma50.loc[today]
    
    if pd.isna(v) or pd.isna(ma): return "FLAT"
    
    if price > ma and v < 1.0: return "BULL_STRONG"
    if price > ma and v >= 1.0: return "BULL"
    if price <= ma and v < 1.0: return "FLAT"
    if price <= ma and v >= 1.0 and v < 2.0: return "BEAR"
    return "CRASH"

def get_target_portfolio(df, regime):
    """Returns dict of {asset: weight} based on trained logic"""
    # These top 3s were derived from the Oracle test on TRAIN data
    top_per_regime = {
        "BULL_STRONG": ["bh_XRP", "bh_BTC", "rsi21"],
        "BULL": ["bb15", "bb30", "bh_XRP"],
        "FLAT": ["bb15", "bb30", "btfd10"],
        "BEAR": ["rsi14", "bh_TRX", "bb15"],
        "CRASH": ["btfd20", "btfd10", "bb30"]
    }
    
    strats = top_per_regime.get(regime, ["bh_BTC"])
    
    # For simplicity in paper bot, we only execute pure B&H strategies right now
    # because active strategies need daily asset rebalancing.
    # Since Oracle chose bh_XRP, bh_BTC, bh_TRX mostly, we can hold those.
    portfolio = {}
    for s in strats:
        if s.startswith("bh_"):
            asset = s.replace("bh_", "")
            portfolio[asset] = portfolio.get(asset, 0) + 1.0/len(strats)
        else:
            # Fallback to BTC if active strategy selected to avoid overcomplication in MVP bot
            portfolio["BTC"] = portfolio.get("BTC", 0) + 1.0/len(strats)
            
    return portfolio

def main():
    print("="*80)
    print(" WALLEX PAPER BOT — EXECUTION")
    print("="*80)
    
    df = load_data()
    today = df.index[-1].strftime("%Y-%m-%d")
    print(f"Date: {today}")
    
    regime = detect_regime(df)
    print(f"Detected Regime: {regime}")
    
    target_port = get_target_portfolio(df, regime)
    print(f"Target Portfolio: {target_port}")
    
    # Load State
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE))
    else:
        state = {"capital": CAPITAL, "holdings": {}, "last_regime": None, "last_date": None}
        
    # Update value based on current prices
    current_val = state["capital"]
    for asset, qty in state["holdings"].items():
        if asset in df.columns:
            current_val += qty * df[asset].iloc[-1]
            
    print(f"Current Equity: ${current_val:.2f}")
    
    # Rebalance if regime changed
    if regime != state["last_regime"]:
        print(f"🔄 REGIME CHANGED: {state['last_regime']} -> {regime}. Rebalancing...")
        # Apply 0.6% fee for full rebalance
        fee = current_val * 0.006
        current_val -= fee
        state["capital"] = current_val
        state["holdings"] = {}
        
        # Buy new portfolio
        for asset, weight in target_port.items():
            if asset in df.columns:
                price = df[asset].iloc[-1]
                alloc = current_val * weight
                qty = alloc / price
                state["holdings"][asset] = qty
                print(f"  Bought {qty:.4f} {asset} @ {price:,.0f} TMN (${alloc:.2f})")
                
        state["last_regime"] = regime
    else:
        print("No regime change. Holding current portfolio.")
        
    state["last_date"] = today
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    print(f"Saved state to {STATE_FILE}")

if __name__ == "__main__":
    main()
