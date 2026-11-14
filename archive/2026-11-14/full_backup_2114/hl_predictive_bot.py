"""HYPERLIQUID PREDICTIVE BOT — Connects live HL API to Researcher's strategies."""
import os, json, time, requests
import pandas as pd
import numpy as np

STATE_FILE = "data/hl_predictive_bot_state.json"
# FROZEN: reads researcher_predictive_results.json (v28.7: GLOBAL 2.98)
# GLOBAL is not as important as TMN/USDT — frozen at v28.7
RESEARCHER_FILE = "data/researcher_predictive_results.json"
CAPITAL = 10000.0
COINS = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "MATIC"]

def fetch_hl_candles(coin, days=200):
    """Fetch daily candles from Hyperliquid API."""
    end = int(time.time() * 1000)
    start = end - days * 86400 * 1000
    try:
        r = requests.post("https://api.hyperliquid.xyz/info", json={
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": "1d", "startTime": start, "endTime": end}
        }, timeout=10)
        data = r.json()
        if not data: return None
        # Format: {"T": time, "c": close, ...}
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["T"], unit="ms")
        df.set_index("date", inplace=True)
        return df["c"].astype(float)
    except Exception as e:
        print(f"  ❌ HL {coin}: {e}")
        return None

def build_df():
    series = {}
    print("Fetching live data from Hyperliquid...")
    for c in COINS:
        s = fetch_hl_candles(c)
        if s is not None and len(s) > 50:
            series[c] = s
    if not series: return None
    df = pd.DataFrame(series)
    return df.ffill()

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
        print("✅ Loaded GLOBAL strategies.")
    except:
        top_per_regime = {"FLAT": ["bh_BTC"]}
        
    strats_raw = top_per_regime.get(regime, {"bh_BTC": 1.0})
    if isinstance(strats_raw, list):
        strats = {s: 1.0/len(strats_raw) for s in strats_raw}
    else:
        strats = strats_raw
    portfolio = {}

    def get_bb_oversold_h(p):
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        z = (df - ma) / sd
        z_today = z.iloc[-1]
        oversold = z_today[z_today < -2].sort_values(ascending=True).head(2)
        return list(oversold.index) if not oversold.empty else ["BTC"]

    def get_rsi_oversold_h(p):
        delta = df.diff()
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        rsi_today = rsi.iloc[-1]
        oversold = rsi_today[rsi_today < 30].sort_values(ascending=True).head(2)
        return list(oversold.index) if not oversold.empty else ["BTC"]

    def get_momentum_top_h(period, top_n, ma_filter):
        ret = df.pct_change(period).iloc[-1]
        if ma_filter:
            ma50 = df.rolling(50).mean().iloc[-1]
            ret = ret[df.iloc[-1] > ma50]
        top = ret.sort_values(ascending=False).head(top_n)
        return list(top.index) if not top.empty else ["BTC"]

    for s, w in strats.items():
        if s.startswith("bh_"):
            asset = s.replace("bh_", "")
            portfolio[asset] = portfolio.get(asset, 0) + w
        elif s.startswith("eq"):
            n = int(s.replace("eq", ""))
            for a in df.columns[:n]: portfolio[a] = portfolio.get(a, 0) + (w/n)
        elif s.startswith("bb"):
            p = int(s.replace("bb", "").split("_")[0])
            assets = get_bb_oversold_h(p)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        elif s.startswith("rsi"):
            p = int(s.replace("rsi", "").split("_")[0])
            assets = get_rsi_oversold_h(p)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        elif s.startswith("mom"):
            parts = s.split("_")
            period = int(parts[0].replace("mom", ""))
            top_n = int(parts[1].replace("t", ""))
            ma_filter = parts[2] == "ma" if len(parts) > 2 else False
            assets = get_momentum_top_h(period, top_n, ma_filter)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        elif s.startswith("P_"):
            # P_STRATEGY_SYMBOL
            parts = s.split("_")
            if len(parts) >= 3:
                asset = parts[2]
                if asset in df.columns:
                    portfolio[asset] = portfolio.get(asset, 0) + w
        else:
            portfolio["BTC"] = portfolio.get("BTC", 0) + w
    return portfolio

