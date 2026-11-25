"""Robust ensemble: strict filters + Sharpe-weighted selection."""
import sys, os, json
import pandas as pd
import numpy as np

FEE = 0.006

def build_strategies(df):
    S = {}
    rets = df.pct_change()
    # Momentum
    for n in [10, 20, 30, 45, 60, 90]:
        mom = df.pct_change(n)
        ma50 = df.rolling(50).mean()
        sig = (mom > 0) & (df > ma50)
        rank = mom.where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"mom{n}_t3"] = w
    # Breakout
    for n in [20, 50]:
        sig = df > df.rolling(n).max().shift(1)
        rank = rets.where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"brk{n}_t3"] = w
    # MA Cross
    for f, s in [(20,50),(50,200)]:
        sig = df.rolling(f).mean() > df.rolling(s).mean()
        rank = (df.rolling(f).mean()/df.rolling(s).mean() - 1).where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"ma{f}_{s}_t3"] = w
    # RSI MR
    delta = df.diff()
    for p in [14, 21]:
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        sig = rsi < 30
        rank = rsi.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"rsi{p}_30"] = w
    # BB MR
    for p in [15, 30]:
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        sig = df < ma - 2*sd
        z = (df - ma) / sd
        rank = z.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"bb{p}_2"] = w
    # BTFD
    for dip in [10, 20]:
        sig = df.pct_change(5) < -dip/100
        rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"btfd{dip}"] = w
    # Trend
    for n in [50, 100, 200]:
        ma = df.rolling(n).mean()
        sig = df > ma * 1.02
        rank = (df/ma).where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"trend{n}"] = w
    # Equal weight
    for n in [3, 5, 10]:
        cols = df.columns[:n]
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        w[cols] = 1.0/n
        S[f"eq{n}"] = w
    # B&H
    for a in ["BTC", "ETH", "BNB", "XRP", "TRX"]:
        if a in df.columns:
            w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
            w[a] = 1.0
            S[f"bh_{a}"] = w
    S["tether"] = pd.DataFrame(0.0, index=df.index, columns=df.columns)
    return S

def stats(daily):
    if len(daily) == 0: return 0, 0, 0
    eq = (1 + daily).cumprod()
    peak = eq.cummax()
    dd = ((peak - eq)/peak).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1]-1)*100, dd, (m/s)*np.sqrt(365) if s > 0 else 0

def count_signals(weights):
    """Count days where any position was held."""
    return (weights.abs().sum(axis=1) > 0.01).sum()

