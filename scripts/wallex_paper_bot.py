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
    # GUARD: If Researcher JSON doesn't exist, exit — do NOT use fallback
    if not os.path.exists("data/researcher_predictive_results.json"):
        print("❌ CRITICAL: researcher_predictive_results.json not found.")
        print("   Run researcher_predictive.py first. Exiting to avoid trading with fallback.")
        return None
    try:
        res = json.load(open("data/researcher_predictive_results.json"))
        top_per_regime = res["TMN"]["predictive"]["top"]
        print("✅ Loaded dynamic strategies from Researcher JSON.")
    except Exception as e:
        print(f"❌ CRITICAL: Failed to parse Researcher JSON: {e}")
        print("   Exiting to avoid trading with fallback.")
        return None
    
    strats_raw = top_per_regime.get(regime, {"bh_BTC": 1.0})
    if isinstance(strats_raw, list):
        # legacy list format
        strats = {s: 1.0/len(strats_raw) for s in strats_raw}
    else:
        strats = strats_raw
    portfolio = {}
    
    # Top-20 liquid assets only (avoid HOT, AGLD, OSMO, etc.)
    LIQUID_ASSETS = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "LINK", "AVAX", "DOT", "MATIC", "LTC", "BCH", "UNI", "ATOM", "ETC", "XLM", "NEAR", "APT"}
    
    def get_bb_oversold(p):
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        z = (df - ma) / sd
        z_today = z.iloc[-1]
        # Only liquid assets
        liquid_cols = [c for c in z_today.index if c in LIQUID_ASSETS]
        if not liquid_cols:
            return ["BTC"]
        z_liquid = z_today[liquid_cols]
        oversold = z_liquid[z_liquid < -2].sort_values(ascending=True).head(3)
        return list(oversold.index) if not oversold.empty else ["BTC"]

    def get_btfd(dip):
        ret = df.pct_change(5).iloc[-1]
        dips = ret[ret < -dip/100].sort_values(ascending=True).head(3)
        return list(dips.index) if not dips.empty else ["BTC"]

    def get_momentum_top(period, top_n, ma_filter):
        ret = df.pct_change(period).iloc[-1]
        if ma_filter:
            ma50 = df.rolling(50).mean().iloc[-1]
            ret = ret[df.iloc[-1] > ma50]  # Only assets above MA50
        # Only liquid assets
        ret = ret[[c for c in ret.index if c in LIQUID_ASSETS]]
        top = ret.sort_values(ascending=False).head(top_n)
        return list(top.index) if not top.empty else ["BTC"]

    def get_rsi_oversold(p):
        delta = df.diff()
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        rsi_today = rsi.iloc[-1]
        oversold = rsi_today[rsi_today < 30].sort_values(ascending=True).head(3)
        return list(oversold.index) if not oversold.empty else ["BTC"]

    for s, w in strats.items():
        # Parse new unified DB format: wallex::strategy::SYMBOL
        if s.startswith("wallex::"):
            parts = s.split("::")
            if len(parts) >= 2:
                s = parts[1]  # Extract strategy name (e.g., "bb15_1.5")
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
            parts = s.replace("rsi", "").split("_")
            p = int(parts[0])
            assets = get_rsi_oversold(p)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        # NEW FORMATS from v23.0 (Momentum, Profiler)
        elif s.startswith("mom"):
            # e.g. mom5_t2_ma -> momentum of 5 days, top 2, with MA filter
            parts = s.split("_")
            period = int(parts[0].replace("mom", ""))
            top_n = int(parts[1].replace("t", ""))
            ma_filter = parts[2] == "ma"
            assets = get_momentum_top(period, top_n, ma_filter)
            for a in assets:
                portfolio[a] = portfolio.get(a, 0) + (w / len(assets))
        elif s.startswith("P_"):
            # Profiler format: P_STRATEGY_SYMBOL
            parts = s.split("_")
            if len(parts) >= 3:
                strategy_name = parts[1]
                asset = parts[2]
                # For profiler strategies, just buy the specific asset if in liquid list
                if asset in LIQUID_ASSETS and asset in df.columns:
                    portfolio[asset] = portfolio.get(asset, 0) + w
                
    return portfolio

