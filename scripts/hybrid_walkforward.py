"""Hybrid Walk-Forward — 43 strategies × 5 windows → final selection."""

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
    print(" 🔬 HYBRID WALK-FORWARD — 43 strategies × 5 windows")
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

    # 5 windows (train 180, test 90)
    windows = []
    for k in range(5):
        ts = k * 90; te = ts + 180; vs = te; ve = min(vs + 90, n)
        if ve <= vs: break
        windows.append({"train_start": candles[ts]["t"], "train_end": candles[te-1]["t"],
                        "test_start": candles[vs]["t"], "test_end": candles[ve-1]["t"]})
    print(f"✅ {len(windows)} WF windows")

    # For each strategy: run once, slice trades per window
    results = {}
    for name, fn in ALL_STRATEGIES.items():
        try:
            trades = fn(candles)
            if not trades:
                results[name] = {"wf_sharpe_mean": 0, "n": 0, "error": "no trades"}
                continue
            wf_sharpes = []
            for w in windows:
                tr = [t["ret"] for t in trades if w["test_start"] <= t["t"] <= w["test_end"]]
                wf_sharpes.append(stats(tr)["sharpe"])
            results[name] = {
                "wf_sharpe_mean": round(float(np.mean(wf_sharpes)), 3),
                "wf_sharpe_min": round(float(np.min(wf_sharpes)), 3),
                "wf_sharpe_max": round(float(np.max(wf_sharpes)), 3),
                "per_window": wf_sharpes,
                "n": len(trades),
                "trades": [(t["t"], round(t["ret"], 6)) for t in trades],
            }
        except Exception as e:
            results[name] = {"wf_sharpe_mean": 0, "n": 0, "error": str(e)}

    # Filter 1: n>=30 AND wf_sharpe_mean > 0.5
    good = {n: r for n, r in results.items() if r.get("wf_sharpe_mean", 0) > 0.5 and r.get("n", 0) >= 30}
    print(f"\n✅ {len(good)} استراتژی از 43 (n>=30 + WF Sharpe>0.5)")
    if len(good) < 5:
        print(f"\n⚠️ فقط {len(good)} استراتژی قبول شدند — نامشان:")
        for name, r in sorted(good.items(), key=lambda x: -x[1]["wf_sharpe_mean"]):
            print(f"   {name:25s}: WF={r['wf_sharpe_mean']:>6.2f}, n={r['n']:>4}")
        # آستانه پایین‌تر — همه استراتژی‌های با WF>0.2 و n>=20
        relaxed = {n: r for n, r in results.items()
                   if r.get("wf_sharpe_mean", 0) > 0.2 and r.get("n", 0) >= 20}
        print(f"\n🔓 استراتژی‌های با WF>0.2 و n>=20 (relaxed): {len(relaxed)}")
        for name, r in sorted(relaxed.items(), key=lambda x: -x[1]["wf_sharpe_mean"])[:15]:
            print(f"   {name:25s}: WF={r['wf_sharpe_mean']:>6.2f}, n={r['n']:>4}")

    # Correlation filter
    daily_rets = {}
    for name, r in good.items():
        if "trades" not in r: continue
        tr = pd.Series({pd.to_datetime(t, unit="ms"): ret for t, ret in r["trades"]})
        daily = tr.resample("D").sum().fillna(0) if tr else pd.Series(dtype=float)
        if daily: daily_rets[name] = daily

    selected = []
    if daily_rets:
        corr = pd.DataFrame(daily_rets).fillna(0).corr()
        for name, r in sorted(good.items(), key=lambda x: -x[1]["wf_sharpe_mean"]):
            if name not in corr.columns: continue
            if not selected: selected.append(name); continue
            max_c = max([abs(corr.loc[s, name]) for s in selected if s in corr.index and name in corr.columns] or [0])
            if max_c < 0.7: selected.append(name)

    # Save
    output = {
        "windows": windows,
        "total_tested": len(results),
        "good_strategies": len(good),
        "selected_after_corr": len(selected),
        "selected": selected,
        "details": {n: {k: v for k, v in results[n].items() if k != "trades"} for n in results},
    }
    with open("data/hybrid_v2_strategies.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 80)
    print(f"  انتخاب نهایی: {len(selected)} استراتژی")
    print("=" * 80)
    for name in selected:
        r = results[name]
        print(f"  {name:25s}: WF={r['wf_sharpe_mean']:>6.2f}, n={r['n']:>4}")

    # Also print rejected good strategies (high corr)
    rejected = [n for n in good if n not in selected]
    if rejected:
        print(f"\n  ⚠️ حذف شده به خاطر correlation: {len(rejected)}")
        for n in rejected[:5]:
            print(f"    {n:25s}: WF={results[n]['wf_sharpe_mean']:>6.2f}")

    print("\n✅ Saved to data/hybrid_v2_strategies.json")

if __name__ == "__main__":
    main()
