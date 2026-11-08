"""WALLEX PAPER BOT — Live execution of Vol+Trend Ensemble with Active Strategies."""
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
    df.index = pd.to_datetime(df.index)
    return df

def detect_regime(df):
    """Vol + Trend Logic (Optimized from Oracle testing)"""
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
    """Executes the actual active strategies chosen by Oracle for this regime"""
    # Read dynamically from Researcher's output
    try:
        res = json.load(open("data/researcher_predictive_results.json"))
        top_per_regime = res["TMN"]["predictive"]["top"]
        print("✅ Loaded dynamic strategies from Researcher JSON.")
    except Exception as e:
        print(f"⚠️ Could not load Researcher JSON ({e}). Using defaults.")
        top_per_regime = {
            "BULL_STRONG": ["bh_BTC"], "BULL": ["bh_BTC"],
            "FLAT": ["bh_BTC"], "BEAR": ["bh_BTC"], "CRASH": ["bh_BTC"]
        }
    
    strats = top_per_regime.get(regime, ["bh_BTC"])
    portfolio = {}
    
    def get_bb_oversold(p):
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        z = (df - ma) / sd
        z_today = z.iloc[-1]
        oversold = z_today[z_today < -2].sort_values(ascending=True).head(3)
        return list(oversold.index) if not oversold.empty else ["BTC"]

    def get_btfd(dip):
        ret = df.pct_change(5).iloc[-1]
        dips = ret[ret < -dip/100].sort_values(ascending=True).head(3)
        return list(dips.index) if not dips.empty else ["BTC"]

    def get_rsi_oversold(p):
        delta = df.diff()
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        rsi_today = rsi.iloc[-1]
        oversold = rsi_today[rsi_today < 30].sort_values(ascending=True).head(3)
        return list(oversold.index) if not oversold.empty else ["BTC"]

    for s in strats:
        w = 1.0 / len(strats)  # Equal weight per strategy
        if s.startswith("bh_"):
            asset = s.replace("bh_", "")
            portfolio[asset] = portfolio.get(asset, 0) + w
        elif s.startswith("bb"):
            p = int(s.replace("bb", "").split("_")[0])
            assets = get_bb_oversold(p)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        elif s.startswith("btfd"):
            dip = int(s.replace("btfd", "").split("_")[0])
            assets = get_btfd(dip)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        elif s.startswith("rsi"):
            p = int(s.replace("rsi", "").split("_")[0])
            assets = get_rsi_oversold(p)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
                
    return portfolio

def main():
    print("="*80)
    print(" WALLEX PAPER BOT — EXECUTION (Active Strategies)")
    print("="*80)
    
    df = load_data()
    today = df.index[-1].strftime("%Y-%m-%d")
    
    # KILL SWITCH CHECK
    if os.path.exists(STATE_FILE):
        tmp_state = json.load(open(STATE_FILE))
        eq_check = tmp_state.get("capital", CAPITAL) + sum(q * df[a].iloc[-1] for a, q in tmp_state.get("holdings", {}).items() if a in df.columns)
        if eq_check < CAPITAL * 0.9:
            print(f"❌ KILL SWITCH TRIGGERED: Equity {eq_check:.2f} < 90% of {CAPITAL:.2f}")
            return
    print(f"Date: {today}")
    
    regime = detect_regime(df)
    print(f"Detected Regime: {regime}")
    
    if regime in ["BEAR", "CRASH"]:
        print(f"⚠️ Regime {regime}: Forcing TETHER (Survival Mode)")
        target_port = {"TETHER": 1.0}
    else:
        target_port = get_target_portfolio(df, regime)
    print(f"Target Portfolio: {target_port}")
    
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE))
    else:
        state = {"capital": CAPITAL, "holdings": {}, "last_regime": None, "last_date": None, "last_port_keys": []}
        
    current_val = state["capital"]
    for asset, qty in state["holdings"].items():
        if asset in df.columns:
            current_val += qty * df[asset].iloc[-1]
            
    print(f"Current Equity: ${current_val:.2f}")
    
    curr_keys = set(target_port.keys())
    prev_keys = set(state.get("last_port_keys", []))
    
    # Rebalance if regime changes OR if the target assets change
    if regime != state["last_regime"] or curr_keys != prev_keys or not state["holdings"]:
        print(f"🔄 REBALANCING... (Regime: {state['last_regime']} -> {regime}, Assets: {prev_keys} -> {curr_keys})")
        
        # Fee: 0.6% for regime change, 0.2% for daily active rotation
        fee_pct = 0.006 if regime != state["last_regime"] else 0.002
        fee = current_val * fee_pct
        current_val -= fee
        state["capital"] = 0.0  # Fully invested (no cash left)
        state["holdings"] = {}
        
        for asset, weight in target_port.items():
            if asset in df.columns:
                price = df[asset].iloc[-1] * 1.003 # 0.3% Slippage
                alloc = current_val * weight
                qty = alloc / price
                state["holdings"][asset] = qty
                print(f"  Bought {qty:.6f} {asset} @ {price:,.0f} TMN (${alloc:.2f})")
                
        state["last_regime"] = regime
        state["last_port_keys"] = list(curr_keys)
    else:
        print("No regime change or asset rotation. Holding current portfolio.")
        
    state["last_date"] = today
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    print(f"Saved state to {STATE_FILE}")

if __name__ == "__main__":
    main()
