"""
Reproducibility Test v2 — Using ACTUAL bot logic.
اجرا در Actions (pandas دارد).
"""
import json, os, sys, importlib.util
import pandas as pd
import numpy as np
from datetime import datetime


def load_bot(path):
    spec = importlib.util.spec_from_file_location("bot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # __main__ guard prevents execution
    return module


def load_market(market):
    raw = json.load(open(f"data/wallex_{market.lower()}_all.json"))
    suffix = market
    df_dict = {}
    for k, prices in raw.items():
        if not k.endswith(suffix) or len(prices) < 100:
            continue
        df_dict[k[:-len(suffix)]] = pd.Series(prices)
    df = pd.DataFrame(df_dict)
    df.index = pd.to_datetime(df.index)
    return df.sort_index().ffill()


def simulate(df, bot, days=30):
    capital = bot.CAPITAL
    holdings = {}
    prev_regime = None
    prev_keys = set()
    history = []
    
    tgju = json.load(open("data/usd_irr_tgju.json"))
    usd_rate = tgju[sorted(tgju.keys())[-1]]
    
    for i, date in enumerate(df.index[-days:]):
        df_today = df.loc[:date]
        
        if i == 0:
            history.append({"date": str(date.date()), "equity": capital})
            continue
        
        try:
            regime = bot.detect_regime(df_today)
            target = bot.get_target_portfolio(df_today, regime)
        except Exception:
            history.append({"date": str(date.date()), "equity": capital})
            continue
        
        if target is None:
            history.append({"date": str(date.date()), "equity": capital})
            continue
        
        curr_keys = set(target.keys())
        
        if regime != prev_regime or curr_keys != prev_keys:
            equity = capital
            for a, q in holdings.items():
                if a in df_today.columns:
                    equity += q * df_today[a].iloc[-1] / usd_rate
            
            fee_pct = 0.006 if regime != prev_regime else 0.002
            equity -= equity * fee_pct
            
            capital = 0
            holdings = {}
            for a, w in target.items():
                alloc = equity * w
                if a == "TETHER":
                    capital += alloc
                    continue
                if a in df_today.columns and bot.is_price_fresh(df_today, a, 7):
                    p_usd = df_today[a].iloc[-1] * 1.003 / usd_rate
                    holdings[a] = alloc / p_usd
                else:
                    capital += alloc
            
            prev_regime = regime
            prev_keys = curr_keys
        
        eq = capital
        for a, q in holdings.items():
            if a in df_today.columns:
                eq += q * df_today[a].iloc[-1] / usd_rate
        
        history.append({"date": str(date.date()), "equity": round(eq, 2)})
    
    return history


def stats(history):
    eqs = [h["equity"] for h in history if h["equity"] > 0]
    if len(eqs) < 2:
        return None
    rets = [eqs[i]/eqs[i-1]-1 for i in range(1, len(eqs))]
    total = (eqs[-1]/eqs[0]-1)*100
    sharpe = (np.mean(rets)/np.std(rets)*np.sqrt(365)) if np.std(rets) > 0 else 0
    peak = eqs[0]; mdd = 0
    for e in eqs:
        peak = max(peak, e)
        mdd = min(mdd, (e/peak-1)*100)
    return {
        "start": eqs[0], "end": eqs[-1],
        "return_pct": round(total, 2),
        "sharpe": round(sharpe, 2),
        "max_dd_pct": round(mdd, 2),
        "days": len(eqs),
    }


def main():
    print("="*60)
    print("  REPRODUCIBILITY v2 — Using ACTUAL bot code")
    print("="*60)
    
    bot = load_bot("scripts/wallex_paper_bot.py")
    print(f"\n✅ Bot loaded (CAPITAL=${bot.CAPITAL})")
    
    df = load_market("TMN")
    print(f"✅ Data: {len(df.columns)} assets, {len(df)} days")
    
    history = simulate(df, bot, days=30)
    s = stats(history)
    
    if s:
        print(f"\n  Results:")
        for k, v in s.items():
            print(f"    {k}: {v}")
    
    os.makedirs("archive/reproducibility", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    with open(f"archive/reproducibility/latest_v2.json", "w") as f:
        json.dump({"TMN": {**s, "history": history}}, f, indent=2, default=str)
    print(f"\n✅ Saved: archive/reproducibility/latest_v2.json")


if __name__ == "__main__":
    main()
