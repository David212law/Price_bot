"""M12 Researcher v2 — metrics (pandas-based، استاندارد).

ابزار استاندارد برای محاسبه:
  - Sharpe ratio
  - Win rate
  - Max drawdown
  - Total return
  - Expectancy

خروجی: DataFrame — قابل ذخیره در CSV/Excel.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
# تک‌متریک‌ها (همه با pandas/numpy)
# ─────────────────────────────────────────────
def sharpe(returns: pd.Series, tpy: int = 365) -> float:
    """Sharpe ratio سالانه — استاندارد."""
    if len(returns) < 20 or returns.std() == 0:
        return 0.0
    return float((returns.mean() / returns.std()) * np.sqrt(tpy))


def win_rate(returns: pd.Series) -> float:
    """Win rate = درصد trades برنده."""
    if len(returns) == 0:
        return 0.0
    return float((returns > 0).mean())


def max_drawdown(returns: pd.Series) -> float:
    """Max drawdown با equity curve از returns."""
    if len(returns) == 0:
        return 0.0
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def total_return(returns: pd.Series) -> float:
    """بازده کل (compound)."""
    if len(returns) == 0:
        return 0.0
    return float((1 + returns).prod() - 1)


def expectancy(returns: pd.Series) -> float:
    """Expectancy = mean(returns) — متوسط بازده هر trade."""
    if len(returns) == 0:
        return 0.0
    return float(returns.mean())


# ─────────────────────────────────────────────
# محاسبه همه metrics برای یک Series
# ─────────────────────────────────────────────
def compute_metrics(returns: pd.Series, tpy: int = 365) -> dict:
    """همه metrics برای یک Series از returns."""
    return {
        "n": int(len(returns)),
        "sharpe": sharpe(returns, tpy),
        "win_rate": win_rate(returns),
        "max_dd": max_drawdown(returns),
        "total_return": total_return(returns),
        "expectancy": expectancy(returns),
    }


# ─────────────────────────────────────────────
# محاسبه metrics برای همه استراتژی×regime
# ─────────────────────────────────────────────
def compute_all_metrics(
    backtest_results: dict,
    tpy: int = 365,
) -> pd.DataFrame:
    """
    محاسبه metrics برای همه (strategy × regime).
    
    Args:
        backtest_results: {strategy: {regime: {"won": [...], "ret": [...]}}}
        tpy: trades per year (365 برای روزانه)
    
    Returns:
        DataFrame با ستون‌های: strategy, regime, n, sharpe, win_rate, max_dd, total_return, expectancy
    """
    rows = []
    for strategy, regimes in backtest_results.items():
        for regime, data in regimes.items():
            ret_list = data.get("ret", [])
            if len(ret_list) == 0:
                continue
            rets = pd.Series(ret_list, dtype=float)
            metrics = compute_metrics(rets, tpy)
            rows.append({
                "strategy": strategy,
                "regime": regime,
                **metrics,
            })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# فیلترها (استاندارد)
# ─────────────────────────────────────────────
def filter_by_threshold(
    df: pd.DataFrame,
    min_trades: int = 20,
    min_win_rate: float = 0.52,
    min_sharpe: float = 0.0,
) -> pd.DataFrame:
    """فیلتر استراتژی‌ها بر اساس آستانه‌ها."""
    return df[
        (df["n"] >= min_trades)
        & (df["win_rate"] >= min_win_rate)
        & (df["sharpe"] > min_sharpe)
    ].copy()


def filter_correlation(
    selected: list[str],
    returns_by_strategy: dict[str, pd.Series],
    max_corr: float = 0.5,
) -> list[str]:
    """
    حذف استراتژی‌های correlated.
    
    Args:
        selected: لیست استراتژی‌های کاندید
        returns_by_strategy: {name: pd.Series of returns}
        max_corr: حداکثر correlation مجاز
    
    Returns:
        لیست نهایی استراتژی‌ها
    """
    picked: list[str] = []
    picked_returns: list[pd.Series] = []

    for name in selected:
        if name not in returns_by_strategy:
            continue
        rets = returns_by_strategy[name]

        if not picked:
            picked.append(name)
            picked_returns.append(rets)
            continue

        max_c = 0.0
        for existing in picked_returns:
            # align indexes
            common = rets.index.intersection(existing.index)
            if len(common) < 10:
                continue
            corr = rets.loc[common].corr(existing.loc[common])
            if not pd.isna(corr):
                max_c = max(max_c, abs(corr))

        if max_c < max_corr:
            picked.append(name)
            picked_returns.append(rets)

    return picked


__all__ = [
    "sharpe",
    "win_rate",
    "max_drawdown",
    "total_return",
    "expectancy",
    "compute_metrics",
    "compute_all_metrics",
    "filter_by_threshold",
    "filter_correlation",
]


# ─────────────────────────────────────────────
# CLI entry point (برای تست / GitHub Actions)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os

    print("═══ M12 researcher_v2 — metrics test ═══")

    # داده نمونه
    dummy_returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015] * 10)
    results = compute_metrics(dummy_returns)

    print("\nنتایج:")
    for k, v in results.items():
        print(f"  {k:15s}: {v}")

    # ذخیره در results/
    os.makedirs("results", exist_ok=True)
    df = pd.DataFrame([results])
    df.to_csv("results/metrics_summary.csv", index=False)
    print(f"\n✅ ذخیره شد: results/metrics_summary.csv")
