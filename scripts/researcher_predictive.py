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
    
    # ═══════════════════════════════════════════════════════════════════
    # HIGH-FREQUENCY STRATEGIES (for more trades per regime)
    # ═══════════════════════════════════════════════════════════════════
    def equal_weight_portfolio(selected_assets):
        w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
        valid = [a for a in selected_assets if a in df.columns]
        if valid:
            for a in valid:
                w[a] = 1.0 / len(valid)
        return w
    
    # 1. GRID Trading (BTC & ETH only, high liquidity)
    for col in ["BTC", "ETH"]:
        if col not in df.columns: continue
        prices = df[col]
        low = prices.rolling(20).min()
        high = prices.rolling(20).max()
        mid = (low + high) / 2
        # Buy when price < 90% of mid (support)
        for pct in [0.90, 0.95]:
            sig = (prices < mid * pct).astype(float)
            w = pd.DataFrame(0.0, index=df.index, columns=df.columns)
            w[col] = sig
            S[f'grid_{col}_{int(pct*100)}'] = w
    
    # 2. FAST RSI Mean Reversion
    for p in [5, 7, 10, 14]:
        delta = df.diff()
        up = delta.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        down = -delta.clip(upper=0).ewm(alpha=1/p, adjust=False).mean()
        rsi = 100 - 100/(1 + up/down)
        for th in [25, 30]:
            sig = (rsi < th).astype(float)
            # Apply to all assets (oversold)
            top = sig.rank(axis=1, ascending=False).le(3).astype(float)
            w = top.div(top.sum(axis=1).replace(0, 1), axis=0).fillna(0)
            S[f'rsi_fast_{p}_{th}'] = w
    
    # 3. Bollinger Breakout (for trends)
    for n in [10, 20]:
        ma = df.rolling(n).mean()
        sd = df.rolling(n).std()
        for mult in [1.5, 2.0]:
            sig = (df > ma + mult*sd).astype(float)
            top = sig.rank(axis=1, ascending=False).le(3).astype(float)
            w = top.div(top.sum(axis=1).replace(0, 1), axis=0).fillna(0)
            S[f'bb_breakout_{n}_{mult}'] = w
    
    # 4. Donchian Breakout
    for n in [10, 20, 50]:
        sig = (df > df.rolling(n).max().shift(1)).astype(float)
        top = sig.rank(axis=1, ascending=False).le(3).astype(float)
        w = top.div(top.sum(axis=1).replace(0, 1), axis=0).fillna(0)
        S[f'donchian_breakout_{n}'] = w
    
    # 5. Z-Score Mean Reversion
    for n in [10, 20]:
        ma = df.rolling(n).mean()
        sd = df.rolling(n).std()
        z = (df - ma) / sd
        for th in [-1.5, -2.0]:
            sig = (z < th).astype(float)
            top = sig.rank(axis=1, ascending=False).le(3).astype(float)
            w = top.div(top.sum(axis=1).replace(0, 1), axis=0).fillna(0)
            S[f'zscore_{n}_{abs(th)}'] = w
    
    # 6. VWAP Reversion
    vol = pd.DataFrame(1.0, index=df.index, columns=df.columns)
    vwap = (df * vol).rolling(20).sum() / vol.rolling(20).sum()
    sig = (df < vwap * 0.98).astype(float)
    top = sig.rank(axis=1, ascending=False).le(3).astype(float)
    w = top.div(top.sum(axis=1).replace(0, 1), axis=0).fillna(0)
    S['vwap_rev_20'] = w
    
    # 7. Fast Momentum (for BULL_STRONG)
    for n in [3, 5, 7]:
        for th in [0.02, 0.03]:
            sig = (df.pct_change(n) > th).astype(float)
            top = sig.rank(axis=1, ascending=False).le(3).astype(float)
            w = top.div(top.sum(axis=1).replace(0, 1), axis=0).fillna(0)
            S[f'mom_fast_{n}_{int(th*100)}'] = w
    
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
    # Clip extreme daily returns (Wallex Iran can have >100% daily moves)
    daily = daily.clip(lower=-0.1, upper=0.1)
    eq = (1 + daily).cumprod()
    dd = ((eq.cummax() - eq) / eq.cummax()).max() * 100
    m, s = daily.mean(), daily.std()
    return (eq.iloc[-1] - 1) * 100, dd, (m / s) * np.sqrt(365) if s > 0 else 0