def main():
    # Auto-recover corrupted state
    import os as _os
    _state_path = "data/wallex_paper_bot_state.json"
    if _os.path.exists(_state_path):
        try:
            _tmp = json.load(open(_state_path))
            if not isinstance(_tmp, dict) or "holdings" not in _tmp:
                raise ValueError("bad structure")
        except Exception:
            print(f"⚠️ Corrupted state — resetting {_state_path}")
            _os.remove(_state_path)
    
    print("="*80)
    print(" WALLEX PAPER BOT — EXECUTION (Active Strategies)")
    print("="*80)
    
    df = load_data()
    today = df.index[-1].strftime("%Y-%m-%d")
    
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
            json.dump({
                "active": True,
                "last_triggered": datetime.now().isoformat(),
                "reason": f"Equity {eq_check:.2f} < 90% of {CAPITAL:.2f}",
                "bot": "wallex"
            }, open("data/kill_switch_active.json", "w"), indent=2)
            return
    print(f"Date: {today}")
    
    regime = detect_regime(df)
    print(f"Detected Regime: {regime}")

    # ── IRAN CURRENCY CRISIS DETECTION (Survival Mode 2D) ──
    iran_crisis = False
    try:
        tgju = json.load(open("data/usd_irr_tgju.json"))
        dates_sorted = sorted(tgju.keys())
        if len(dates_sorted) >= 31:
            usd_now = tgju[dates_sorted[-1]]
            usd_30d = tgju[dates_sorted[-31]]
            change_30d = (usd_now / usd_30d - 1)
            if change_30d > 0.20:
                iran_crisis = True
                print(f"🇮🇷 Iran currency crisis detected: USD/IRR +{change_30d*100:.1f}% in 30d")
    except Exception as e:
        print(f"⚠️ Iran crisis check failed: {e}")

    
    # ADAPTIVE MODE: exposure based on regime + 30d momentum
    # 30d momentum
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
        if iran_crisis:
            exposure, mode = 0.7, "IRAN-CRISIS-BTC"
        else:
            exposure, mode = 0.3, "BEAR-DEF"
    else:  # CRASH
        if iran_crisis:
            exposure, mode = 0.7, "IRAN-CRISIS-BTC"
        else:
            exposure, mode = 0.0, "DEFENSIVE"

    print(f"📊 Adaptive: Regime={regime}, Mom30={mom_30:+.1f}%, Mode={mode}, Exposure={exposure:.0%}")

    # Build portfolio: exposure% BTC + (1-exposure)% Tether
    if exposure > 0:
        target_port = get_target_portfolio(df, regime)
        if target_port is None:
            print("❌ Exiting: no valid strategy config.")
            return
        # Scale to exposure
        scaled = {k: v * exposure for k, v in target_port.items()}
        scaled["TETHER"] = scaled.get("TETHER", 0) + (1.0 - exposure)
        target_port = scaled
    else:
        target_port = {"TETHER": 1.0}
    print(f"Target Portfolio: {target_port}")
    
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE))
    else:
        state = {"capital": CAPITAL, "holdings": {}, "last_regime": None, "last_date": None, "last_port_keys": [], "initialized": False}
        
    current_val = state["capital"]
    for asset, qty in state["holdings"].items():
        if asset in df.columns:
            current_val += qty * df[asset].iloc[-1]
            
    print(f"Current Equity: ${current_val:.2f}")
    
    curr_keys = set(target_port.keys())
    prev_keys = set(state.get("last_port_keys", []))
    
    # Rebalance if regime changes OR if the target assets change
    if (not state.get("initialized", False)
        or regime != state["last_regime"]
        or curr_keys != prev_keys):
        print(f"🔄 REBALANCING... (Regime: {state['last_regime']} -> {regime}, Assets: {prev_keys} -> {curr_keys})")
        
        # Fee: 0.6% for regime change, 0.2% for daily active rotation
        # Commission only on rebalance (not per signal)
        # If regime changes: 0.6% (full rebalance)
        # If only asset change: 0.2% (partial rebalance)
        # If no change: 0% (no trade)
        fee_pct = 0.006 if regime != state["last_regime"] else 0.002
        fee = current_val * fee_pct
        current_val -= fee
        print(f"  💰 Fee: {fee_pct*100:.1f}% = ${fee:.2f}")
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
        state["initialized"] = True
    else:
        print("No regime change or asset rotation. Holding current portfolio.")
        
    state["last_date"] = today
    json.dump(state, open(STATE_FILE, "w"), indent=2)
    print(f"Saved state to {STATE_FILE}")

if __name__ == "__main__":
    main()
