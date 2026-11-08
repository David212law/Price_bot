"""Complementary ensemble: find anti-correlated strategies, combine them."""
import sys, os, json
import pandas as pd
import numpy as np

FEE = 0.006


def build_strategies(df):
    S = {}
    rets = df.pct_change()
    # Momentum (simplified — 11 variants instead of 110)
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
    # RSI mean reversion
    delta = df.diff()
    for p in [14, 21]:
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        sig = rsi < 30
        rank = rsi.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"rsi{p}_30"] = w
    # BB mean reversion
    for p in [15, 30]:
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        sig = df < ma - 2*sd
        z = (df - ma) / sd
        rank = z.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"bb{p}_2"] = w
    # BTFD (buy the f***ing dip)
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
    # Tether
    S["tether"] = pd.DataFrame(0.0, index=df.index, columns=df.columns)
    return S


def stats(daily):
    if len(daily) == 0: return 0, 0, 0
    eq = (1 + daily).cumprod()
    peak = eq.cummax()
    dd = ((peak - eq)/peak).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1]-1)*100, dd, (m/s)*np.sqrt(365) if s > 0 else 0


def main():
    print("="*100)
    print(" COMPLEMENTARY ENSEMBLE — find anti-correlated strategies, combine")
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

        print(f"  Assets: {len(df.columns)}, Days: {len(df)}")

        S = build_strategies(df)
        print(f"  Strategies: {len(S)}")

        # Returns per strategy (no look-ahead: shift(1))
        strat_rets = {name: (w.shift(1) * rets).sum(axis=1) for name, w in S.items()}
        df_rets = pd.DataFrame(strat_rets)

        split_idx = int(len(df) * 0.7)
        split_date = df.index[split_idx]
        train_mask = df.index < split_date
        test_mask = df.index >= split_date
        train_rets = df_rets[train_mask]
        test_rets = df_rets[test_mask]

        print(f"  TRAIN: {train_mask.sum()}d | TEST: {test_mask.sum()}d")

        # Step 1: Filter — keep only "good" strategies on TRAIN
        train_stats = {n: stats(train_rets[n]) for n in train_rets.columns}
        good = [n for n, (t, d, s) in train_stats.items() if s > 0.5 and t > 0 and n != "tether"]
        print(f"\n  Step 1: Filter good on TRAIN")
        print(f"    Sharpe > 0.5 AND return > 0: {len(good)}/{len(S)}")

        if len(good) < 3:
            print("    Too few good strategies — skip market")
            continue

        # Step 2: Greedy diversity selection
        print(f"\n  Step 2: Greedy selection (corr < 0.5 to existing)")
        selected = []
        # Sort by Sharpe descending
        good_sorted = sorted(good, key=lambda n: -train_stats[n][2])
        for cand in good_sorted:
            if len(selected) == 0:
                selected.append(cand)
                continue
            # Check correlation with all selected
            corrs = [train_rets[[cand, s]].corr().iloc[0, 1] for s in selected]
            if max(corrs) < 0.5:
                selected.append(cand)
            if len(selected) >= 10:
                break

        print(f"    Selected {len(selected)} strategies:")
        for i, s in enumerate(selected, 1):
            t, d, sh = train_stats[s]
            corrs = [train_rets[[s, other]].corr().iloc[0, 1] for other in selected[:i-1]] if i > 1 else []
            corr_str = f", max corr {max(corrs):.2f}" if corrs else ""
            print(f"      {i}. {s:<18} (TRAIN Sh {sh:.2f}, return {t:+.1f}%{corr_str})")

        # Step 3: Equal weight combine, apply on TEST with fee
        test_combined = test_rets[selected].mean(axis=1)
        # Fee: assume one rebalance per month
        monthly_switches = len(test_rets) / 30
        fee_total = monthly_switches * FEE * 0.5
        test_combined_net = test_combined - (FEE * 0.5 / 30)  # daily fee accrual

        ct, cdd, csh = stats(test_combined_net)

        # B&H BTC
        if "BTC" in df.columns:
            bh_daily = rets.loc[test_mask, "BTC"]
            bht, bhdd, bhsh = stats(bh_daily)
        else:
            bht, bhdd, bhsh = 0, 0, 0

        print(f"\n  Step 3: Ensemble on TEST (with fee)")
        print(f"    {'Ensemble':<24} {ct:>+10.1f}%  DD {cdd:>5.1f}%  Sh {csh:>5.2f}")
        print(f"    {'B&H BTC':<24} {bht:>+10.1f}%  DD {bhdd:>5.1f}%  Sh {bhsh:>5.2f}")
        print(f"    {'Excess':<24} {ct-bht:>+10.1f}%")

        # Step 4: Show per-strategy on TEST for comparison
        print(f"\n  Step 4: Selected strategies on TEST (individual)")
        for s in selected:
            st, sd, ss = stats(test_rets[s])
            print(f"    {s:<18} {st:>+10.1f}%  DD {sd:>5.1f}%  Sh {ss:>5.2f}")

        # Step 5: Correlation matrix of selected
        print(f"\n  Step 5: Correlation matrix (TRAIN)")
        corr_mat = train_rets[selected].corr()
        print("    " + " ".join(f"{s[:8]:>9}" for s in selected))
        for s1 in selected:
            row = f"    {s1[:8]:>9} "
            for s2 in selected:
                row += f"{corr_mat.loc[s1, s2]:>9.2f} "
            print(row)


if __name__ == "__main__":
    main()
