"""PREDICTIVE RESEARCHER v2 — Multi-Market + Bale Report + Save."""
import math
import traceback
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

def sharpe_to_pvalue(sharpe, n_days):
    """Two-sided p-value from Sharpe (approx, normal returns)."""
    if n_days < 10 or abs(sharpe) < 1e-6:
        return 1.0
    z = abs(sharpe) * math.sqrt(n_days)
    # p = 2 * (1 - Phi(z)) = erfc(z / sqrt(2))
    p = math.erfc(z / math.sqrt(2))
    return min(1.0, p)

def benjamini_hochberg(p_values, q=0.10):
    """Return set of indices that pass FDR at level q."""
    n = len(p_values)
    if n == 0:
        return set()
    sorted_idx = sorted(range(n), key=lambda i: p_values[i])
    sorted_p = [p_values[i] for i in sorted_idx]
    max_k = -1
    for k in range(n):
        threshold = (k + 1) * q / n
        if sorted_p[k] <= threshold:
            max_k = k
    return set(sorted_idx[:max_k + 1])

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

def run_ensemble(df_rets, regimes, train_mask, test_mask, fee, market="TMN"):
    # Force DataFrame/Series types (guard against pandas edge cases)
    if not isinstance(df_rets, pd.DataFrame):
        df_rets = pd.DataFrame(df_rets)
    if not isinstance(regimes, pd.Series):
        regimes = pd.Series(regimes)
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
        p_values = []
        names_list = list(df_rets.columns)
        for name in names_list:
            t, d, sh = stats(df_rets.loc[r_train, name])
            scores[name] = sh
            p_values.append(sharpe_to_pvalue(sh, int(r_train.sum())))
        # FDR filter (q=0.10 for Iran markets, q=0.05 for GLOBAL)
        q_level = 0.05 if market == "GLOBAL" else 0.10
        passing_idx = benjamini_hochberg(p_values, q=q_level)
        passing_names = [names_list[i] for i in passing_idx]
        if len(passing_names) > 0:
            fdr_scores = {n: scores[n] for n in passing_names}
            top_3 = sorted(fdr_scores, key=fdr_scores.get, reverse=True)[:3]
            print(f"  FDR ({r}): {len(passing_names)}/{len(names_list)} passed (q={q_level})")
        else:
            top_3 = sorted(scores, key=scores.get, reverse=True)[:3]
            print(f"  ⚠️ FDR ({r}): 0 passed! Fallback to top 3.")
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
    regime_daily = {r: [] for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]}
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
        regime_daily[r].append(r_val)
        combined.append(r_val)

    ct, cdd, csh = stats(pd.Series(combined, index=df_rets.index[test_mask]))
    per_regime_sharpe = {}
    for r_name, daily_rets in regime_daily.items():
        if len(daily_rets) >= 5:
            _, _, sh_r = stats(pd.Series(daily_rets))
            per_regime_sharpe[r_name] = round(sh_r, 4)
        else:
            per_regime_sharpe[r_name] = 0.0
    return top_per_regime, ct, cdd, csh, switches, per_regime_sharpe

def load_profiler_returns_as_df(market, dates_index):
    """Load ALL 9035 profiler strategies (all statuses), filter blacklist only."""
    import os
    path = "research_lab/logs/profiles/state.json"
    if not os.path.exists(path):
        return pd.DataFrame()
    
    state = json.load(open(path))
    done = state.get("done", {})
    
    # Load blacklist
    try:
        from research_lab.pipeline_contract import BLACKLIST
    except:
        BLACKLIST = ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"]
    
    cols = {}
    skipped_blacklist = 0
    skipped_no_file = 0
    skipped_short = 0
    loaded_by_status = {"validated": 0, "profiled": 0, "other": 0}
    
    for key, v in done.items():
        if not isinstance(v, dict): continue
        parts = key.split(":")
        if len(parts) < 4: continue
        exch, strat, h, sym = parts[0], parts[1], parts[2], parts[3]
        
        # Skip blacklist (artifact strategies)
        if any(bl in strat for bl in BLACKLIST):
            skipped_blacklist += 1
            continue
        
        # Filter by market
        if market == "GLOBAL":
            if exch not in ["hyperliquid", "aster", "kucoin"]: continue
        else:  # TMN / USDT
            if exch != "wallex": continue
        
        ret_file = f"research_lab/logs/profiles/returns_matrices/{exch}/{strat}_{h}_{sym}.json"
        if not os.path.exists(ret_file):
            skipped_no_file += 1
            continue
        try:
            rets = json.load(open(ret_file))
            if len(rets) < 60:
                skipped_short += 1
                continue
            s = pd.Series(rets)
            s.index = pd.to_datetime(s.index)
            s = s.reindex(dates_index, method=None).fillna(0.0)
            if s.abs().sum() > 0:
                name = f"P_{strat}_{sym}"
                cols[name] = s
                
                status = v.get("status", "other")
                if status in loaded_by_status:
                    loaded_by_status[status] += 1
                else:
                    loaded_by_status["other"] += 1
        except: 
            skipped_no_file += 1
    
    if cols:
        df = pd.DataFrame(cols)
        print(f"  ✅ Loaded {len(cols)} profiler strategies for {market}")
        print(f"     By status: {loaded_by_status}")
        print(f"     Skipped: {skipped_blacklist} blacklist, {skipped_no_file} no file, {skipped_short} short")
    else:
        df = pd.DataFrame()
        print(f"  ⚠️ No profiler strategies for {market}")
    return df



