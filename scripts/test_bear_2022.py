"""Test Researcher's regime detection and ensemble on 2022 bear market."""
import sys, os, json
import pandas as pd
import numpy as np

FEE = 0.0005  # Global fee (approx)

def build_strategies(df):
    S = {}
    rets = df.pct_change()
    # Momentum
    for n in [10, 20, 30, 45, 60]:
        mom = df.pct_change(n)
        ma50 = df.rolling(50).mean()
        sig = (mom > 0) & (df > ma50)
        rank = mom.where(sig).rank(axis=1, ascending=False)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"mom{n}"] = w
    # BB MR
    for p in [15, 30]:
        ma = df.rolling(p).mean(); sd = df.rolling(p).std()
        sig = df < (ma - 2*sd)
        z = (df - ma) / sd
        rank = z.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"bb{p}"] = w
    # BTFD
    for dip in [10, 20]:
        sig = df.pct_change(5) < -dip/100
        rank = df.pct_change(5).where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"btfd{dip}"] = w
    # RSI MR
    delta = df.diff()
    up = delta.clip(lower=0); down = -delta.clip(upper=0)
    for p in [14, 21]:
        rsi = 100 - 100 / (1 + up.ewm(alpha=1/p, adjust=False).mean() / down.ewm(alpha=1/p, adjust=False).mean())
        sig = rsi < 30
        rank = rsi.where(sig).rank(axis=1, ascending=True)
        w = (rank <= 3).astype(float).div((rank <= 3).sum(axis=1), axis=0).fillna(0)
        S[f"rsi{p}"] = w
    # B&H
    for a in df.columns:
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        w[a] = 1.0
        S[f"bh_{a}"] = w
    return S

def detect_regime(df):
    """v2 — Improved regime detection with drawdown + distance from MA50."""
    if "BTC" not in df.columns: return pd.Series("FLAT", index=df.index)
    btc = df["BTC"]
    rets = btc.pct_change()
    vol = rets.rolling(14).std() * np.sqrt(365)
    ma50 = btc.rolling(50).mean()
    ath = btc.cummax()
    drawdown = (btc / ath - 1) * 100  # Negative if below ATH
    distance_ma50 = (btc / ma50 - 1) * 100
    
    regs = pd.Series("FLAT", index=df.index)
    
    # Priority order: CRASH > BEAR > BULL > FLAT
    # CRASH: vol very high OR deep drawdown
    crash_mask = (vol > 1.5) | (drawdown < -50)
    # BEAR: distance from MA50 negative OR high vol OR drawdown moderate
    bear_mask = (distance_ma50 < -10) | (vol > 0.8) | (drawdown < -25)
    # BULL_STRONG: above MA50 + strong
    bull_strong_mask = (distance_ma50 > 10) & (vol < 1.0)
    # BULL: above MA50
    bull_mask = (distance_ma50 > 0)
    
    regs[bull_mask] = "BULL"
    regs[bull_strong_mask] = "BULL_STRONG"
    regs[bear_mask] = "BEAR"
    regs[crash_mask] = "CRASH"
    return regs

def stats(daily):
    if len(daily) == 0: return 0, 0, 0
    eq = (1 + daily).cumprod()
    dd = ((eq.cummax() - eq) / eq.cummax()).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1] - 1) * 100, dd, (m / s) * np.sqrt(365) if s > 0 else 0

def main():
    print("="*80)
    print(" BEAR MARKET TEST — 2022 (LUNA + FTX + Bear)")
    print("="*80)
    
    raw = json.load(open("data/crypto_2022_bear.json"))
    # Strip -USD from keys
    cleaned = {k.replace("-USD", ""): v for k, v in raw.items()}
    df = pd.DataFrame(cleaned)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    rets = df.pct_change().fillna(0)
    
    print(f"\nData: {len(df)} days ({df.index[0].date()} → {df.index[-1].date()})")
    print(f"Assets: {len(df.columns)}")
    
    # Regime distribution
    regimes = detect_regime(df)
    from collections import Counter
    counts = Counter(regimes)
    print(f"\n📊 Regime distribution in 2022:")
    for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        c = counts.get(r, 0)
        print(f"  {r:<14} {c:>3} days ({c/len(df)*100:.1f}%)")
    
    # BTC performance
    btc_ret = (df["BTC"].iloc[-1] / df["BTC"].iloc[0] - 1) * 100
    print(f"\n📈 BTC return in 2022: {btc_ret:+.1f}%")
    print(f"   Start: ${df['BTC'].iloc[0]:,.0f}")
    print(f"   End:   ${df['BTC'].iloc[-1]:,.0f}")
    
    # Build strategies
    S = build_strategies(df)
    strat_rets = pd.DataFrame({k: (v.shift(1) * rets).sum(axis=1) for k, v in S.items()})
    
    # Use same top strategies from current researcher (from current JSON)
    try:
        current = json.load(open("data/researcher_predictive_results.json"))
        top_per_regime = current.get("GLOBAL", {}).get("predictive", {}).get("top", {})
        print(f"\n✅ Loaded current Researcher strategies for GLOBAL")
    except:
        top_per_regime = {"BEAR": ["rsi35_35", "rsi21_30", "bb10_1.5"], 
                          "CRASH": ["bh_BTC"], "FLAT": ["btfd30_h5"]}
        print(f"⚠️ Using fallback strategies")
    
    # Apply strategies
    combined = []
    cur_strats = []
    switches = 0
    regime_log = []
    for d in df.index[1:]:
        r = regimes.loc[d]
        if r == "UNKNOWN": 
            combined.append(0)
            continue
        strats = [s for s in top_per_regime.get(r, ["bh_BTC"]) if s in strat_rets.columns]
        if not strats:
            strats = ["bh_BTC"]
        r_val = strat_rets.loc[d, strats].mean() if d in strat_rets.index else 0
        if set(strats) != set(cur_strats):
            r_val -= FEE * 0.5
            switches += 1
            cur_strats = strats
        combined.append(r_val)
        regime_log.append(r)
    
    comb_s = pd.Series(combined, index=df.index[1:])
    ct, cdd, csh = stats(comb_s)
    
    bh_daily = rets["BTC"].iloc[1:]
    bht, bhdd, bhsh = stats(bh_daily)
    
    print(f"\n{'='*80}")
    print(" RESULTS on 2022 BEAR MARKET")
    print("="*80)
    print(f"  {'Strategy':<20} {'Return':>10} {'DD':>8} {'Sharpe':>8}")
    print(f"  {'-'*50}")
    print(f"  {'Researcher Ensemble':<20} {ct:>+9.1f}% {cdd:>7.1f}% {csh:>7.2f}")
    print(f"  {'B&H BTC':<20} {bht:>+9.1f}% {bhdd:>7.1f}% {bhsh:>7.2f}")
    print(f"\n  Switches: {switches}")
    
    # Kill switch check
    if ct < -10:
        print(f"\n  ⚠️ Kill Switch WOULD HAVE TRIGGERED (Return {ct:.1f}% < -10%)")
    else:
        print(f"\n  ✅ Kill Switch NOT triggered (Return {ct:.1f}% > -10%)")
    
    print(f"\n  Verdict:")
    if ct > bht:
        print(f"  ✅ Ensemble BEAT B&H in bear market ({ct-bht:+.1f}%)")
    elif ct > -10:
        print(f"  🟡 Ensemble survived bear market (return > -10%)")
    else:
        print(f"  ❌ Ensemble FAILED in bear market")

if __name__ == "__main__":
    main()
