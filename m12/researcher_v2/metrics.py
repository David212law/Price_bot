"""M12 Researcher v2 — metrics (با fallback بدون pandas).

اگه pandas نصب باشه → از pandas استفاده می‌کنه.
اگه نباشه → fallback ساده با stdlib.
"""
from __future__ import annotations

# ─── تلاش برای import pandas ───
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None
    HAS_PANDAS = False

import math


# ─────────────────────────────────────────────
# Helpers (کار با list و pandas)
# ─────────────────────────────────────────────
def _to_list(returns):
    """تبدیل ورودی به list (چه pandas باشه چه list)."""
    if HAS_PANDAS and isinstance(returns, pd.Series):
        return returns.tolist()
    return list(returns)


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _std(values):
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / len(values)
    return math.sqrt(var)


# ─────────────────────────────────────────────
# تک‌متریک‌ها
# ─────────────────────────────────────────────
def sharpe(returns, tpy=365):
    """Sharpe ratio سالانه."""
    values = _to_list(returns)
    if len(values) < 20:
        return 0.0
    sd = _std(values)
    if sd == 0:
        return 0.0
    return (_mean(values) / sd) * math.sqrt(tpy)


def win_rate(returns):
    """Win rate = درصد trades برنده."""
    values = _to_list(returns)
    if not values:
        return 0.0
    return sum(1 for x in values if x > 0) / len(values)


def max_drawdown(returns):
    """Max drawdown."""
    values = _to_list(returns)
    if not values:
        return 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in values:
        equity *= (1 + r)
        peak = max(peak, equity)
        dd = (equity - peak) / peak
        max_dd = min(max_dd, dd)
    return max_dd


def total_return(returns):
    """بازده کل."""
    values = _to_list(returns)
    if not values:
        return 0.0
    eq = 1.0
    for r in values:
        eq *= (1 + r)
    return eq - 1


def expectancy(returns):
    """Expectancy = mean."""
    return _mean(_to_list(returns))


# ─────────────────────────────────────────────
# compute_metrics
# ─────────────────────────────────────────────
def compute_metrics(returns, tpy=365):
    """همه metrics برای یک Series/list."""
    values = _to_list(returns)
    return {
        "n": int(len(values)),
        "sharpe": sharpe(values, tpy),
        "win_rate": win_rate(values),
        "max_dd": max_drawdown(values),
        "total_return": total_return(values),
        "expectancy": expectancy(values),
    }


# ─────────────────────────────────────────────
# compute_all_metrics
# ─────────────────────────────────────────────
def compute_all_metrics(backtest_results, tpy=365):
    """
    محاسبه metrics برای همه (strategy × regime).
    
    اگه pandas باشه → DataFrame
    اگه نباشه → list of dicts
    """
    rows = []
    for strategy, regimes in backtest_results.items():
        for regime, data in regimes.items():
            ret_list = data.get("ret", [])
            if not ret_list:
                continue
            metrics = compute_metrics(ret_list, tpy)
            rows.append({
                "strategy": strategy,
                "regime": regime,
                **metrics,
            })

    if HAS_PANDAS:
        return pd.DataFrame(rows)
    return rows


# ─────────────────────────────────────────────
# فیلترها
# ─────────────────────────────────────────────
def filter_by_threshold(df, min_trades=20, min_win_rate=0.52, min_sharpe=0.0):
    """فیلتر استراتژی‌ها."""
    if HAS_PANDAS and isinstance(df, pd.DataFrame):
        return df[
            (df["n"] >= min_trades)
            & (df["win_rate"] >= min_win_rate)
            & (df["sharpe"] > min_sharpe)
        ].copy()
    # fallback list
    return [
        r for r in df
        if r["n"] >= min_trades
        and r["win_rate"] >= min_win_rate
        and r["sharpe"] > min_sharpe
    ]


__all__ = [
    "sharpe", "win_rate", "max_drawdown", "total_return", "expectancy",
    "compute_metrics", "compute_all_metrics", "filter_by_threshold",
    "HAS_PANDAS",
]
