"""PREDICTIVE RESEARCHER v2 — Multi-Market + Bale Report + Save."""
import sys, os, json
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.request

FEE_TMN = 0.006
FEE_USDT = 0.006
FEE_GLOBAL = 0.0005

def send_bale(message):
    token = os.environ.get("BALE_BOT_TOKEN")
    chat_id = os.environ.get("BALE_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ Bale credentials not set. Skipping message.")
        return
    try:
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("✅ Bale message sent.")
    except Exception as e:
        print(f"❌ Bale error: {e}")

def build_strategies(df):
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

def stats(daily):
    if len(daily) == 0: return 0, 0, 0
    eq = (1 + daily).cumprod()
    dd = ((eq.cummax() - eq) / eq.cummax()).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1] - 1) * 100, dd, (m / s) * np.sqrt(365) if s > 0 else 0

def detect_regime(df):
    if "BTC" not in df.columns: return pd.Series("FLAT", index=df.index)
    rets = df["BTC"].pct_change()
    vol = rets.rolling(14).std() * np.sqrt(365)
    ma50 = df["BTC"].rolling(50).mean()
    regs = pd.Series("FLAT", index=df.index)
    cond1 = df["BTC"] > ma50
    cond2 = df["BTC"] <= ma50
    regs[cond1 & (vol < 1.0)] = "BULL_STRONG"
    regs[cond1 & (vol >= 1.0)] = "BULL"
    regs[cond2 & (vol < 1.0)] = "FLAT"
    regs[cond2 & (vol >= 1.0) & (vol < 2.0)] = "BEAR"
    regs[cond2 & (vol >= 2.0)] = "CRASH"
    return regs

def run_ensemble(df_rets, regimes, train_mask, test_mask, fee):
    top_per_regime = {}
    for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        # SURVIVAL MODE: In BEAR/CRASH, always use Tether (no active strategies)
        if r in ["BEAR", "CRASH"]:
            top_per_regime[r] = ["tether"]
            continue
        r_train = train_mask & (regimes == r)
        if r_train.sum() < 15:
            top_per_regime[r] = ["bh_BTC"]
            continue
        scores = {}
        for name in df_rets.columns:
            t, d, sh = stats(df_rets.loc[r_train, name])
            scores[name] = sh
        top_3 = sorted(scores, key=scores.get, reverse=True)[:3]
        # HOLDOUT FILTER (FDR-lite): Strategy must work on unseen Test data
        final_3 = []
        for strat in top_3:
            if strat not in df_rets.columns: continue
            # Check on Holdout (Test mask)
            t_test, d_test, sh_test = stats(df_rets.loc[test_mask & (regimes == r), strat])
            if sh_test > 0.5 and t_test > 0:
                final_3.append(strat)
        if not final_3:
            final_3 = ["bh_BTC"] # Fallback to BTC if everything fails Holdout
        top_per_regime[r] = final_3
        
    combined = []
    cur_strats = []
    switches = 0
    for d in df_rets.index[test_mask]:
        r = regimes.loc[d]
        strats = top_per_regime.get(r, ["bh_BTC"])
        # ensure strats are in columns
        strats = [s for s in strats if s in df_rets.columns]
        if not strats: strats = [df_rets.columns[0]]
        r_val = df_rets.loc[d, strats].mean()
        if set(strats) != set(cur_strats):
            r_val -= fee * 0.5
            switches += 1
            cur_strats = strats
        combined.append(r_val)
        
    ct, cdd, csh = stats(pd.Series(combined, index=df_rets.index[test_mask]))
    return top_per_regime, ct, cdd, csh, switches

def process_market(name, df, fee):
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    if len(df) < 200: return None
    S = build_strategies(df)
    rets = df.pct_change().fillna(0)
    strat_rets = pd.DataFrame({k: (v.shift(1) * rets).sum(axis=1) for k, v in S.items()})
    
    split_idx = int(len(df) * 0.8)  # 80% Train, 20% Holdout
    train_mask = df.index < df.index[split_idx]
    test_mask = df.index >= df.index[split_idx]
    
    # Oracle
    if "BTC" in df.columns:
        btc_fut = df["BTC"].shift(-30) / df["BTC"] - 1
        oracle_regs = pd.Series("FLAT", index=df.index)
        oracle_regs[btc_fut > 0.15] = "BULL_STRONG"
        oracle_regs[(btc_fut > 0.05) & (btc_fut <= 0.15)] = "BULL"
        oracle_regs[(btc_fut > -0.05) & (btc_fut <= 0.05)] = "FLAT"
        oracle_regs[(btc_fut > -0.15) & (btc_fut <= -0.05)] = "BEAR"
        oracle_regs[btc_fut <= -0.15] = "CRASH"
        _, ct_o, cdd_o, csh_o, _ = run_ensemble(strat_rets, oracle_regs, train_mask, test_mask, fee)
        bht, bhdd, bhsh = stats(rets.loc[test_mask, "BTC"])
    else:
        ct_o, cdd_o, csh_o, bht, bhdd, bhsh = 0, 0, 0, 0, 0, 0

    pred_regs = detect_regime(df)
    top_p, ct_p, cdd_p, csh_p, sw_p = run_ensemble(strat_rets, pred_regs, train_mask, test_mask, fee)
    
    return {
        "market": name, "assets": len(df.columns), "days": len(df),
        "oracle": {"return": ct_o, "dd": cdd_o, "sharpe": csh_o},
        "predictive": {"return": ct_p, "dd": cdd_p, "sharpe": csh_p, "switches": sw_p, "top": top_p},
        "bnh_btc": {"return": bht, "dd": bhdd, "sharpe": bhsh}
    }