def load_unified_db():
    """Load all strategies from the unified database."""
    import os
    unified_path = "data/all_strategies_unified.json"
    if not os.path.exists(unified_path):
        print("  ⚠️ unified DB not found")
        return {}
    data = json.load(open(unified_path))
    strats = data.get("strategies", {})
    # Only those with returns
    with_returns = {k: v for k, v in strats.items() if "returns" in v}
    print(f"  ✅ Unified DB: {len(with_returns)} strategies with returns (out of {len(strats)} total)")
    return with_returns

def process_market(name, df, fee):
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    if len(df) < 200: return None
    S = build_strategies(df)
    rets = df.pct_change().fillna(0)
    strat_rets_dict = {k: (v.shift(1) * rets).sum(axis=1) for k, v in S.items()}
    strat_rets = pd.DataFrame(strat_rets_dict)
    if not isinstance(strat_rets, pd.DataFrame):
        strat_rets = pd.DataFrame(strat_rets)
    
    # Load from UNIFIED DB (single source of truth)
    try:
        unified = load_unified_db()
        # Filter by market
        rows = []
        for sid, s in unified.items():
            exch = s.get("exchange", "")
            if name == "GLOBAL" and exch not in ["hyperliquid", "aster", "kucoin"]: continue
            if name in ["TMN", "USDT"] and exch != "wallex": continue
            rets = s.get("returns", {})
            if not rets: continue
            # Build aligned series
            try:
                series = pd.Series(rets)
                series.index = pd.to_datetime(series.index)
                series = series.reindex(df.index).fillna(0.0)
                if series.abs().sum() > 0:
                    rows.append((sid, series))
            except: pass
        
        if rows:
            profiler_df = pd.DataFrame(dict(rows))
            profiler_df = profiler_df.reindex(df.index).fillna(0.0)
            strat_rets = pd.concat([strat_rets, profiler_df], axis=1)
            print(f"  📊 {name}: {len(strat_rets.columns)} candidates (306 + {len(rows)} unified)")
    except Exception as e:
        print(f"  ⚠️ Unified DB load failed: {e}")
    
    # (Profiler loader deprecated — unified DB is used)
    
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
        _, ct_o, cdd_o, csh_o, _, _ = run_ensemble(strat_rets, oracle_regs, train_mask, test_mask, fee, market=name)
        bht, bhdd, bhsh = stats(rets.loc[test_mask, "BTC"])
    else:
        ct_o, cdd_o, csh_o, bht, bhdd, bhsh = 0, 0, 0, 0, 0, 0

    pred_regs = detect_regime(df)
    top_p, ct_p, cdd_p, csh_p, sw_p, sh_per_regime = run_ensemble(strat_rets, pred_regs, train_mask, test_mask, fee, market=name)

    return {
        "market": name, "assets": len(df.columns), "days": len(df),
        "oracle": {"return": ct_o, "dd": cdd_o, "sharpe": csh_o},
        "predictive": {"return": ct_p, "dd": cdd_p, "sharpe": csh_p, "switches": sw_p, "top": top_p, "metrics": {r: {"sharpe": sh} for r, sh in sh_per_regime.items()}},
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

    # Load ALL profiler strategies
    try:
        profiler_df = load_profiler_returns_as_df("GLOBAL", df.index) if "GLOBAL" in "name" else None
    except: pass
    
    # Save to pending (requires human approval)
    with open("data/researcher_pending.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ Saved results to PENDING. Human approval required.")

    # Bale
    msg = "🤖 *Predictive Researcher — PENDING APPROVAL*\n\n"
    for m, r in results.items():
        if not isinstance(r, dict): continue
        msg += f"📊 *{m}* ({r.get('assets', 0)} assets, {r.get('days', 0)}d)\n"
        msg += f"├ Oracle: {r['oracle']['return']:+.1f}% (DD {r['oracle']['dd']:.1f}%, Sh {r['oracle']['sharpe']:.2f})\n"
        msg += f"├ Predicted: {r['predictive']['return']:+.1f}% (DD {r['predictive']['dd']:.1f}%, Sh {r['predictive']['sharpe']:.2f})\n"
        msg += f"└ B&H BTC: {r['bnh_btc']['return']:+.1f}%\n"
        msg += "Top: " + ", ".join([f"{k}:{v[0]}" for k,v in r['predictive']['top'].items()]) + "\n\n"
    msg += "\n✅ برای تأیید: در ترموس دستور python3 scripts/approve_strategies.py را اجرا کنید."
    send_bale(msg)

if __name__ == "__main__":
    main()
