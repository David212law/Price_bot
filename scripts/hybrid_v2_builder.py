"""Hybrid v2 — ترکیب مکمل از همه استراتژی‌های ممکن."""

import json, sys
from pathlib import Path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path: sys.path.insert(0, _project_root)

import pandas as pd
import numpy as np

from strategies.library.trend import (strat_ema_cross, strat_macd, strat_adx_trend, strat_supertrend,
    strat_donchian, strat_ichimoku, strat_price_sma, strat_dual_momentum, strat_triple_ema, strat_parabolic_sar)
from strategies.library.mean_reversion import (strat_bollinger, strat_rsi_reversal, strat_zscore,
    strat_keltner_reversion, strat_rsi_divergence, strat_mean_rev_sma, strat_connors_rsi, strat_rsi_mean)
from strategies.library.momentum import (strat_roc, strat_momentum_sma, strat_momentum_ema,
    strat_elder_impulse, strat_rsi_momentum, strat_price_momentum)
from strategies.library.volatility import (strat_bb_squeeze, strat_atr_breakout, strat_keltner_squeeze,
    strat_vol_breakout_donchian, strat_nr_breakout)
from strategies.library.volume import strat_obv, strat_vwap, strat_mfi, strat_volume_breakout

ALL_STRATEGIES = {
    "ema_cross_20_50": lambda c: strat_ema_cross(c, 20, 50),
    "ema_cross_50_200": lambda c: strat_ema_cross(c, 50, 200),
    "macd_12_26": lambda c: strat_macd(c, 12, 26, 9),
    "adx_trend": lambda c: strat_adx_trend(c, 14, 25),
    "supertrend": lambda c: strat_supertrend(c, 10, 3.0),
    "donchian_20": lambda c: strat_donchian(c, 20),
    "ichimoku": lambda c: strat_ichimoku(c, 9, 26),
    "price_sma_50": lambda c: strat_price_sma(c, 50),
    "dual_momentum": lambda c: strat_dual_momentum(c, 20, 50),
    "triple_ema": lambda c: strat_triple_ema(c, 10, 20, 50),
    "parabolic_sar": lambda c: strat_parabolic_sar(c),
    "bb_20_2": lambda c: strat_bollinger(c, 20, 2.0),
    "bb_30_2.5": lambda c: strat_bollinger(c, 30, 2.5),
    "rsi_14_30_70": lambda c: strat_rsi_reversal(c, 14, 30, 70),
    "rsi_21_25_75": lambda c: strat_rsi_reversal(c, 21, 25, 75),
    "zscore_20": lambda c: strat_zscore(c, 20, 2.0),
    "keltner_rev": lambda c: strat_keltner_reversion(c, 20, 2.0),
    "rsi_divergence": lambda c: strat_rsi_divergence(c, 14, 10),
    "mean_rev_sma_50": lambda c: strat_mean_rev_sma(c, 50, 0.02),
    "connors_rsi": lambda c: strat_connors_rsi(c, 3, 200),
    "rsi_mean": lambda c: strat_rsi_mean(c, 14, 40, 60),
    "roc_10": lambda c: strat_roc(c, 10, 0.02),
    "roc_20": lambda c: strat_roc(c, 20, 0.02),
    "momentum_sma_20": lambda c: strat_momentum_sma(c, 20, 0.01),
    "momentum_ema": lambda c: strat_momentum_ema(c, 10, 30),
    "elder_impulse": lambda c: strat_elder_impulse(c, 13),
    "rsi_momentum_14": lambda c: strat_rsi_momentum(c, 14, 60),
    "price_momentum_20": lambda c: strat_price_momentum(c, 20, 0.015),
    "bb_squeeze_20": lambda c: strat_bb_squeeze(c, 20, 50),
    "atr_breakout_14": lambda c: strat_atr_breakout(c, 14, 1.5),
    "keltner_squeeze": lambda c: strat_keltner_squeeze(c, 20, 2.0),
    "vol_breakout_donch": lambda c: strat_vol_breakout_donchian(c, 20, 1.0),
    "nr_breakout": lambda c: strat_nr_breakout(c, 7, 20),
    "obv": lambda c: strat_obv(c, 20),
    "vwap": lambda c: strat_vwap(c, 20, 0.01),
    "mfi": lambda c: strat_mfi(c, 14, 20, 80),
    "volume_breakout": lambda c: strat_volume_breakout(c, 20, 2.0),
}

def stats(rets):
    if len(rets) < 10: return {"sharpe": 0, "dd": 0, "n": 0}
    r = pd.Series(rets)
    sharpe = r.mean() / r.std() * (365**0.5) if r.std() > 0 else 0
    cum = (1 + r).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    return {"sharpe": round(float(sharpe), 3), "dd": round(float(dd), 3), "n": len(rets)}

