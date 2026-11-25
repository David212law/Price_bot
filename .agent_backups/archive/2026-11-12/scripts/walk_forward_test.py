"""Walk-Forward: 5 rolling windows (6mo train, 3mo test)."""
import json
import os
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, "scripts")

from researcher_predictive import (
    detect_regime, run_ensemble, stats, load_unified_db, build_strategies,
    FEE_TMN, FEE_USDT, FEE_GLOBAL
)

def load_market_data(name):
    """Load data exactly like main() does."""
    if name == "TMN":
        raw = json.load(open("data/wallex_tmn_all.json"))
        df = pd.DataFrame({k[:-3]: v for k,v in raw.items() if k != "USDTTMN" and k.endswith("TMN") and len(v)>=100})
    elif name == "USDT":
        raw = json.load(open("data/wallex_usdt_all.json"))
        df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k != "USDTUSDT" and k.endswith("USDT") and len(v)>=100})
    elif name == "GLOBAL":
        raw = json.load(open("data/crypto_5y_usd.json"))
        df = pd.DataFrame({k[:-4]: v for k,v in raw.items() if k.endswith("-USD")})
    else:
        return None
    df.index = pd.to_datetime(df.index)
    return df.sort_index().ffill()

def build_strat_rets(df, name):
    """Build strat_rets exactly like process_market does."""
    S = build_strategies(df)
    market_rets = df.pct_change().fillna(0)
    strat_rets_dict = {k: (v.shift(1) * market_rets).sum(axis=1) for k, v in S.items()}
    strat_rets = pd.DataFrame(strat_rets_dict)
    
    # Add unified DB strategies
    try:
        unified = load_unified_db()
        rows = []
        for sid, s in unified.items():
            exch = s.get("exchange", "")
            if name == "GLOBAL" and exch not in ["hyperliquid", "aster", "kucoin"]: continue
            if name in ["TMN", "USDT"] and exch != "wallex": continue
            rets = s.get("returns", {})
            if not rets: continue
            try:
                series = pd.Series(rets)
                series.index = pd.to_datetime(series.index)
                series = series.reindex(df.index).fillna(0.0)
                if series.abs().sum() > 0:
                    rows.append((sid, series))
            except: pass
        if rows:
            profiler_df = pd.DataFrame(dict(rows)).reindex(df.index).fillna(0.0)
            strat_rets = pd.concat([strat_rets, profiler_df], axis=1)
    except Exception as e:
        print(f"  ⚠️ Unified DB load failed: {e}")
    
    return strat_rets

def walk_forward_market(name, fee, n_windows=5, train_days=180, test_days=90):
    df = load_market_data(name)
    if df is None or len(df) < 400:
        print(f"  ⚠️ Not enough data for {name}: {len(df) if df is not None else 0} days")
        return []
    
    strat_rets = build_strat_rets(df, name)
    regimes = detect_regime(df)
    
    total_days = len(df)
    step = (total_days - train_days - test_days) // (n_windows - 1)
    
    results = []
    for i in range(n_windows):
        train_start = i * step
        train_end = train_start + train_days
        test_start = train_end
        test_end = test_start + test_days
        
        if test_end > total_days:
            break
        
        train_mask = pd.Series(False, index=df.index)
        train_mask.iloc[train_start:train_end] = True
        test_mask = pd.Series(False, index=df.index)
        test_mask.iloc[test_start:test_end] = True
        
        try:
            _, ret, dd, sharpe, switches, _ = run_ensemble(
                strat_rets, regimes, train_mask, test_mask, fee, market=name
            )
            results.append({
                "window": i,
                "train": [str(df.index[train_start].date()), str(df.index[train_end-1].date())],
                "test": [str(df.index[test_start].date()), str(df.index[test_end-1].date())],
                "return": round(ret, 2),
                "dd": round(dd, 2),
                "sharpe": round(sharpe, 3),
                "switches": switches
            })
            print(f"  Window {i}: Test {results[-1]['test']} → Sharpe={sharpe:.2f}, Return={ret:.1f}%, DD={dd:.1f}%")
        except Exception as e:
            print(f"  Window {i} failed: {e}")
            import traceback; traceback.print_exc()
    
    return results

def main():
    print("=" * 80)
    print(" WALK-FORWARD TEST — 5 rolling windows (180d train, 90d test)")
    print("=" * 80)
    
    all_results = {}
    for name, fee in [("TMN", FEE_TMN), ("USDT", FEE_USDT), ("GLOBAL", FEE_GLOBAL)]:
        print(f"\n{'='*80}\n {name}\n{'='*80}")
        results = walk_forward_market(name, fee)
        all_results[name] = results
    
    # Summary
    print("\n" + "=" * 80)
    print(" SUMMARY — Walk-Forward Confirmation")
    print("=" * 80)
    passed = {}
    for name, results in all_results.items():
        if not results:
            passed[name] = False
            continue
        sharpes = [r["sharpe"] for r in results]
        all_above = all(s > 1.5 for s in sharpes)
        passed[name] = all_above
        print(f"\n{name}:")
        print(f"  Windows: {len(results)}")
        print(f"  Sharpe: min={min(sharpes):.2f}, max={max(sharpes):.2f}, mean={np.mean(sharpes):.2f}")
        print(f"  All > 1.5: {'✅ YES' if all_above else '❌ NO'}")
    
    print("\n" + "=" * 80)
    print(f" FINAL: {sum(passed.values())}/{len(passed)} markets PASS Walk-Forward")
    print("=" * 80)
    
    os.makedirs("data", exist_ok=True)
    with open("data/walk_forward_results.json", "w") as f:
        json.dump({"results": all_results, "passed": passed}, f, indent=2)
    print(f"\n✅ Saved to data/walk_forward_results.json")

if __name__ == "__main__":
    main()
