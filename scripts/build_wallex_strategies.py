"""Build returns matrices for advanced strategies on Wallex data."""
import json
import pandas as pd
import numpy as np
import os
from datetime import datetime

# Load Wallex TMN data
raw = json.load(open("data/wallex_tmn_all.json"))
data = {}
for sym, prices in raw.items():
    if sym == "USDTTMN" or not sym.endswith("TMN"): continue
    base = sym[:-3]
    if len(prices) >= 100: data[base] = prices
df = pd.DataFrame(data).sort_index().ffill()
df.index = pd.to_datetime(df.index)
rets = df.pct_change().fillna(0)

# Define advanced strategies manually (since build_strategies in Researcher has limited set)
def make_signals():
    S = {}
    # 1. Z-Score Mean Reversion
    for n in [10, 20, 30]:
        ma = df.rolling(n).mean()
        sd = df.rolling(n).std()
        z = (df - ma) / sd
        S[f'zscore_{n}'] = (z < -1.5).astype(float)
    
    # 2. SuperTrend (simplified)
    hl2 = (df.rolling(10).max() + df.rolling(10).min()) / 2
    atr = (df.rolling(10).max() - df.rolling(10).min())
    S['supertrend_10'] = ((df > hl2 + atr) * 1.0)
    
    # 3. VWAP Mean Reversion
    vol = pd.DataFrame(1, index=df.index, columns=df.columns) # placeholder
    vwap = (df * vol).rolling(20).sum() / vol.rolling(20).sum()
    S['vwap_20'] = (df < vwap * 0.98).astype(float)
    
    # 4. Donchian Breakout
    for n in [20, 50]:
        S[f'donchian_{n}'] = (df > df.rolling(n).max().shift(1)).astype(float)
    
    # 5. Keltner Reversion
    ema = df.ewm(span=20).mean()
    atr_k = (df.rolling(20).max() - df.rolling(20).min()).rolling(20).mean()
    S['keltner_rev'] = (df < ema - 2 * atr_k).astype(float)
    
    return S

S = make_signals()
os.makedirs("research_lab/logs/profiles/returns_matrices/wallex", exist_ok=True)

# Save each strategy's returns
for name, sig in S.items():
    strat_rets = (sig.shift(1) * rets).sum(axis=1)
    # Convert to dict for JSON
    rets_dict = {str(k.date()): float(v) * 100 for k, v in strat_rets.items() if not pd.isna(v)}
    out_path = f"research_lab/logs/profiles/returns_matrices/wallex/{name}_WALLEX.json"
    with open(out_path, "w") as f:
        json.dump(rets_dict, f)
    print(f"✅ Saved {name}: {len(rets_dict)} days")

print(f"\n✅ Done. Built {len(S)} new strategies.")