def main():
    print("=" * 80)
    print(" 🔬 HYBRID v2 — ترکیب مکمل")
    print("=" * 80)

    # Load data
    raw = json.load(open("data/wallex_tmn_all.json"))
    df_dict = {k[:-3]: pd.Series(v) for k, v in raw.items() if k != "USDTTMN" and k.endswith("TMN") and len(v) >= 100}
    df = pd.DataFrame(df_dict)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill()
    btc = df["BTC"] if "BTC" in df.columns else df.iloc[:, 0]
    candles = [{"t": int(t.timestamp()*1000), "o": float(p), "h": float(p), "l": float(p), "c": float(p), "v": 1.0}
               for t, p in zip(btc.index, btc.values)]
    n = len(candles)
    print(f"✅ {len(df.columns)} assets × {n} days")

    # Get returns per strategy (daily)
    daily_rets = {}
    raw_trades = {}
    for name, fn in ALL_STRATEGIES.items():
        try:
            trades = fn(candles)
            if not trades:
                continue
            tr_series = pd.Series({pd.to_datetime(t["t"], unit="ms"): t["ret"] for t in trades})
            daily = tr_series.resample("D").sum().fillna(0)
            if daily.abs().sum() > 0:
                daily_rets[name] = daily
                raw_trades[name] = trades
        except Exception:
            pass

    print(f"✅ {len(daily_rets)} استراتژی با returns")

    # Combine on same index
    all_rets = pd.DataFrame(daily_rets).fillna(0)
    print(f"✅ {len(all_rets)} days × {len(all_rets.columns)} استراتژی")

    # Per-strategy stats
    per_strat = {}
    for name in daily_rets:
        s = stats(daily_rets[name].tolist())
        if s["n"] >= 20:
            per_strat[name] = s

    print(f"✅ {len(per_strat)} استراتژی با n>=20")

    # Correlation matrix
    corr = all_rets[list(per_strat.keys())].corr()

    # === مکمل‌سازی: greedy با correlation < 0.6 ===
    # اولویت: WF_score (نه Sharpe خام)
    # weight = sharpe / (1 + corr با قبلی‌ها)
    sorted_by_sharpe = sorted(per_strat.items(), key=lambda x: -x[1]["sharpe"])

    selected = []
    max_corr_threshold = 0.6
    for name, r in sorted_by_sharpe:
        if r["sharpe"] < 0.2:  # آستانه پایین — بگذاریم هر استراتژی مثبت وارد شود
            continue
        if not selected:
            selected.append(name)
            continue
        max_c = max([abs(corr.loc[s, name]) for s in selected])
        if max_c < max_corr_threshold:
            selected.append(name)

    print(f"\n✅ {len(selected)} استراتژی مکمل (corr < {max_corr_threshold})")

    # === ترکیب با وزن Sharpe-based ===
    selected_sharpes = {name: per_strat[name]["sharpe"] for name in selected}
    total_sharpe = sum(selected_sharpes.values())
    weights = {name: round(s / total_sharpe, 4) for name, s in selected_sharpes.items()}

    # Combined portfolio
    combined = (all_rets[selected] * pd.Series(weights)).sum(axis=1)
    combo_stats = stats(combined.tolist())

    print("\n" + "=" * 80)
    print(f"  🎯 ترکیب {len(selected)} استراتژی:")
    print("=" * 80)
    for name in selected:
        print(f"  {name:25s}: weight={weights[name]:>6.3f}, sharpe={per_strat[name]['sharpe']:>6.2f}, n={per_strat[name]['n']:>4}")

    print(f"\n  📊 ترکیب ({len(selected)} استراتژی):")
    print(f"    Sharpe={combo_stats['sharpe']:.2f}, DD={combo_stats['dd']:.1%}, n={combo_stats['n']}")

    # مقایسه با تک استراتژی برتر
    best_single = sorted_by_sharpe[0]
    print(f"\n  🔍 مقایسه:")
    print(f"    تک استراتژی ({best_single[0]:20s}): Sharpe={best_single[1]['sharpe']:>6.2f}, DD={best_single[1]['dd']:>6.1%}, n={best_single[1]['n']}")
    print(f"    ترکیب {len(selected):2d} استراتژی:                    Sharpe={combo_stats['sharpe']:>6.2f}, DD={combo_stats['dd']:>6.1%}, n={combo_stats['n']}")

    # === A/B test: چند ترکیب مختلف ===
    print(f"\n  🧪 A/B Test — ترکیب‌های مختلف:")

    # ترکیب ۲ (با index صحیح)
    top2 = selected[:2]
    w2 = [weights[s] for s in top2]
    w2_norm = [w/sum(w2) for w in w2]
    combo2 = (all_rets[top2] * pd.Series(w2_norm, index=top2)).sum(axis=1)
    s2 = stats(combo2.tolist())
    print(f"    Top 2 استراتژی: Sharpe={s2['sharpe']:>6.2f}, DD={s2['dd']:>6.1%}")

    # ترکیب ۵
    if len(selected) >= 5:
        top5 = selected[:5]
        w5 = [weights[s] for s in top5]
        w5_norm = [w/sum(w5) for w in w5]
        combo5 = (all_rets[top5] * pd.Series(w5_norm, index=top5)).sum(axis=1)
        s5 = stats(combo5.tolist())
        print(f"    Top 5 استراتژی: Sharpe={s5['sharpe']:>6.2f}, DD={s5['dd']:>6.1%}")

    # ترکیب همه
    print(f"    همه {len(selected)} استراتژی:  Sharpe={combo_stats['sharpe']:>6.2f}, DD={combo_stats['dd']:>6.1%}")

    # Save
    output = {
        "total_testable": len(per_strat),
        "selected_count": len(selected),
        "selected": selected,
        "weights": weights,
        "per_strategy": per_strat,
        "combo_sharpe": combo_stats["sharpe"],
        "combo_dd": combo_stats["dd"],
        "top2_sharpe": s2["sharpe"],
        "top5_sharpe": s5["sharpe"] if len(selected) >= 5 else None,
    }
    with open("data/hybrid_v2_final.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ Saved to data/hybrid_v2_final.json")

if __name__ == "__main__":
    main()
