"""M12 Bot — Paper trading using config."""
import json, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path: sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)

from calc import regime_label
from m12_strategies import STRATEGIES

CONFIG = os.path.join(_HERE, "config.json")
STATE = os.path.join(_HERE, "state.json")
DATA_DIR = os.path.join(_ROOT, "data")

def load_data():
    raw = json.load(open(os.path.join(DATA_DIR, "wallex_tmn_all.json")))
    btc = raw["BTCTMN"]
    return [float(v) for k, v in sorted(btc.items())] if isinstance(btc, dict) else [float(x) for x in btc]

def to_candles(prices):
    return [{"t": i, "o": p, "h": p*1.005, "l": p*0.995, "c": p, "v": 1.0} for i, p in enumerate(prices)]

def main():
    if not os.path.exists(CONFIG):
        print("No config found. Run researcher.py first."); return
    config = json.load(open(CONFIG))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"equity": 10000.0, "trades": []}
    
    btc = load_data()
    regime = regime_label(btc[-1] / btc[-31] - 1)
    print(f"Current Regime: {regime}")
    
    for market in ["TMN", "USDT"]:
        active = config.get(market, {}).get(regime, {})
        print(f"[{market}] Active: {list(active.keys()) if active else 'CASH'}")
        
        if not active: continue
        
        # Simulate one trade per active strategy on the latest bar
        for strat_name, weight in active.items():
            # Find the asset (we use BTC for simplicity in this test)
            candles = to_candles(btc)
            trades = STRATEGIES[strat_name](candles)
            if trades:
                last_trade = trades[-1]
                # Check if last trade happened on the latest bar
                if last_trade.get("t") == candles[-1]["t"]:
                    print(f"  -> SIGNAL: {strat_name} | Ret: {last_trade['ret']*100:.2f}% (Weight: {weight:.2f})")
                    state["trades"].append({
                        "time": last_trade["t"],
                        "market": market,
                        "strategy": strat_name,
                        "weight": weight,
                        "ret": last_trade["ret"]
                    })
    
    json.dump(state, open(STATE, "w"), indent=2)
    print(f"State saved to {STATE}")

if __name__ == "__main__":
    main()
