"""GLOBAL PAPER BOT — Executes strategies discovered by Researcher for GLOBAL market."""
import os, json
import pandas as pd
import numpy as np

STATE_FILE = "data/global_paper_bot_state.json"
CAPITAL = 10000.0

def load_data():
    raw = json.load(open("data/crypto_5y_usd.json"))
    df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k.endswith("-USD")})
    df.index = pd.to_datetime(df.index)
    return df.sort_index().ffill()

def detect_regime(df):
    btc = df["BTC"]; rets = btc.pct_change()
    vol = rets.rolling(14).std() * np.sqrt(365); ma50 = btc.rolling(50).mean()
    today = df.index[-1]; price, v, ma = btc.loc[today], vol.loc[today], ma50.loc[today]
    if pd.isna(v) or pd.isna(ma): return "FLAT"
    if price > ma and v < 1.0: return "BULL_STRONG"
    if price > ma and v >= 1.0: return "BULL"
    if price <= ma and v < 1.0: return "FLAT"
    if price <= ma and v >= 1.0 and v < 2.0: return "BEAR"
    return "CRASH"

def get_target_portfolio(df, regime):
    try:
        res = json.load(open("data/researcher_predictive_results.json"))
        top_per_regime = res["GLOBAL"]["predictive"]["top"]
        print("✅ Loaded dynamic GLOBAL strategies.")
    except:
        top_per_regime = {"FLAT": ["bh_BTC"]}
        
    strats = top_per_regime.get(regime, ["bh_BTC"])
    portfolio = {}
    
    # Simplistic execution for GLOBAL (assumes long-only spot)
    for s in strats:
        w = 1.0 / len(strats)
        if s.startswith("bh_"):
            portfolio[s.replace("bh_", "")] = portfolio.get(s.replace("bh_", ""), 0) + w
        elif s.startswith("eq"):
            n = int(s.replace("eq", ""))
            for a in df.columns[:n]: portfolio[a] = portfolio.get(a, 0) + (w/n)
        else:
            # Fallback for active strategies (btfd, bb) -> just buy BTC for simplicity in MVP
            portfolio["BTC"] = portfolio.get("BTC", 0) + w
            
    return portfolio

def main():
    df = load_data()
    regime = detect_regime(df)
    target = get_target_portfolio(df, regime)
    print(f"Regime: {regime} | Target: {target}")
    
    if os.path.exists(STATE_FILE): state = json.load(open(STATE_FILE))
    else: state = {"capital": CAPITAL, "holdings": {}, "last_regime": None, "last_port_keys": []}
        
    val = state["capital"]
    for a, q in state["holdings"].items():
        if a in df.columns: val += q * df[a].iloc[-1]
            
    curr_keys = set(target.keys())
    if regime != state["last_regime"] or curr_keys != set(state["last_port_keys"]) or not state["holdings"]:
        fee = val * 0.001 # 0.1% global fee approx
        val -= fee; state["capital"] = 0.0; state["holdings"] = {}
        for a, w in target.items():
            if a in df.columns:
                qty = (val * w) / df[a].iloc[-1]
                state["holdings"][a] = qty
                print(f"  Bought {qty:.4f} {a} @ ${df[a].iloc[-1]:,.0f}")
        state["last_regime"] = regime; state["last_port_keys"] = list(curr_keys)
    
    state["last_date"] = df.index[-1].strftime("%Y-%m-%d")
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    print(f"Equity: ${val:.2f}")

if __name__ == "__main__": main()
