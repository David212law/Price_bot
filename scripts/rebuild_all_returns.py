"""Rebuild ALL return files for 9035 strategies in state.json."""
import os, json, glob
import pandas as pd
import numpy as np

RETURNS_DIR = "research_lab/logs/profiles/returns_matrices"
STATE_FILE = "research_lab/logs/profiles/state.json"

def build_strategies(df):
    """306 parametric strategies."""
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

def main():
    print("="*80)
    print(" REBUILDING ALL RETURNS FOR 9035 STRATEGIES")
    print("="*80)
    
    if not os.path.exists(STATE_FILE):
        print("❌ state.json not found")
        return
    
    state = json.load(open(STATE_FILE))
    done = state.get("done", {})
    print(f"Total strategies: {len(done)}")
    
    # Group by exchange, then load data and build strategies
    by_exchange = {}
    for key, v in done.items():
        if not isinstance(v, dict): continue
        parts = key.split(":")
        if len(parts) < 4: continue
        exch = parts[0]
        if exch not in by_exchange:
            by_exchange[exch] = []
        by_exchange[exch].append(parts)
    
    print(f"\nExchanges: {list(by_exchange.keys())}")
    
    total_saved = 0
    for exch, entries in by_exchange.items():
        print(f"\n[{exch}] {len(entries)} strategies")
        os.makedirs(f"{RETURNS_DIR}/{exch}", exist_ok=True)
        
        # Determine which data files to use
        if exch == "wallex":
            data_files = ["data/wallex_tmn_all.json", "data/wallex_usdt_all.json"]
        elif exch == "hyperliquid":
            data_files = ["data/crypto_5y_usd.json"]
        elif exch in ["aster", "kucoin"]:
            data_files = ["data/crypto_5y_usd.json"]  # approximate
        else:
            continue
        
        # Load data
        all_data = {}
        for df_path in data_files:
            if os.path.exists(df_path):
                raw = json.load(open(df_path))
                for k, v in raw.items():
                    if isinstance(v, dict) and len(v) >= 60:
                        base = k.replace("-USD", "").replace("TMN", "").replace("USDT", "").replace("USDTUSDT", "")
                        if base not in all_data or len(v) > len(all_data[base]):
                            all_data[base] = v
        
        if not all_data:
            print(f"  ⚠️ No data found for {exch}, skip")
            continue
        
        # Build strategies once
        df = pd.DataFrame(all_data)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().ffill()
        rets = df.pct_change().fillna(0)
        S = build_strategies(df)
        print(f"  Built {len(S)} strategies on {len(df.columns)} assets")
        
        # For each entry, find matching strategy and save
        saved = 0
        for parts in entries:
            if len(parts) < 4: continue
            strat, h, sym = parts[1], parts[2], parts[3]
            
            # Find strategy name match
            strat_match = None
            if strat in S:
                strat_match = strat
            else:
                # Try prefix match
                for sname in S:
                    if sname.startswith(strat) or strat.startswith(sname):
                        strat_match = sname
                        break
            
            if not strat_match: continue
            
            # Compute returns
            daily = (S[strat_match].shift(1) * rets).sum(axis=1)
            ret_dict = {d.strftime("%Y-%m-%d"): float(v * 100) for d, v in daily.items() if v != 0}
            if len(ret_dict) < 60: continue
            
            out_file = f"{RETURNS_DIR}/{exch}/{strat}_{h}_{sym}.json"
            json.dump(ret_dict, open(out_file, "w"))
            saved += 1
        
        print(f"  ✅ Saved {saved} return files")
        total_saved += saved
    
    print(f"\n{'='*80}")
    print(f"✅ TOTAL SAVED: {total_saved} return files")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
