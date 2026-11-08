"""Test different predictive regime detectors to see which one gets closest to Oracle."""
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
        S[f"mom{n}"] = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
    for f, s in [(20,50),(50,200)]:
        sig = df.rolling(f).mean() > df.rolling(s).mean()
        rank = (df.rolling(f).mean()/df.rolling(s).mean()).where(sig).rank(axis=1, ascending=False)
        S[f"ma{f}_{s}"] = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
    delta = df.diff()
    for p in [14, 21]:
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        sig = rsi < 30
        rank = rsi.where(sig).rank(axis=1, ascending=True)
        S[f"rsi{p}"] = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
    for p in [15, 30]:
        ma = df.rolling(p).mean()
        sd = df.rolling(p).std()
        sig = df < ma - 2*sd
        z = (df - ma) / sd
        rank = z.where(sig).rank(axis=1, ascending=True)
        S[f"bb{p}"] = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
    for dip in [10, 20]:
        sig = df.pct_change(5) < -dip/100
        rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
        S[f"btfd{dip}"] = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
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
    print(" PREDICTIVE REGIME DETECTORS — Can we approximate the Oracle?")
    print("="*100)

    for market in ["TMN"]: # Focus on TMN where Oracle shined
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

        # 1. Oracle (Future 30d)
        btc_future = df["BTC"].shift(-30) / df["BTC"] - 1
        oracle_reg = pd.Series("FLAT", index=df.index)
        oracle_reg[btc_future > 0.15] = "BULL_STRONG"
        oracle_reg[(btc_future > 0.05) & (btc_future <= 0.15)] = "BULL"
        oracle_reg[(btc_future > -0.05) & (btc_future <= 0.05)] = "FLAT"
        oracle_reg[(btc_future > -0.15) & (btc_future <= -0.05)] = "BEAR"
        oracle_reg[btc_future <= -0.15] = "CRASH"

        # 2. Detector A: Past 7d momentum
        past_7d = df["BTC"].pct_change(7)
        reg_a = pd.Series("FLAT", index=df.index)
        reg_a[past_7d > 0.05] = "BULL_STRONG"
        reg_a[(past_7d > 0.02) & (past_7d <= 0.05)] = "BULL"
        reg_a[(past_7d > -0.02) & (past_7d <= 0.02)] = "FLAT"
        reg_a[(past_7d > -0.05) & (past_7d <= -0.02)] = "BEAR"
        reg_a[past_7d <= -0.05] = "CRASH"

        # 3. Detector B: Volatility + Trend
        rets_14 = df["BTC"].pct_change()
        vol = rets_14.rolling(14).std() * np.sqrt(365)
        ma50 = df["BTC"].rolling(50).mean()
        reg_b = pd.Series("FLAT", index=df.index)
        reg_b[(df["BTC"] > ma50) & (vol < 1.0)] = "BULL_STRONG"
        reg_b[(df["BTC"] > ma50) & (vol >= 1.0)] = "BULL"
        reg_b[(df["BTC"] <= ma50) & (vol < 1.0)] = "FLAT"
        reg_b[(df["BTC"] <= ma50) & (vol >= 1.0) & (vol < 2.0)] = "BEAR"
        reg_b[(df["BTC"] <= ma50) & (vol >= 2.0)] = "CRASH"

        detectors = [("Oracle (Future)", oracle_reg), ("Past 7d Mom", reg_a), ("Vol + Trend", reg_b)]
        
        for name, regs in detectors:
            top_per_regime = {}
            for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
                r_mask = train_mask & (regs == r)
                if r_mask.sum() < 10: 
                    top_per_regime[r] = ["bh_BTC"]
                    continue
                scores = {n: stats(train_rets.loc[r_mask, n])[2] for n in S}
                top_per_regime[r] = sorted(scores, key=scores.get, reverse=True)[:3]

            combined = []
            cur_strats = []
            switches = 0
            for d in test_rets.index:
                r = regs.loc[d]
                strats = top_per_regime.get(r, ["bh_BTC"])
                r_val = test_rets.loc[d, strats].mean()
                if set(strats) != set(cur_strats):
                    r_val -= FEE * 0.5
                    switches += 1
                    cur_strats = strats
                combined.append(r_val)
                
            ct, cdd, csh = stats(pd.Series(combined, index=test_rets.index))
            print(f"  {name:<16} -> Return {ct:>+8.1f}% | DD {cdd:>5.1f}% | Sharpe {csh:>5.2f} | Switches: {switches}")

if __name__ == "__main__":
    main()
