"""Merge 306 parametric strategies into profiler returns_matrices."""
import os, json
import pandas as pd
import numpy as np

RETURNS_DIR = "research_lab/logs/profiles/returns_matrices"
STATE_FILE = "research_lab/logs/profiles/state.json"

def build_strategies(df):
    """Same 306 strategies from researcher_predictive.py"""
    S = {}
    rets = df.pct_change()
    for n in [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 250]:
        mom = df.pct_change(n)
        for top in [1, 2, 3, 4, 5]:
            for filt in [True, False]:
                sig = mom > 0
                if filt:
                    ma50 = df.rolling(50).mean()
                    sig = sig & (df > ma50)
                rank = mom.where(sig).rank(axis=1, ascending=False)
                w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
                S[f"mom{n}_t{top}_{'ma' if filt else 'no'}"] = w
    for n in [10, 20, 30, 50, 100, 150, 200]:
        sig = df > df.rolling(n).max().shift(1)
        rank = rets.where(sig).rank(axis=1, ascending=False)
        for top in [1, 2, 3, 4, 5]:
            w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
            S[f"brk{n}_t{top}"] = w
    for f, s in [(5,20),(10,30),(20,50),(50,200),(100,200),(20,100),(30,90)]:
        sig = df.rolling(f).mean() > df.rolling(s).mean()
        rank = (df.rolling(f).mean()/df.rolling(s).mean()).where(sig).rank(axis=1, ascending=False)
        for top in [1, 2, 3, 4, 5]:
            w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
            S[f"ma{f}_{s}_t{top}"] = w
    delta = df.diff()
    up = delta.clip(lower=0); down = -delta.clip(upper=0)
    for p in [7, 14, 21, 28, 35]:
        rsi = 100 - 100 / (1 + up.ewm(alpha=1/p, adjust=False).mean() / down.ewm(alpha=1/p, adjust=False).mean())
        for th in [20, 25, 30, 35, 40]:
            sig = rsi < th
            rank = rsi.where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"rsi{p}_{th}"] = w
    for p in [10, 15, 20, 30, 40]:
        ma = df.rolling(p).mean(); sd = df.rolling(p).std()
        for ns in [1.5, 2, 2.5, 3, 3.5]:
            sig = df < (ma - ns * sd)
            z = (df - ma) / sd
            rank = z.where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"bb{p}_{ns}"] = w
    for dip in [5, 10, 15, 20, 30]:
        for hold in [5, 10, 20]:
            sig = df.pct_change(5) < (-dip / 100)
            rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"btfd{dip}_h{hold}"] = w
    for n in [2, 3, 5, 8, 10]:
        cols = df.columns[:n]
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        w[cols] = 1.0 / n
        S[f"eq{n}"] = w
    for a in ["BTC","ETH","BNB","XRP","TRX","SOL","DOGE","ADA","LINK","AVAX"]:
        if a in df.columns:
            w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
            w[a] = 1.0
            S[f"bh_{a}"] = w
    return S

def process_market(market_name, data_file):
    """Compute returns for all 306 strategies, save to returns_matrices."""
    if not os.path.exists(data_file):
        print(f"  ⚠️ {data_file} not found, skip")
        return 0
    
    print(f"\n📊 Processing {market_name}...")
    raw = json.load(open(data_file))
    data = {}
    for k, v in raw.items():
        if k == "USDTTMN": continue
        base = k.replace("TMN", "").replace("USDT", "").replace("-USD", "")
        if len(v) >= 100:
            data[base] = v
    
    if len(data) < 5:
        print(f"  ⚠️ Too few assets, skip")
        return 0
    
    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    rets = df.pct_change().fillna(0)
    
    print(f"  Assets: {len(df.columns)}, Days: {len(df)}")
    S = build_strategies(df)
    print(f"  Strategies: {len(S)}")
    
    os.makedirs(f"{RETURNS_DIR}/wallex", exist_ok=True)
    
    # Save returns for each strategy
    saved = 0
    for name, weights in S.items():
        daily_rets = (weights.shift(1) * rets).sum(axis=1)
        # Save as {date: ret_pct}
        ret_dict = {d.strftime("%Y-%m-%d"): float(v * 100) for d, v in daily_rets.items() if v != 0}
        if len(ret_dict) < 60: continue
        out_path = f"{RETURNS_DIR}/wallex/{name}_WALLEX.json"
        json.dump(ret_dict, open(out_path, "w"))
        saved += 1
    
    print(f"  ✅ Saved {saved} return matrices")
    return saved

def main():
    print("="*70)
    print(" MERGE ALL STRATEGIES INTO RETURNS_MATRICES")
    print("="*70)
    
    total = 0
    total += process_market("TMN", "data/wallex_tmn_all.json")
    total += process_market("USDT", "data/wallex_usdt_all.json")
    
    print(f"\n{'='*70}")
    print(f"✅ Total: {total} new return files saved")
    print(f"   Now Researcher can load them for TMN and USDT")

if __name__ == "__main__":
    main()