def main():
    print("="*100)
    print(" ROBUST ENSEMBLE — strict filters + Sharpe-weighted")
    print("="*100)

    for market in ["TMN", "USDT"]:
        print(f"\n{'='*100}\n MARKET: {market}\n{'='*100}")

        raw = json.load(open(f"data/wallex_{market.lower()}_all.json"))
        data = {}
        for sym, prices in raw.items():
            if sym == "USDTTMN" or not sym.endswith(market): continue
            base = sym[:-len(market)]
            if len(prices) >= 100: data[base] = prices
        df = pd.DataFrame(data)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().ffill()
        rets = df.pct_change().fillna(0)

        S = build_strategies(df)
        strat_rets = {name: (w.shift(1) * rets).sum(axis=1) for name, w in S.items()}
        df_rets = pd.DataFrame(strat_rets)

        split_idx = int(len(df) * 0.7)
        split_date = df.index[split_idx]
        train_mask = df.index < split_date
        test_mask = df.index >= split_date
        train_rets = df_rets[train_mask]
        test_rets = df_rets[test_mask]

        print(f"  Assets: {len(df.columns)}, Days: {len(df)}")
        print(f"  TRAIN: {train_mask.sum()}d | TEST: {test_mask.sum()}d")
        print(f"  Strategies: {len(S)}")

        # STEP 1: STRICT FILTER
        print(f"\n  Step 1: Strict filter")
        candidates = []
        for name in S:
            if name == "tether": continue
            t, d, sh = stats(train_rets[name])
            n_sig = count_signals(S[name][train_mask])
            # Filters:
            # 1. TRAIN return < 500% (filter bugs)
            # 2. TRAIN DD < 35%
            # 3. TRAIN Sharpe > 0.7
            # 4. n_signals >= 50
            if t > 500: continue
            if d > 35: continue
            if sh < 0.7: continue
            if n_sig < 50: continue
            candidates.append((name, t, d, sh, n_sig))

        candidates.sort(key=lambda x: -x[3])  # sort by Sharpe
        print(f"    Pass filters: {len(candidates)}/{len(S)-1}")
        for name, t, d, sh, n in candidates[:10]:
            print(f"      {name:<15} TRAIN Sh={sh:.2f} ret={t:+.1f}% DD={d:.1f}% n={n}")

        if len(candidates) < 3:
            print("    Too few after filter — skip")
            continue

        # STEP 2: GREEDY DIVERSIFY (corr < 0.6)
        print(f"\n  Step 2: Greedy selection (corr < 0.6)")
        selected = []
        for name, t, d, sh, n in candidates:
            if len(selected) == 0:
                selected.append((name, sh, t, d))
                continue
            corrs = [train_rets[[name, s[0]]].corr().iloc[0, 1] for s in selected]
            max_corr = max(corrs)
            if max_corr < 0.6 and not np.isnan(max_corr):
                selected.append((name, sh, t, d))
            if len(selected) >= 8:
                break

        print(f"    Selected {len(selected)}:")
        for i, (n, sh, t, d) in enumerate(selected, 1):
            print(f"      {i}. {n:<15} TRAIN Sh={sh:.2f} ret={t:+.1f}% DD={d:.1f}%")

        # STEP 3: SHARPE-SQUARED WEIGHTS
        print(f"\n  Step 3: Weights by Sharpe²")
        # Only positive Sharpe strategies
        pos = [(n, sh) for n, sh, t, d in selected if sh > 0]
        weights = {n: sh**2 for n, sh in pos}
        total = sum(weights.values())
        weights = {n: w/total for n, w in weights.items()}
        for n, w in sorted(weights.items(), key=lambda x: -x[1]):
            print(f"      {n:<15} weight={w:.1%}")

        # STEP 4: ENSEMBLE ON TEST
        print(f"\n  Step 4: Ensemble on TEST")
        test_ensemble = pd.Series(0.0, index=test_rets.index)
        for n, w in weights.items():
            test_ensemble += w * test_rets[n]
        # Monthly fee
        test_ensemble -= FEE * 0.5 / 30

        ct, cdd, csh = stats(test_ensemble)
        if "BTC" in df.columns:
            bht, bhdd, bhsh = stats(rets.loc[test_mask, "BTC"])
        else:
            bht, bhdd, bhsh = 0, 0, 0

        print(f"    {'Ensemble':<20} {ct:>+10.1f}%  DD {cdd:>5.1f}%  Sh {csh:>5.2f}")
        print(f"    {'B&H BTC':<20} {bht:>+10.1f}%  DD {bhdd:>5.1f}%  Sh {bhsh:>5.2f}")
        print(f"    {'Excess':<20} {ct-bht:>+10.1f}%")

        # Per-component on TEST
        print(f"\n    Component performance on TEST:")
        for n in weights:
            st, sd, ss = stats(test_rets[n])
            print(f"      {n:<15} {st:>+10.1f}%  DD {sd:>5.1f}%  Sh {ss:>5.2f}")

        # Final verdict
        print(f"\n  VERDICT for {market}:")
        if csh > bhsh and ct > bht:
            print(f"    ✅✅ Ensemble beats B&H on BOTH return and Sharpe")
        elif csh > bhsh:
            print(f"    ✅ Ensemble better Sharpe (defensive)")
        elif ct > bht:
            print(f"    ✅ Ensemble better return (aggressive)")
        else:
            print(f"    ❌ Ensemble worse — B&H wins")

if __name__ == "__main__":
    main()
