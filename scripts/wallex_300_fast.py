"""300+ strategies on Wallex — PANDAS VECTORIZED (runs in seconds)."""
import sys, os, json
import pandas as pd
import numpy as np
from collections import Counter

FEE = 0.006

def build_strategies(df):
    """Return dict of {name: weights_df}."""
    S = {}
    rets = df.pct_change()
    
    # 1. Momentum variants (110)
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
                
    # 2. Breakout (35)
    for n in [10, 20, 30, 50, 100, 150, 200]:
        high_n = df.rolling(n).max().shift(1)
        sig = df > high_n
        rank = rets.where(sig).rank(axis=1, ascending=False)
        for top in [1, 2, 3, 4, 5]:
            w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
            S[f"brk{n}_t{top}"] = w
            
    # 3. MA Cross (35)
    for f, s in [(5,20),(10,30),(20,50),(50,200),(100,200),(20,100),(30,90)]:
        mf = df.rolling(f).mean()
        ms = df.rolling(s).mean()
        sig = mf > ms
        rank = (mf / ms - 1).where(sig).rank(axis=1, ascending=False)
        for top in [1, 2, 3, 4, 5]:
            w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
            S[f"ma{f}_{s}_t{top}"] = w
            
    # 4. RSI Mean Reversion (25)
    delta = df.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    for p in [7, 14, 21, 28, 35]:
        ema_up = up.ewm(alpha=1/p, adjust=False).mean()
        ema_down = down.ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100 / (1 + ema_up / ema_down)
        for th in [20, 25, 30, 35, 40]:
            sig = rsi < th
            rank = rsi.where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"rsi{p}_{th}"] = w
            
    # 5. RSI Reversal (25)
    for p in [7, 14, 21, 28, 35]:
        ema_up = up.ewm(alpha=1/p, adjust=False).mean()
        ema_down = down.ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100 / (1 + ema_up / ema_down)
        for th in [60, 65, 70, 75, 80]:
            sig = rsi > th
            rank = rsi.where(sig).rank(axis=1, ascending=False)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"rsir{p}_{th}"] = w

    # 6. BB Mean Reversion (25)
    for p in [10, 15, 20, 30, 40]:
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        for ns in [1.5, 2, 2.5, 3, 3.5]:
            sig = df < (ma - ns * sd)
            z = (df - ma) / sd
            rank = z.where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"bb{p}_{ns}"] = w

    # 7. Vol Breakout (5)
    for n in [10, 20, 30, 50, 100]:
        vol = rets.rolling(n).std()
        sig = (rets > 2 * vol) & (rets > 0)
        rank = rets.where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"vol{n}"] = w

    # 8. Trend (5)
    for n in [20, 50, 100, 150, 200]:
        ma = df.rolling(n).mean()
        sig = df > ma * 1.02
        rank = (df / ma).where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"trend{n}"] = w

    # 9. BTFD (15)
    for dip in [5, 10, 15, 20, 30]:
        for hold in [5, 10, 20]:
            sig = df.pct_change(5) < (-dip / 100)
            rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"btfd{dip}_h{hold}"] = w

    # 10. Equal Weight (5)
    for n in [2, 3, 5, 8, 10]:
        cols = df.columns[:n]
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        w[cols] = 1.0 / n
        S[f"eq{n}"] = w

    # 11. Calendar (5)
    days = df.index.dayofweek
    dom = df.index.day
    for which, mask in [("mon", days==0), ("tue", days==1), ("wed", days==2), ("eom", dom>=25), ("bom", dom<=5)]:
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        if "BTC" in w.columns: w.loc[mask, "BTC"] = 1.0
        S[f"cal_{which}"] = w

    # 12. Pairs (5)
    for a1, a2 in [("BTC","ETH"),("BTC","BNB"),("ETH","BNB"),("BTC","XRP"),("BTC","TRX")]:
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        if a1 in w.columns: w[a1] = 0.5
        if a2 in w.columns: w[a2] = 0.5
        S[f"pair_{a1}_{a2}"] = w

    # 13. B&H (10)
    for a in ["BTC","ETH","BNB","XRP","TRX","SOL","DOGE","ADA","LINK","AVAX"]:
        if a in df.columns:
            w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
            w[a] = 1.0
            S[f"bh_{a}"] = w

    # 14. Tether (1)
    S["tether"] = pd.DataFrame(0.0, index=df.index, columns=df.columns)

    return S

