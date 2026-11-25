"""TRUE Ensemble: Top 3 strategies per regime, no strict filters."""
import sys, os, json
import pandas as pd
import numpy as np

FEE = 0.006

def build_strategies(df):
    S = {}
    rets = df.pct_change()
    for n in [10, 20, 30, 45, 60]:
        mom = df.pct_change(n)
        ma50 = df.rolling(50).mean()
        sig = (mom > 0) & (df > ma50)
        rank = mom.where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"mom{n}"] = w
    for n in [20, 50]:
        sig = df > df.rolling(n).max().shift(1)
        rank = rets.where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"brk{n}"] = w
    for f, s in [(20,50),(50,200)]:
        sig = df.rolling(f).mean() > df.rolling(s).mean()
        rank = (df.rolling(f).mean()/df.rolling(s).mean()).where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"ma{f}_{s}"] = w
    delta = df.diff()
    for p in [14, 21]:
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        sig = rsi < 30
        rank = rsi.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"rsi{p}"] = w
    for p in [15, 30]:
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        sig = df < ma - 2*sd
        z = (df - ma) / sd
        rank = z.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"bb{p}"] = w
    for dip in [10, 20]:
        sig = df.pct_change(5) < -dip/100
        rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"btfd{dip}"] = w
    for n in [50, 100]:
        ma = df.rolling(n).mean()
        sig = df > ma * 1.02
        rank = (df/ma).where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"trend{n}"] = w
    for a in ["BTC", "ETH", "BNB", "XRP", "TRX"]:
        if a in df.columns:
            w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
            w[a] = 1.0
            S[f"bh_{a}"] = w
    return S

def stats(daily):
    if len(daily) == 0: return 0, 0, 0
    eq = (1 + daily).cumprod()
    dd = ((eq.cummax() - eq)/eq.cummax()).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1]-1)*100, dd, (m/s)*np.sqrt(365) if s > 0 else 0

def main():
    print("="*100)
    print(" TRUE ENSEMBLE — Top 3 per regime, NO strict filters")
    print("="*100)

    for market in ["TMN", "USDT"]:
        print(f"\n{'='*100}\n MARKET: {market}\n{'='*100}")
        raw = json.load(open(f"data/wallex_{market.lower()}_all.json"))
        data = {sym[:-len(market)]: prices for sym, prices in raw.items() 
                if sym != "USDTTMN" and sym.endswith(market) and len(prices) >= 100}
        df = pd.DataFrame(data).sort_index().ffill()
        rets = df.pct_change().fillna(0)
        
        S = build_strategies(df)
        strat_rets = pd.DataFrame({name: (w.shift(1) * rets).sum(axis=1) for name, w in S.items()})
        
        split_idx = int(len(df) * 0.7)
        split_date = df.index[split_idx]
        train_mask, test_mask = df.index < split_date, df.index >= split_date
        train_rets, test_rets = strat_rets[train_mask], strat_rets[test_mask]

        # Regimes (fixed)
        btc_ret = df["BTC"].pct_change(30) * 100
        regimes = pd.Series("FLAT", index=df.index)
        regimes[btc_ret > 15] = "BULL_STRONG"
        regimes[(btc_ret > 5) & (btc_ret <= 15)] = "BULL"
        regimes[(btc_ret > -5) & (btc_ret <= 5)] = "FLAT"
        regimes[(btc_ret > -15) & (btc_ret <= -5)] = "BEAR"
        regimes[btc_ret <= -15] = "CRASH"
        
        print(f"  Days: {len(df)} | TRAIN: {train_mask.sum()}d | TEST: {test_mask.sum()}d")
        print(f"  Strategies: {len(S)}")

        # Select Top 3 per regime
        top_per_regime = {}
        for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
            r_mask = train_mask & (regimes == r)
            if r_mask.sum() < 10: 
                top_per_regime[r] = ["bh_BTC"]
                continue
            # Score by Sharpe
            scores = {}
            for name in S:
                t, d, sh = stats(train_rets.loc[r_mask, name])
                scores[name] = sh
            best_3 = sorted(scores, key=scores.get, reverse=True)[:3]
            top_per_regime[r] = best_3
            print(f"    {r:<14} ({r_mask.sum():>3}d) -> {', '.join(best_3)}")

        # Apply on TEST (equal weight top 3 per regime, fee on switch)
        combined = []
        cur_strats = []
        switches = 0
        for d in test_rets.index:
            r = regimes.loc[d]
            strats = top_per_regime.get(r, ["bh_BTC"])
            # Equal weight return
            r_val = test_rets.loc[d, strats].mean()
            # Fee if changed
            if set(strats) != set(cur_strats):
                r_val -= FEE * 0.5
                switches += 1
                cur_strats = strats
            combined.append(r_val)
            
        comb_s = pd.Series(combined, index=test_rets.index)
        ct, cdd, csh = stats(comb_s)
        
        bht, bhdd, bhsh = stats(rets.loc[test_mask, "BTC"])

        print(f"\n  RESULTS on TEST:")
        print(f"    {'Ensemble (Top 3)':<24} {ct:>+10.1f}%  DD {cdd:>5.1f}%  Sh {csh:>5.2f}  (switches={switches})")
        print(f"    {'B&H BTC':<24} {bht:>+10.1f}%  DD {bhdd:>5.1f}%  Sh {bhsh:>5.2f}")
        print(f"    {'Excess':<24} {ct-bht:>+10.1f}%")

if __name__ == "__main__":
    main()
