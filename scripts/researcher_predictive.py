"""PREDICTIVE RESEARCHER — Automated Discovery of Regime-Aware Ensembles."""
import sys, os, json
import pandas as pd
import numpy as np
from datetime import datetime

FEE = 0.006

def build_strategies(df):
    """Build 306 strategies via parameter sweep."""
    S = {}
    rets = df.pct_change()
    # 1. Momentum (110)
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
        sig = df > df.rolling(n).max().shift(1)
        rank = rets.where(sig).rank(axis=1, ascending=False)
        for top in [1, 2, 3, 4, 5]:
            w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
            S[f"brk{n}_t{top}"] = w
    # 3. MA Cross (35)
    for f, s in [(5,20),(10,30),(20,50),(50,200),(100,200),(20,100),(30,90)]:
        sig = df.rolling(f).mean() > df.rolling(s).mean()
        rank = (df.rolling(f).mean()/df.rolling(s).mean()).where(sig).rank(axis=1, ascending=False)
        for top in [1, 2, 3, 4, 5]:
            w = (rank <= top).astype(float).div((rank <= top).sum(axis=1), axis=0).fillna(0)
            S[f"ma{f}_{s}_t{top}"] = w
    # 4. RSI MR (25)
    delta = df.diff()
    up = delta.clip(lower=0); down = -delta.clip(upper=0)
    for p in [7, 14, 21, 28, 35]:
        rsi = 100 - 100 / (1 + up.ewm(alpha=1/p, adjust=False).mean() / down.ewm(alpha=1/p, adjust=False).mean())
        for th in [20, 25, 30, 35, 40]:
            sig = rsi < th
            rank = rsi.where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"rsi{p}_{th}"] = w
    # 5. BB MR (25)
    for p in [10, 15, 20, 30, 40]:
        ma = df.rolling(p).mean(); sd = df.rolling(p).std()
        for ns in [1.5, 2, 2.5, 3, 3.5]:
            sig = df < (ma - ns * sd)
            z = (df - ma) / sd
            rank = z.where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"bb{p}_{ns}"] = w
    # 6. BTFD (15)
    for dip in [5, 10, 15, 20, 30]:
        for hold in [5, 10, 20]:
            sig = df.pct_change(5) < (-dip / 100)
            rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
            w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
            S[f"btfd{dip}_h{hold}"] = w
    # 7. Equal Weight (5)
    for n in [2, 3, 5, 8, 10]:
        cols = df.columns[:n]
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        w[cols] = 1.0 / n
        S[f"eq{n}"] = w
    # 8. B&H (10)
    for a in ["BTC","ETH","BNB","XRP","TRX","SOL","DOGE","ADA","LINK","AVAX"]:
        if a in df.columns:
            w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
            w[a] = 1.0
            S[f"bh_{a}"] = w
    return S

def stats(daily):
    if len(daily) == 0: return 0, 0, 0
    eq = (1 + daily).cumprod()
    dd = ((eq.cummax() - eq) / eq.cummax()).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1] - 1) * 100, dd, (m / s) * np.sqrt(365) if s > 0 else 0

def detect_regime(df, method="vol_trend"):
    rets = df["BTC"].pct_change()
    vol = rets.rolling(14).std() * np.sqrt(365)
    ma50 = df["BTC"].rolling(50).mean()
    
    regs = pd.Series("FLAT", index=df.index)
    if method == "vol_trend":
        cond1 = df["BTC"] > ma50
        cond2 = df["BTC"] <= ma50
        regs[cond1 & (vol < 1.0)] = "BULL_STRONG"
        regs[cond1 & (vol >= 1.0)] = "BULL"
        regs[cond2 & (vol < 1.0)] = "FLAT"
        regs[cond2 & (vol >= 1.0) & (vol < 2.0)] = "BEAR"
        regs[cond2 & (vol >= 2.0)] = "CRASH"
    return regs