def build_combo_strategies(S, top_n=8):
    """Generate conditional combos from top base strategies."""
    if not S or len(S) < 2:
        return {}
    
    # Take top_n strategies by their standard deviation (as a proxy for signal quality)
    # In a real scenario, we'd rank by historical Sharpe, but here we use the first N for simplicity
    base_names = list(S.keys())[:top_n]
    combos = {}
    
    import itertools
    for (name1, name2) in itertools.combinations(base_names, 2):
        sig1 = S[name1]
        sig2 = S[name2]
        
        # Combo 1: AND (both must agree) - higher quality, fewer trades
        combos[f"combo_AND_{name1}_{name2}"] = (sig1 * sig2)
        
        # Combo 2: OR (either can trigger) - lower quality, more trades
        combos[f"combo_OR_{name1}_{name2}"] = ((sig1 + sig2) > 0).astype(float)
        
    return combos

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

def run_ensemble(df_rets, regimes, train_mask, test_mask, fee, market="TMN", max_strat_override=None):
    if not isinstance(df_rets, pd.DataFrame):
        df_rets = pd.DataFrame(df_rets)
    if not isinstance(regimes, pd.Series):
        regimes = pd.Series(regimes)

    top_per_regime = {}
    for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        if r in ["BEAR", "CRASH"]:
            top_per_regime[r] = {"tether": 1.0}
            continue

        r_train = train_mask & (regimes == r)
        if r_train.sum() < 15:
            top_per_regime[r] = {"bh_BTC": 1.0}
            continue

        scores = {}
        p_values = []
        names_list = list(df_rets.columns)
        for name in names_list:
            t, d, sh = stats(df_rets.loc[r_train, name])
            scores[name] = sh
            p_values.append(sharpe_to_pvalue(sh, int(r_train.sum())))

        q_level = 0.10
        passing_idx = benjamini_hochberg(p_values, q=q_level)
        passing_names = [names_list[i] for i in passing_idx]

        if not passing_names:
            top_per_regime[r] = {"bh_BTC": 1.0}
            continue

        final_strats = []
        for strat in passing_names:
            if strat not in df_rets.columns:
                continue
            if r in ["BULL_STRONG", "BULL", "FLAT"] and ("SHORT" in strat.upper() or "FLIP_SHORT" in strat.upper()):
                continue
            t_test, d_test, sh_test = stats(df_rets.loc[test_mask & (regimes == r), strat])
            if sh_test > 0.5 and t_test > 0:
                final_strats.append(strat)

        if not final_strats:
            top_per_regime[r] = {"bh_BTC": 1.0}
            continue

        # Sort by Sharpe (using recent 90-day window for high-frequency strategies)
        recent_window = 90  # 90 days
        recent_scores = {}
        for strat in final_strats:
            if strat not in df_rets.columns: continue
            # Calculate Sharpe on recent 90 days
            recent_data = df_rets.loc[r_train, strat].tail(recent_window)
            if len(recent_data) > 10:
                _, _, recent_sharpe = stats(recent_data)
                recent_scores[strat] = recent_sharpe
            else:
                recent_scores[strat] = scores[strat]  # fallback to full
        
        # Use recent scores for sorting (more weight to recent performance)
        sorted_final = sorted(final_strats, key=lambda s: recent_scores.get(s, 0), reverse=True)
        
        # Family mapping (for P_ strategies, we don't know, so they go to "other")
        def get_family(name):
            for p in ["bb", "mom", "rsi", "btfd", "brk", "bh_"]:
                if name.startswith(p): return p
            return "other"

        selected = []
        selected_returns = []
        
        # Family tracking
        used_families = {}

        # Market-specific filters (commission-aware) + A/B Test override
        if max_strat_override is not None:
            # A/B Test: use override value
            max_strategies = max_strat_override
            max_per_family = 3
            corr_threshold = 0.75
        elif market == "TMN":
            max_per_family = 2
            corr_threshold = 0.7
            max_strategies = 5    # Conservative default
        elif market == "USDT":
            max_per_family = 5
            corr_threshold = 0.9
            max_strategies = 20
        else:  # GLOBAL
            max_per_family = 3
            corr_threshold = 0.85
            max_strategies = 10

        for strat in sorted_final:
            if len(selected) >= max_strategies: break

            fam = get_family(strat)
            if used_families.get(fam, 0) >= max_per_family:
                continue

            is_complementary = True
            if selected_returns:
                recent = df_rets.loc[r_train, strat]
                for prev_ret in selected_returns:
                    if recent.std() > 0 and prev_ret.std() > 0:
                        corr = recent.corr(prev_ret)
                        if corr > corr_threshold:
                            is_complementary = False
                            break

            if is_complementary:
                selected.append((strat, scores[strat]))
                selected_returns.append(df_rets.loc[r_train, strat])
                used_families[fam] = used_families.get(fam, 0) + 1

        if not selected:
            top_per_regime[r] = {"bh_BTC": 1.0}
            continue

        # Weight by Sharpe (squared - more weight to top performers)
        positive = [(s, sh) for s, sh in selected if sh > 0.3]
        if not positive:
            top_per_regime[r] = {"bh_BTC": 1.0}
            continue
        scores_sq = [(s, sh**2) for s, sh in positive]
        total_sq = sum(sh_sq for _, sh_sq in scores_sq)
        if total_sq > 0:
            weighted = {s: round(sh_sq / total_sq, 4) for s, sh_sq in scores_sq}
        else:
            weighted = {s: round(1.0/len(positive), 4) for s, _ in positive}

        top_per_regime[r] = weighted
        print(f"  🧬 {r}: {len(weighted)} uncorrelated (from {len(final_strats)} final)")
        for s, w in weighted.items():
            print(f"      {s}: {w:.3f}")

    combined = []
    cur_strats = []
    switches = 0
    regime_daily = {r: [] for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]}

    for i, d in enumerate(df_rets.index[test_mask]):
        r = regimes.loc[d]
        strats_dict = top_per_regime.get(r, {"bh_BTC": 1.0})
        valid_strats = {s: w for s, w in strats_dict.items() if s in df_rets.columns}
        if not valid_strats:
            valid_strats = {df_rets.columns[0]: 1.0}
        total_w = sum(valid_strats.values())
        r_val = sum(df_rets.loc[d, s] * w for s, w in valid_strats.items()) / total_w if total_w > 0 else 0
        regime_daily[r].append(r_val)
        combined.append(r_val)
        current_keys = set(valid_strats.keys())
        if current_keys != set(cur_strats):
            r_val -= fee * 0.5
            switches += 1
            cur_strats = list(current_keys)

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
    
    # ── NEW: Load ALL files directly from returns_matrices/wallex (for strategies not in state.json)
    if market in ["TMN", "USDT"]:
        import glob
        wallex_dir = "research_lab/logs/profiles/returns_matrices/wallex"
        for fpath in glob.glob(f"{wallex_dir}/*_WALLEX.json"):
            fname = os.path.basename(fpath).replace("_WALLEX.json", "")
            if fname in cols: continue
            if any(bl in fname for bl in BLACKLIST): continue
            try:
                rets = json.load(open(fpath))
                if len(rets) < 60: continue
                s = pd.Series(rets)
                s.index = pd.to_datetime(s.index)
                s = s.reindex(dates_index).fillna(0.0)
                if s.abs().sum() > 0:
                    cols[fname] = s
            except: pass

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