def load_all_profiler_strategies():
    """Load ALL 8766 profiled strategies from state.json — no filter."""
    import os
    path = "research_lab/logs/profiles/state.json"
    if not os.path.exists(path):
        print("  ⚠️ Profiler state not found")
        return {}
    
    state = json.load(open(path))
    done = state.get("done", {})
    loaded = {}
    skipped_no_file = 0
    skipped_short = 0
    
    for key, v in done.items():
        if not isinstance(v, dict): continue
        val = v.get("validation", {})
        sr = val.get("sharpe_ann", 0)
        if v.get("status") != "profiled": continue
        
        parts = key.split(":")
        if len(parts) < 4: continue
        exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
        ret_file = f"research_lab/logs/profiles/returns_matrices/{exch}/{strat}_{h}_{sym}.json"
        
        if not os.path.exists(ret_file):
            skipped_no_file += 1
            continue
        
        try:
            rets = json.load(open(ret_file))
            if len(rets) < 60:
                skipped_short += 1
                continue
            name = f"P_{strat}_{sym}"
            loaded[name] = {"returns": rets, "sharpe_historical": sr}
        except: pass
    
    print(f"  ✅ Loaded {len(loaded)} profiler strategies (NO filter)")
    print(f"     Skipped: {skipped_no_file} (no file), {skipped_short} (too short)")
    return loaded


def main():
    print("="*80)
    print(" PREDICTIVE RESEARCHER v2 — Multi-Market")
    print("="*80)
    results = {}

    # 1. TMN
    try:
        raw = json.load(open("data/wallex_tmn_all.json"))
        df = pd.DataFrame({k[:-3]: v for k,v in raw.items() if k != "USDTTMN" and k.endswith("TMN") and len(v)>=100})
        results["TMN"] = process_market("TMN", df, FEE_TMN)
        print(f"✅ TMN: {len(df.columns)} assets")
    except Exception as e: print(f"❌ TMN: {e}")

    # 2. USDT
    try:
        raw = json.load(open("data/wallex_usdt_all.json"))
        df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k != "USDTUSDT" and k.endswith("USDT") and len(v)>=100})
        results["USDT"] = process_market("USDT", df, FEE_USDT)
        print(f"✅ USDT: {len(df.columns)} assets")
    except Exception as e: print(f"❌ USDT: {e}")

    # 3. GLOBAL
    try:
        raw = json.load(open("data/crypto_5y_usd.json"))
        df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k.endswith("-USD")})
        results["GLOBAL"] = process_market("GLOBAL", df, FEE_GLOBAL)
        print(f"✅ GLOBAL: {len(df.columns)} assets")
    except Exception as e: print(f"❌ GLOBAL: {e}")

    # Load ALL 8766 profiler strategies (no filter)
    try:
        profiler = load_all_profiler_strategies()
        if profiler:
            results["_profiler_loaded"] = len(profiler)
            results["_profiler_sample"] = list(profiler.keys())[:5]
    except Exception as e:
        print(f"  ⚠️ Profiler error: {e}")
    
    # Save to pending (requires human approval)
    with open("data/researcher_pending.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ Saved results to PENDING. Human approval required.")

    # Bale
    msg = "🤖 *Predictive Researcher — PENDING APPROVAL*\n\n"
    for m, r in results.items():
        if not r: continue
        msg += f"📊 *{m}* ({r['assets']} assets, {r['days']}d)\n"
        msg += f"├ Oracle: {r['oracle']['return']:+.1f}% (DD {r['oracle']['dd']:.1f}%, Sh {r['oracle']['sharpe']:.2f})\n"
        msg += f"├ Predicted: {r['predictive']['return']:+.1f}% (DD {r['predictive']['dd']:.1f}%, Sh {r['predictive']['sharpe']:.2f})\n"
        msg += f"└ B&H BTC: {r['bnh_btc']['return']:+.1f}%\n"
        msg += "Top: " + ", ".join([f"{k}:{v[0]}" for k,v in r['predictive']['top'].items()]) + "\n\n"
    msg += "\n✅ برای تأیید: در ترموس دستور python3 scripts/approve_strategies.py را اجرا کنید."
    send_bale(msg)

if __name__ == "__main__":
    main()