def run_ensemble(df_rets, regimes, train_mask, test_mask):
    """Find Top-3 per regime on train, test on OOS."""
    top_per_regime = {}
    for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        r_train = train_mask & (regimes == r)
        if r_train.sum() < 15:
            top_per_regime[r] = ["bh_BTC"]
            continue
        scores = {}
        for name in df_rets.columns:
            t, d, sh = stats(df_rets.loc[r_train, name])
            scores[name] = sh
        best_3 = sorted(scores, key=scores.get, reverse=True)[:3]
        top_per_regime[r] = best_3
        
    combined = []
    cur_strats = []
    switches = 0
    for d in df_rets.index[test_mask]:
        r = regimes.loc[d]
        strats = top_per_regime.get(r, ["bh_BTC"])
        r_val = df_rets.loc[d, strats].mean()
        if set(strats) != set(cur_strats):
            r_val -= FEE * 0.5
            switches += 1
            cur_strats = strats
        combined.append(r_val)
        
    ct, cdd, csh = stats(pd.Series(combined, index=df.index[test_mask]))
    return top_per_regime, ct, cdd, csh, switches

def main():
    print("="*100)
    print(" PREDICTIVE RESEARCHER — AUTOMATED PIPELINE")
    print("="*100)
    
    market = "TMN" # Focus on Toman
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

    print(f"Market: {market} | Assets: {len(df.columns)} | Days: {len(df)}")

    # 1. Build Strategies
    S = build_strategies(df)
    print(f"Built {len(S)} strategies.")

    # 2. Honest Returns (shift 1)
    strat_rets = pd.DataFrame({name: (w.shift(1) * rets).sum(axis=1) for name, w in S.items()})

    # 3. Split (70% Train, 30% Test)
    split_idx = int(len(df) * 0.7)
    split_date = df.index[split_idx]
    train_mask = df.index < split_date
    test_mask = df.index >= split_date
    print(f"TRAIN: {train_mask.sum()}d | TEST: {test_mask.sum()}d | Split: {split_date.date()}")

    # 4. Oracle Test
    print("\n--- ORACLE TEST (Upper Bound) ---")
    btc_future_ret = df["BTC"].shift(-30) / df["BTC"] - 1
    oracle_regs = pd.Series("FLAT", index=df.index)
    oracle_regs[btc_future_ret > 0.15] = "BULL_STRONG"
    oracle_regs[(btc_future_ret > 0.05) & (btc_future_ret <= 0.15)] = "BULL"
    oracle_regs[(btc_future_ret > -0.05) & (btc_future_ret <= 0.05)] = "FLAT"
    oracle_regs[(btc_future_ret > -0.15) & (btc_future_ret <= -0.05)] = "BEAR"
    oracle_regs[btc_future_ret <= -0.15] = "CRASH"
    
    _, ct_o, cdd_o, csh_o, _ = run_ensemble(strat_rets, oracle_regs, train_mask, test_mask)
    bht, bhdd, bhsh = stats(rets.loc[test_mask, "BTC"])
    print(f"Oracle Ensemble: {ct_o:+.1f}% (DD {cdd_o:.1f}%, Sharpe {csh_o:.2f})")
    print(f"B&H BTC:         {bht:+.1f}% (DD {bhdd:.1f}%, Sharpe {bhsh:.2f})")

    # 5. Predictive Regime (Vol+Trend)
    print("\n--- PREDICTIVE REGIME (Vol+Trend) ---")
    pred_regs = detect_regime(df, "vol_trend")
    top_pred, ct_p, cdd_p, csh_p, sw_p = run_ensemble(strat_rets, pred_regs, train_mask, test_mask)
    print(f"Ensemble: {ct_p:+.1f}% (DD {cdd_p:.1f}%, Sharpe {csh_p:.2f}, Switches: {sw_p})")
    print(f"Gap to Oracle: {((ct_p/ct_o)-1)*100 if ct_o>0 else 0:+.1f}% of return captured.")

    # Save results
    results = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "market": market,
        "oracle": {"return": ct_o, "dd": cdd_o, "sharpe": csh_o},
        "predictive": {
            "return": ct_p, "dd": cdd_p, "sharpe": csh_p, "switches": sw_p,
            "top_per_regime": top_pred
        },
        "bnh_btc": {"return": bht, "dd": bhdd, "sharpe": bhsh}
    }
    json.dump(results, open("data/researcher_predictive_results.json", "w"), indent=2)
    print("\nSaved: data/researcher_predictive_results.json")

if __name__ == "__main__":
    main()
