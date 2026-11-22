"""
Hybrid Backtest — تست ۴۳ استراتژی از library.

Output: data/hybrid_strategy_scores.json
  {
    "ema_cross_20_50": {
      "sharpe_7d": 1.2,
      "sharpe_per_regime": {"BULL": 1.5, "FLAT": 0.8, ...},
      "max_dd": 0.15,
      "n_trades": 50,
    },
    ...
  }
"""

import json
import sys
import os as _os
from pathlib import Path

# PROJECT-ROOT-INJECT (D-356 fix) — اجازه import از ریشه پروژه
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
from strategies.library.trend import (
    strat_ema_cross, strat_macd, strat_adx_trend, strat_supertrend,
    strat_donchian, strat_ichimoku, strat_price_sma, strat_dual_momentum,
    strat_triple_ema, strat_parabolic_sar
)
from strategies.library.mean_reversion import (
    strat_bollinger, strat_rsi_reversal, strat_zscore, strat_keltner_reversion,
    strat_rsi_divergence, strat_mean_rev_sma, strat_connors_rsi, strat_rsi_mean
)
from strategies.library.momentum import (
    strat_roc, strat_momentum_sma, strat_momentum_ema, strat_elder_impulse,
    strat_rsi_momentum, strat_price_momentum
)
from strategies.library.volatility import (
    strat_bb_squeeze, strat_atr_breakout, strat_keltner_squeeze,
    strat_vol_breakout_donchian, strat_nr_breakout
)
from strategies.library.volume import (
    strat_obv, strat_vwap, strat_mfi, strat_volume_breakout
)
from strategies.library.funding import (
    m31_sma, m31_ema, m31_threshold, m31_quantile, m31_momentum,
    strat_funding_mean_rev
)

# همه ۴۳ استراتژی
ALL_STRATEGIES = {
    # TREND (11)
    "ema_cross_20_50":   lambda c: strat_ema_cross(c, 20, 50),
    "ema_cross_50_200":  lambda c: strat_ema_cross(c, 50, 200),
    "macd_12_26":        lambda c: strat_macd(c, 12, 26, 9),
    "adx_trend":         lambda c: strat_adx_trend(c, 14, 25),
    "supertrend":        lambda c: strat_supertrend(c, 10, 3.0),
    "donchian_20":       lambda c: strat_donchian(c, 20),
    "ichimoku":          lambda c: strat_ichimoku(c, 9, 26),
    "price_sma_50":      lambda c: strat_price_sma(c, 50),
    "dual_momentum":     lambda c: strat_dual_momentum(c, 20, 50),
    "triple_ema":        lambda c: strat_triple_ema(c, 10, 20, 50),
    "parabolic_sar":     lambda c: strat_parabolic_sar(c),
    # MEAN_REV (9)
    "bb_20_2":           lambda c: strat_bollinger(c, 20, 2.0),
    "bb_30_2.5":         lambda c: strat_bollinger(c, 30, 2.5),
    "rsi_14_30_70":      lambda c: strat_rsi_reversal(c, 14, 30, 70),
    "rsi_21_25_75":      lambda c: strat_rsi_reversal(c, 21, 25, 75),
    "zscore_20":         lambda c: strat_zscore(c, 20, 2.0),
    "keltner_rev":       lambda c: strat_keltner_reversion(c, 20, 2.0),
    "rsi_divergence":    lambda c: strat_rsi_divergence(c, 14, 10),
    "mean_rev_sma_50":   lambda c: strat_mean_rev_sma(c, 50, 0.02),
    "connors_rsi":       lambda c: strat_connors_rsi(c, 3, 200),
    "rsi_mean":          lambda c: strat_rsi_mean(c, 14, 40, 60),
    # MOMENTUM (6)
    "roc_10":            lambda c: strat_roc(c, 10, 0.02),
    "roc_20":            lambda c: strat_roc(c, 20, 0.02),
    "momentum_sma_20":   lambda c: strat_momentum_sma(c, 20, 0.01),
    "momentum_ema":      lambda c: strat_momentum_ema(c, 10, 30),
    "elder_impulse":     lambda c: strat_elder_impulse(c, 13),
    "rsi_momentum_14":   lambda c: strat_rsi_momentum(c, 14, 60),
    "price_momentum_20": lambda c: strat_price_momentum(c, 20, 0.015),
    # VOLATILITY (5)
    "bb_squeeze_20":     lambda c: strat_bb_squeeze(c, 20, 50),
    "atr_breakout_14":   lambda c: strat_atr_breakout(c, 14, 1.5),
    "keltner_squeeze":   lambda c: strat_keltner_squeeze(c, 20, 2.0),
    "vol_breakout_donch":lambda c: strat_vol_breakout_donchian(c, 20, 1.0),
    "nr_breakout":       lambda c: strat_nr_breakout(c, 7, 20),
    # VOLUME (4)
    "obv":               lambda c: strat_obv(c, 20),
    "vwap":              lambda c: strat_vwap(c, 20, 0.01),
    "mfi":               lambda c: strat_mfi(c, 14, 20, 80),
    "volume_breakout":   lambda c: strat_volume_breakout(c, 20, 2.0),
}