def main():
    df = build_df()
    if df is None:
        print("❌ Failed to fetch live data.")
        return
        
    # AUTO-RESET KILL SWITCH IF STATE MISSING (fresh start)
    if not os.path.exists(STATE_FILE):
        if os.path.exists("data/kill_switch_active.json"):
            json.dump({"active": False, "last_triggered": None, "reason": None}, 
                      open("data/kill_switch_active.json", "w"), indent=2)
            print("🔄 Fresh start: Kill Switch auto-reset")

    # KILL SWITCH CHECK
    if os.path.exists(STATE_FILE):
        tmp_state = json.load(open(STATE_FILE))
        eq_check = tmp_state.get("capital", CAPITAL) + sum(q * df[a].iloc[-1] for a, q in tmp_state.get("holdings", {}).items() if a in df.columns)
        if eq_check < CAPITAL * 0.9:
            print(f"❌ KILL SWITCH TRIGGERED: Equity {eq_check:.2f} < 90% of {CAPITAL:.2f}")
            from datetime import datetime as _dt
            json.dump({
                "active": True,
                "last_triggered": _dt.now().isoformat(),
                "reason": f"Equity {eq_check:.2f} < 90% of {CAPITAL:.2f}",
                "bot": "hl"
            }, open("data/kill_switch_active.json", "w"), indent=2)
            return
            
    regime = detect_regime(df)
    # ADAPTIVE MODE
    btc_series = df["BTC"]
    mom_30 = 0
    if len(btc_series) >= 31:
        mom_30 = (btc_series.iloc[-1] / btc_series.iloc[-31] - 1) * 100

    if regime == "BULL_STRONG":
        exposure, mode = 1.0, "AGGRESSIVE"
    elif regime == "BULL":
        exposure, mode = 0.8, "BULL-MILD"
    elif regime == "FLAT":
        if mom_30 < -5:
            exposure, mode = 0.3, "FLAT->BEAR"
        elif mom_30 > 5:
            exposure, mode = 0.8, "FLAT->BULL"
        else:
            exposure, mode = 0.5, "BALANCED"
    elif regime == "BEAR":
        exposure, mode = 0.3, "BEAR-DEF"
    else:  # CRASH
        exposure, mode = 0.0, "DEFENSIVE"

    print(f"📊 Adaptive: Regime={regime}, Mom30={mom_30:+.1f}%, Mode={mode}, Exposure={exposure:.0%}")

    if exposure > 0:
        target = get_target_portfolio(df, regime)
        scaled = {k: v * exposure for k, v in target.items()}
        scaled["TETHER"] = scaled.get("TETHER", 0) + (1.0 - exposure)
        target = scaled
    else:
        target = {"TETHER": 1.0}
    print(f"Date: {df.index[-1].date()} | Regime: {regime} | Target: {target}")
    
    if os.path.exists(STATE_FILE): state = json.load(open(STATE_FILE))
    else: state = {"capital": CAPITAL, "holdings": {}, "last_regime": None, "last_port_keys": [], "initialized": False}
        
    val = state["capital"]
    for a, q in state["holdings"].items():
        if a in df.columns: val += q * df[a].iloc[-1]
            
    curr_keys = set(target.keys())
    if (not state.get("initialized", False)
        or regime != state["last_regime"]
        or curr_keys != set(state["last_port_keys"])):
        fee = val * 0.00035 # HL taker fee ~0.035%
        print(f"  💰 Fee: 0.035% = ${fee:.2f}")
        val -= fee; state["capital"] = 0.0; state["holdings"] = {}
        for a, w in target.items():
            if a in df.columns:
                price = df[a].iloc[-1] * 1.001 # 0.1% Slippage
                qty = (val * w) / price
                state["holdings"][a] = qty
                print(f"  Bought {qty:.4f} {a} @ ${df[a].iloc[-1]:,.0f}")
        state["last_regime"] = regime; state["last_port_keys"] = list(curr_keys); state["initialized"] = True
    
    state["last_date"] = df.index[-1].strftime("%Y-%m-%d")
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    print(f"Equity: ${val:.2f}")

if __name__ == "__main__": main()