def stats(daily):
    if len(daily) == 0: return 0,0,0
    eq = (1 + daily).cumprod()
    peak = eq.cummax()
    dd = ((peak - eq) / peak).max() * 100
    mean = daily.mean()
    std = daily.std()
    sharpe = (mean / std) * np.sqrt(365) if std > 0 else 0
    total = (eq.iloc[-1] - 1) * 100
    return total, dd, sharpe

def main():
    print("="*100)
    print(" WALLEX 300+ STRATEGIES — PANDAS VECTORIZED")
    print("="*100)
    
    summary = {}
    for market in ["TMN", "USDT"]:
        print(f"\n{'='*100}\n MARKET: {market}\n{'='*100}")
        fname = f"data/wallex_{market.lower()}_all.json"
        if not os.path.exists(fname): continue
        
        raw = json.load(open(fname))
        data = {}
        for sym, prices in raw.items():
            if sym == "USDTTMN" or not sym.endswith(market): continue
            base = sym[:-len(market)]
            if len(prices) >= 100:
                data[base] = prices
                
        if not data: continue
        df = pd.DataFrame(data)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().ffill()
        rets = df.pct_change().fillna(0)
        
        print(f"  Assets: {len(df.columns)}, Days: {len(df)} ({df.index[0].date()} -> {df.index[-1].date()})")
        
        # Regime detection
        if "BTC" in df.columns:
            btc_ret = df["BTC"].pct_change(30)
            regimes = pd.Series("FLAT", index=df.index)
            regimes[btc_ret > 15] = "BULL_STRONG"
            regimes[(btc_ret > 5) & (btc_ret <= 15)] = "BULL"
            regimes[(btc_ret > -5) & (btc_ret <= 5)] = "FLAT"
            regimes[(btc_ret > -15) & (btc_ret <= -5)] = "BEAR"
            regimes[btc_ret <= -15] = "CRASH"
        else:
            regimes = pd.Series("FLAT", index=df.index)
            
        print("  Building 306 strategies...")
        S = build_strategies(df)
        print(f"  Strategies built: {len(S)}")
        
        print("  Computing strategy returns...")
        strat_rets = {}
        for name, weights in S.items():
            # shift(1) ensures no look-ahead
            strat_rets[name] = (weights.shift(1) * rets).sum(axis=1)
            
        df_rets = pd.DataFrame(strat_rets)
        
        split_idx = int(len(df) * 0.7)
        split_date = df.index[split_idx]
        train_mask = df.index < split_date
        test_mask = df.index >= split_date
        
        print(f"  TRAIN: {train_mask.sum()}d | TEST: {test_mask.sum()}d | split: {split_date.date()}")
        
        print("  Ranking per regime...")
        best_per_regime = {}
        for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
            r_train = train_mask & (regimes == r)
            if r_train.sum() < 15:
                best_per_regime[r] = "tether"
                continue
            scores = df_rets[r_train].mean()
            best_per_regime[r] = scores.idxmax()
            print(f"    {r:<14} ({r_train.sum():>3}d) -> {best_per_regime[r]}")
            
        # Apply on test
        test_rets = df_rets[test_mask]
        test_regimes = regimes[test_mask]
        
        # Robot combination logic
        combined = []
        cur_strat = "tether"
        fee_paid = 0
        switches = 0
        for date, r in test_regimes.items():
            strat = best_per_regime.get(r, "tether")
            r_val = test_rets.loc[date, strat]
            if strat != cur_strat:
                r_val -= FEE * 0.5
                fee_paid += FEE * 0.5
                switches += 1
                cur_strat = strat
            combined.append(r_val)
            
        comb_s = pd.Series(combined, index=test_rets.index)
        ct, cdd, csh = stats(comb_s)
        
        if "BTC" in df.columns:
            bh_s = rets.loc[test_mask, "BTC"]
            bht, bhdd, bhsh = stats(bh_s)
        else:
            bht, bhdd, bhsh = 0, 0, 0
            
        print(f"\n  RESULTS:")
        print(f"    Combined: {ct:+.1f}% (DD {cdd:.1f}%, Sh {csh:.2f}), Switches={switches}, Fee={fee_paid*100:.1f}%")
        print(f"    B&H BTC:  {bht:+.1f}% (DD {bhdd:.1f}%, Sh {bhsh:.2f})")
        
        summary[market] = {
            "combined": {"total": ct, "dd": cdd, "sharpe": csh, "switches": switches, "fee_pct": fee_paid*100},
            "bnh_btc": {"total": bht, "dd": bhdd, "sharpe": bhsh},
            "best_per_regime": best_per_regime
        }

    json.dump(summary, open("data/wallex_300_fast_results.json", "w"), indent=2)
    print("\nSaved: data/wallex_300_fast_results.json")

if __name__ == "__main__":
    main()