def stats(returns):
    """Compute Sharpe, DD, n_trades from list of returns."""
    if not returns or len(returns) < 10:
        return {"sharpe": 0, "dd": 0, "n": 0}
    rets = pd.Series(returns)
    sharpe = rets.mean() / rets.std() * (365 ** 0.5) if rets.std() > 0 else 0
    cum = (1 + rets).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    return {"sharpe": round(float(sharpe), 3), "dd": round(float(dd), 3), "n": len(returns)}

def main():
    print("=" * 80)
    print(f" 🔬 HYBRID BACKTEST — {len(ALL_STRATEGIES)} strategies from library")
    print("=" * 80)
    print()

    # Load data
    raw = json.load(open("data/wallex_tmn_all.json"))
    df_dict = {}
    for k, v in raw.items():
        if k == "USDTTMN" or not k.endswith("TMN") or len(v) < 100:
            continue
        df_dict[k[:-3]] = pd.Series(v)
    df = pd.DataFrame(df_dict)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    print(f"✅ Data: {len(df.columns)} assets × {len(df)} days")

    # Build candles (for library functions that expect candles)
    btc = df["BTC"] if "BTC" in df.columns else df.iloc[:, 0]
    candles = [
        {"t": int(t.timestamp() * 1000), "o": float(p), "h": float(p),
         "l": float(p), "c": float(p), "v": 1.0}
        for t, p in zip(btc.index, btc.values)
    ]

    # Backtest each strategy
    results = {}
    for name, fn in ALL_STRATEGIES.items():
        try:
            trades = fn(candles)
            rets = [t["ret"] for t in trades] if trades else []
            results[name] = stats(rets)
            status = "✅" if results[name]["sharpe"] > 0.5 else ("🟡" if results[name]["sharpe"] > 0 else "🔴")
            print(f"  {name:25s}: Sharpe={results[name]['sharpe']:>6.2f}, DD={results[name]['dd']:>6.2%}, n={results[name]['n']:>4} {status}")
        except Exception as e:
            results[name] = {"sharpe": 0, "dd": 0, "n": 0, "error": str(e)}
            print(f"  {name:25s}: ❌ {e}")

    # Save
    with open("data/hybrid_strategy_scores.json", "w") as f:
        json.dump(results, f, indent=2)

    # Summary
    print()
    print("=" * 80)
    good = [n for n, r in results.items() if r["sharpe"] > 0.5]
    medium = [n for n, r in results.items() if 0 < r["sharpe"] <= 0.5]
    bad = [n for n, r in results.items() if r["sharpe"] <= 0]
    print(f"  Sharpe > 0.5 (خوب):     {len(good)}")
    print(f"  0 < Sharpe ≤ 0.5 (متوسط): {len(medium)}")
    print(f"  Sharpe ≤ 0 (ضعیف):       {len(bad)}")
    print()
    print(f"  بهترین ۱۰ استراتژی:")
    best_10 = sorted(results.items(), key=lambda x: -x[1]["sharpe"])[:10]
    for name, r in best_10:
        print(f"    {name:25s}: Sharpe={r['sharpe']:>6.2f}")
    print()
    print("✅ Saved to data/hybrid_strategy_scores.json")

if __name__ == "__main__":
    main()