def process_market(name, df, fee, max_strat_override=None):
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    if len(df) < 200: return None
    S = build_strategies(df)
    
    # NEW: Add conditional combo strategies
    combos = build_combo_strategies(S, top_n=8)
    S.update(combos)
    print(f"  🧬 Added {len(combos)} combo strategies")
    
    market_rets = df.pct_change().fillna(0)
    strat_rets_dict = {k: (v.shift(1) * market_rets).sum(axis=1) for k, v in S.items()}
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
        bht, bhdd, bhsh = stats(market_rets.loc[test_mask, "BTC"])
    else:
        ct_o, cdd_o, csh_o, bht, bhdd, bhsh = 0, 0, 0, 0, 0, 0

    pred_regs = detect_regime(df)
    # ═══════════════════════════════════════════════════════════════
    # A/B Test: دو بار run_ensemble با override های مختلف
    # ═══════════════════════════════════════════════════════════════
    
    # 1. Conservative (max 5)
    top_p_c, ct_p_c, cdd_p_c, csh_p_c, sw_p_c, sh_per_regime_c = run_ensemble(
        strat_rets, pred_regs, train_mask, test_mask, fee, market=name, 
        max_strat_override=5
    )
    
    # 2. Aggressive (max 15)
    top_p_a, ct_p_a, cdd_p_a, csh_p_a, sw_p_a, sh_per_regime_a = run_ensemble(
        strat_rets, pred_regs, train_mask, test_mask, fee, market=name, 
        max_strat_override=15
    )
    
    # استفاده از Conservative برای خروجی اصلی
    top_p = top_p_c
    ct_p, cdd_p, csh_p, sw_p = ct_p_c, cdd_p_c, csh_p_c, sw_p_c
    sh_per_regime = sh_per_regime_c

    # ═══════════════════════════════════════════════════════════════
    # A/B Test: دو بار run_ensemble با max_strat_override مختلف
    # ═══════════════════════════════════════════════════════════════
    
    # 1. Conservative (max 5)
    top_p_c, ct_p_c, cdd_p_c, csh_p_c, sw_p_c, sh_c = run_ensemble(
        strat_rets, pred_regs, train_mask, test_mask, fee, market=name, 
        max_strat_override=5
    )
    
    # 2. Aggressive (max 15)
    top_p_a, ct_p_a, cdd_p_a, csh_p_a, sw_p_a, sh_a = run_ensemble(
        strat_rets, pred_regs, train_mask, test_mask, fee, market=name, 
        max_strat_override=15
    )
    
    return {
        "market": name, "assets": len(df.columns), "days": len(df),
        "oracle": {"return": ct_o, "dd": cdd_o, "sharpe": csh_o},
        "predictive_conservative": {
            "return": ct_p_c, "dd": cdd_p_c, "sharpe": csh_p_c, "switches": sw_p_c, 
            "top": top_p_c, 
            "metrics": {r: {"sharpe": sh} for r, sh in sh_c.items()}
        },
        "predictive_aggressive": {
            "return": ct_p_a, "dd": cdd_p_a, "sharpe": csh_p_a, "switches": sw_p_a, 
            "top": top_p_a, 
            "metrics": {r: {"sharpe": sh} for r, sh in sh_a.items()}
        },
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
    except Exception as e:
        print(f"❌ TMN: {e}")
        traceback.print_exc()

    # 2. USDT
    try:
        raw = json.load(open("data/wallex_usdt_all.json"))
        df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k != "USDTUSDT" and k.endswith("USDT") and len(v)>=100})
        results["USDT"] = process_market("USDT", df, FEE_USDT)
        print(f"✅ USDT: {len(df.columns)} assets")
    except Exception as e:
        print(f"❌ USDT: {e}")
        traceback.print_exc()

    # 3. GLOBAL
    try:
        raw = json.load(open("data/crypto_5y_usd.json"))
        df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k.endswith("-USD")})
        results["GLOBAL"] = process_market("GLOBAL", df, FEE_GLOBAL)
        print(f"✅ GLOBAL: {len(df.columns)} assets")
    except Exception as e:
        print(f"❌ GLOBAL: {e}")
        traceback.print_exc()

    # Load ALL profiler strategies
    try:
        profiler_df = load_profiler_returns_as_df(name, df.index) if name in ["GLOBAL", "TMN", "USDT"] else None
    except: pass
    
    # Save to pending (requires human approval)
    # ۱. ذخیره pending (برای approve)
    with open("data/researcher_pending.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ Saved results to PENDING. Human approval required.")

    # ۲. A/B Test: ذخیره فایل‌های جداگانه (برای ربات‌های Paper)
    conservative_results = {}
    aggressive_results = {}
    
    for market_name, market_data in results.items():
        if market_data is None: 
            print(f"⚠️ {market_name}: market_data is None")
            continue
        if "predictive_conservative" not in market_data: 
            print(f"⚠️ {market_name}: no predictive_conservative")
            continue
        
        base = {
            "market": market_data["market"],
            "assets": market_data["assets"],
            "days": market_data["days"],
            "oracle": market_data["oracle"],
            "bnh_btc": market_data["bnh_btc"]
        }
        
        conservative_results[market_name] = {**base, "predictive": market_data["predictive_conservative"]}
        aggressive_results[market_name] = {**base, "predictive": market_data["predictive_aggressive"]}
    
    if conservative_results:
        try:
            test_json = json.dumps(conservative_results, indent=2, default=str)
            print(f"=== DEBUG: json size: {len(test_json)} chars ===")
            with open("data/researcher_conservative.json", "w") as f:
                f.write(test_json)
            print(f"✅ Saved Conservative ({len(conservative_results)} markets)")
            
            # 🔴 DIRECT UPLOAD TO GITHUB API (before anything can overwrite)
            import os
            GH_TOKEN = os.environ.get("GH_TOKEN")
            if GH_TOKEN:
                import base64
                import requests
                url = "https://api.github.com/repos/David212law/Price_bot/contents/data/researcher_conservative.json"
                headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
                r = requests.get(url, headers=headers)
                sha = r.json().get("sha") if r.status_code == 200 else None
                data = {
                    "message": "Auto: upload conservative [skip ci]",
                    "content": base64.b64encode(test_json.encode()).decode(),
                    "branch": "main"
                }
                if sha: data["sha"] = sha
                r = requests.put(url, headers=headers, json=data)
                print(f"=== DEBUG: GitHub upload status: {r.status_code} ===")
                if r.status_code in [200, 201]:
                    print(f"✅ Uploaded conservative to GitHub!")
                else:
                    print(f"❌ Upload failed: {r.text[:200]}")
        except Exception as e:
            print(f"❌ json.dump/upload failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ No conservative results")
    
    if aggressive_results:
        try:
            test_json_a = json.dumps(aggressive_results, indent=2, default=str)
            with open("data/researcher_aggressive.json", "w") as f:
                f.write(test_json_a)
            print(f"✅ Saved Aggressive ({len(aggressive_results)} markets)")
            
            # DIRECT UPLOAD TO GITHUB API
            import os
            GH_TOKEN = os.environ.get("GH_TOKEN")
            if GH_TOKEN:
                import base64
                import requests
                url = "https://api.github.com/repos/David212law/Price_bot/contents/data/researcher_aggressive.json"
                headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
                r = requests.get(url, headers=headers)
                sha = r.json().get("sha") if r.status_code == 200 else None
                data = {
                    "message": "Auto: upload aggressive [skip ci]",
                    "content": base64.b64encode(test_json_a.encode()).decode(),
                    "branch": "main"
                }
                if sha: data["sha"] = sha
                r = requests.put(url, headers=headers, json=data)
                print(f"=== DEBUG: GitHub upload status: {r.status_code} ===")
                if r.status_code in [200, 201]:
                    print(f"✅ Uploaded aggressive to GitHub!")
                else:
                    print(f"❌ Upload failed: {r.text[:200]}")
        except Exception as e:
            print(f"❌ Failed: {e}")
    else:
        print("❌ No aggressive results")

    # ═══════════════════════════════════════════════════════════════
    # A/B Test: ذخیره هر دو نسخه Conservative و Aggressive
    # ═══════════════════════════════════════════════════════════════
    
    conservative_results = {}
    aggressive_results = {}
    
    for market_name, market_data in results.items():
        if market_data is None: continue
        
        # Conservative
        if "conservative" in market_data:
            conservative_results[market_name] = {
                "market": market_data["market"],
                "assets": market_data["assets"],
                "days": market_data["days"],
                "oracle": market_data["oracle"],
                "predictive": {
                    "return": market_data["predictive"]["return"],
                    "dd": market_data["predictive"]["dd"],
                    "sharpe": market_data["predictive"]["sharpe"],
                    "switches": market_data["predictive"]["switches"],
                    "top": market_data["conservative"]["predictive"]["top"],
                    "metrics": market_data["predictive"]["metrics"]
                },
                "bnh_btc": market_data["bnh_btc"]
            }
        
        # Aggressive
        if "aggressive" in market_data:
            aggressive_results[market_name] = {
                "market": market_data["market"],
                "assets": market_data["assets"],
                "days": market_data["days"],
                "oracle": market_data["oracle"],
                "predictive": {
                    "return": market_data["predictive"]["return"],
                    "dd": market_data["predictive"]["dd"],
                    "sharpe": market_data["predictive"]["sharpe"],
                    "switches": market_data["predictive"]["switches"],
                    "top": market_data["aggressive"]["predictive"]["top"],
                    "metrics": market_data["predictive"]["metrics"]
                },
                "bnh_btc": market_data["bnh_btc"]
            }
    
    with open("data/researcher_conservative.json", "w") as f:
        json.dump(conservative_results, f, indent=2)
    print("✅ Saved Conservative (5 strategies)")
    
    with open("data/researcher_aggressive.json", "w") as f:
        json.dump(aggressive_results, f, indent=2)
    print("✅ Saved Aggressive (15 strategies)")

    # Bale
    msg = "🤖 *Predictive Researcher — PENDING APPROVAL*\n\n"
    for m, r in results.items():
        if not isinstance(r, dict): continue
        msg += f"📊 *{m}* ({r.get('assets', 0)} assets, {r.get('days', 0)}d)\n"
        msg += f"├ Oracle: {r['oracle']['return']:+.1f}% (DD {r['oracle']['dd']:.1f}%, Sh {r['oracle']['sharpe']:.2f})\n"
        # A/B Test: use conservative for the main message
        cons = r.get('predictive_conservative', {})
        aggr = r.get('predictive_aggressive', {})
        if cons:
            msg += f"├ Cons: {cons.get('return', 0):+.1f}% (Sh {cons.get('sharpe', 0):.2f})\n"
        if aggr:
            msg += f"├ Aggr: {aggr.get('return', 0):+.1f}% (Sh {aggr.get('sharpe', 0):.2f})\n"
        if 'bnh_btc' in r:
            msg += f"└ B&H BTC: {r['bnh_btc']['return']:+.1f}%\n"
        top_items = []
        # Use conservative top (or fallback to first available)
        top_source = r.get('predictive_conservative', r.get('predictive', {}))
        for k, v in top_source.get('top', {}).items():
            if isinstance(v, dict):
                best = max(v, key=v.get) if v else "NONE"
            elif isinstance(v, list):
                best = v[0] if v else "NONE"
            else:
                best = str(v)
            top_items.append(f"{k}:{best}")
        msg += "Top: " + ", ".join(top_items) + "\n\n"
    msg += "\n✅ برای تأیید: در ترموس دستور python3 scripts/approve_strategies.py را اجرا کنید."
    send_bale(msg)

if __name__ == "__main__":
    main()
