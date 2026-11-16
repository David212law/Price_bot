"""
Hybrid Signals — 12 pure functions.
Input:  df (DataFrame of prices, index=date, columns=assets)
Output: Series (0/1 per asset) — 1 = BUY/HOLD, 0 = no signal

No side effects. No state. Pure logic.

Families:
  TREND (3):      ema_cross_20_50, macd_12_26, donchian_20
  MEAN_REV (3):   bb_20_2, rsi_14, zscore_20
  MOMENTUM (3):   roc_10, momentum_sma_20, rsi_momentum_14
  BREAKOUT (3):   atr_breakout_14, bb_squeeze_20, donchian_break_20
"""

import pandas as pd


# ═══════════════════════════════════════════════════════════════════
# TREND FAMILY (3)
# ═══════════════════════════════════════════════════════════════════

def signal_ema_cross_20_50(df):
    """EMA 20 > EMA 50 → 1."""
    if len(df) < 55:
        return pd.Series(0, index=df.columns)
    ema_f = df.ewm(span=20, adjust=False).mean().iloc[-1]
    ema_s = df.ewm(span=50, adjust=False).mean().iloc[-1]
    return (ema_f > ema_s).astype(int)


def signal_macd_12_26(df):
    """MACD line > signal line → 1."""
    if len(df) < 40:
        return pd.Series(0, index=df.columns)
    ema_f = df.ewm(span=12, adjust=False).mean()
    ema_s = df.ewm(span=26, adjust=False).mean()
    macd = ema_f - ema_s
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    return (macd.iloc[-1] > macd_signal.iloc[-1]).astype(int)


def signal_donchian_20(df):
    """Close > 20-day high (shifted 1) → 1."""
    if len(df) < 25:
        return pd.Series(0, index=df.columns)
    upper = df.rolling(20).max().shift(1).iloc[-1]
    return (df.iloc[-1] > upper).astype(int)


# ═══════════════════════════════════════════════════════════════════
# MEAN_REV FAMILY (3)
# ═══════════════════════════════════════════════════════════════════

def signal_bb_20_2(df):
    """Price < lower Bollinger Band (20, 2σ) → 1 (oversold)."""
    if len(df) < 25:
        return pd.Series(0, index=df.columns)
    ma = df.rolling(20).mean().iloc[-1]
    sd = df.rolling(20).std().iloc[-1]
    return (df.iloc[-1] < ma - 2 * sd).astype(int)


def signal_rsi_14(df):
    """RSI(14) < 30 → 1 (oversold)."""
    if len(df) < 20:
        return pd.Series(0, index=df.columns)
    delta = df.diff()
    up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    down = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / down.replace(0, 1e-9))
    return (rsi.iloc[-1] < 30).astype(int)


def signal_zscore_20(df):
    """Z-score(20) < -2 → 1 (oversold)."""
    if len(df) < 25:
        return pd.Series(0, index=df.columns)
    ma = df.rolling(20).mean().iloc[-1]
    sd = df.rolling(20).std().iloc[-1]
    z = (df.iloc[-1] - ma) / sd.replace(0, 1e-9)
    return (z < -2.0).astype(int)


# ═══════════════════════════════════════════════════════════════════
# MOMENTUM FAMILY (3)
# ═══════════════════════════════════════════════════════════════════

def signal_roc_10(df):
    """10-day return > 0 → 1."""
    if len(df) < 15:
        return pd.Series(0, index=df.columns)
    ret = df.pct_change(10).iloc[-1]
    return (ret > 0).astype(int)


def signal_momentum_sma_20(df):
    """20-day return > 0 AND price > MA20 → 1."""
    if len(df) < 25:
        return pd.Series(0, index=df.columns)
    ret = df.pct_change(20).iloc[-1]
    ma = df.rolling(20).mean().iloc[-1]
    return ((ret > 0) & (df.iloc[-1] > ma)).astype(int)


def signal_rsi_momentum_14(df):
    """RSI(14) > 60 → 1 (momentum up)."""
    if len(df) < 20:
        return pd.Series(0, index=df.columns)
    delta = df.diff()
    up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    down = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / down.replace(0, 1e-9))
    return (rsi.iloc[-1] > 60).astype(int)


# ═══════════════════════════════════════════════════════════════════
# BREAKOUT FAMILY (3)
# ═══════════════════════════════════════════════════════════════════

def signal_atr_breakout_14(df):
    """Close > 20-day high + 1.5 * ATR → 1."""
    if len(df) < 25:
        return pd.Series(0, index=df.columns)
    high = df.rolling(20).max().shift(1).iloc[-1]
    atr = df.diff().abs().rolling(14).mean().iloc[-1]
    return (df.iloc[-1] > high + 1.5 * atr).astype(int)


def signal_bb_squeeze_20(df):
    """BB width < 20th percentile of last 50 days → 1 (squeeze)."""
    if len(df) < 75:
        return pd.Series(0, index=df.columns)
    ma = df.rolling(20).mean()
    sd = df.rolling(20).std()
    bb_width = (sd * 4) / ma.replace(0, 1e-9)
    current = bb_width.iloc[-1]
    threshold = bb_width.tail(50).quantile(0.2)
    return (current < threshold).astype(int)


def signal_donchian_break_20(df):
    """Close > 20-day high (shifted 2, confirmation) → 1."""
    if len(df) < 25:
        return pd.Series(0, index=df.columns)
    upper = df.rolling(20).max().shift(2).iloc[-1]
    return (df.iloc[-1] > upper).astype(int)


# ═══════════════════════════════════════════════════════════════════
# MAP: strategy name → function
# ═══════════════════════════════════════════════════════════════════

SIGNAL_FUNCTIONS = {
    # TREND
    "ema_cross_20_50": signal_ema_cross_20_50,
    "macd_12_26": signal_macd_12_26,
    "donchian_20": signal_donchian_20,
    # MEAN_REV
    "bb_20_2": signal_bb_20_2,
    "rsi_14": signal_rsi_14,
    "zscore_20": signal_zscore_20,
    # MOMENTUM
    "roc_10": signal_roc_10,
    "momentum_sma_20": signal_momentum_sma_20,
    "rsi_momentum_14": signal_rsi_momentum_14,
    # BREAKOUT
    "atr_breakout_14": signal_atr_breakout_14,
    "bb_squeeze_20": signal_bb_squeeze_20,
    "donchian_break_20": signal_donchian_break_20,
}
