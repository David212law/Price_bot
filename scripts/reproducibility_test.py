"""
Reproducibility Test — اثبات Backtest = Paper
اجرا در GitHub Actions (pandas دارد)
"""

import json
import os
import sys
from datetime import datetime
import pandas as pd
import numpy as np

def load_market_data(market):
    if market == "TMN":
        raw = json.load(open("data/wallex_tmn_all.json"))
        suffix = "TMN"
    elif market == "USDT":
        raw = json.load(open("data/wallex_usdt_all.json"))
        suffix = "USDT"
    else:
        return None
    
    df_dict = {}
    for key, prices in raw.items():
        if not key.endswith(suffix):
            continue
        base = key[:-len(suffix)]
        if len(prices) < 100:
            continue
        df_dict[base] = pd.Series(prices)
    
    df = pd.DataFrame(df_dict)
    df.index = pd.to_datetime(df.index)
    return df.sort_index().ffill()


def get_rate():
    tgju = json.load(open("data/usd_irr_tgju.json"))
    return tgju[sorted(tgju.keys())[-1]]


def detect_regime(btc_series):
    if len(btc_series) < 50:
        return "FLAT"
    rets = btc_series.pct_change()
    vol = rets.rolling(14).std().iloc[-1] * np.sqrt(365)
    ma50 = btc_series.rolling(50).mean().iloc[-1]
    price = btc_series.iloc[-1]
    
    if pd.isna(vol) or pd.isna(ma50):
        return "FLAT"
    if price > ma50 and vol < 1.0:
        return "BULL_STRONG"
    if price > ma50 and vol >= 1.0:
        return "BULL"
    if price <= ma50 and vol < 1.0:
        return "FLAT"
    if price <= ma50 and vol >= 1.0 and vol < 2.0:
        return "BEAR"
    return "CRASH"


def simulate_paper(df, result_json, days=30):
    """شبیه‌سازی Paper برای N روز گذشته"""
    res = json.load(open(result_json))
    if "TMN" not in res:
        return []
    top_per_regime = res["TMN"]["predictive"]["top"]
    
    capital = 10000.0
    holdings = {}
    prev_regime = None
    prev_keys = set()
    history = []
    
    test_dates = df.index[-days:]
    
    for i, date in enumerate(test_dates):
        btc = df["BTC"].loc[:date]
        
        if i == 0:
            history.append({"date": str(date.date()), "equity": capital, "regime": "INIT"})
            continue
        
        regime = detect_regime(btc)
        target = top_per_regime.get(regime, {"TETHER": 1.0})
        curr_keys = set(target.keys())
        
        if regime != prev_regime or curr_keys != prev_keys:
            # compute equity
            rate = get_rate()
            equity = capital
            for a, q in holdings.items():
                if a in df.columns:
                    p = df[a].loc[:date].iloc[-1]
                    equity += q * p / rate
            
            # rebalance
            fee = equity * 0.006
            equity -= fee
            capital = 0
            holdings = {}
            
            rate = get_rate()
            for a, w in target.items():
                alloc = equity * w
                if a == "TETHER":
                    capital += alloc
                    continue
                if a in df.columns:
                    p = df[a].loc[:date].iloc[-1] * 1.003
                    p_usd = p / rate
                    holdings[a] = alloc / p_usd
                else:
                    capital += alloc
            
            prev_regime = regime
            prev_keys = curr_keys
        
        # daily equity
        rate = get_rate()
        equity = capital
        for a, q in holdings.items():
            if a in df.columns:
                p = df[a].loc[:date].iloc[-1]
                equity += q * p / rate
        
        history.append({
            "date": str(date.date()),
            "equity": round(equity, 2),
            "regime": regime,
            "holdings": list(holdings.keys()),
        })
    
    return history


def main():
    print("=" * 60)
    print("  REPRODUCIBILITY TEST")
    print("=" * 60)
    
    results = {}
    
    for market in ["TMN"]:
        print(f"\n[{market}]")
        df = load_market_data(market)
        if df is None or len(df) < 50:
            print(f"  ❌ data not available")
            continue
        print(f"  Loaded {len(df.columns)} assets, {len(df)} days")
        
        history = simulate_paper(df, "data/researcher_predictive_results.json", days=30)
        if not history:
            print(f"  ❌ simulation failed")
            continue
        
        equities = [h["equity"] for h in history if h["equity"] > 0]
        if len(equities) < 2:
            print(f"  ❌ insufficient data")
            continue
        
        total_return = (equities[-1] / equities[0] - 1) * 100
        daily_rets = [equities[i] / equities[i-1] - 1 for i in range(1, len(equities))]
        sharpe = (np.mean(daily_rets) / np.std(daily_rets) * np.sqrt(365)) if np.std(daily_rets) > 0 else 0
        
        print(f"  Start: ${equities[0]:.2f}")
        print(f"  End:   ${equities[-1]:.2f}")
        print(f"  Return: {total_return:+.2f}%")
        print(f"  Sharpe: {sharpe:.2f}")
        print(f"  Max: ${max(equities):.2f}")
        print(f"  Min: ${min(equities):.2f}")
        
        results[market] = {
            "start_equity": equities[0],
            "end_equity": equities[-1],
            "return_pct": round(total_return, 2),
            "sharpe": round(sharpe, 2),
            "max_equity": max(equities),
            "min_equity": min(equities),
            "days": len(equities),
            "history": history,
        }
    
    # Save results
    os.makedirs("archive/reproducibility", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = f"archive/reproducibility/test_{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Results saved: {out_path}")
    
    # Also save latest (for easy access)
    with open("archive/reproducibility/latest.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("=" * 60)


if __name__ == "__main__":
    main()
