"""
Source of Truth for Regime Detection, Statistics, and Portfolio Logic.
تمام ماژول‌ها باید از این فایل import کنند.
"""
import math, random
from datetime import datetime, timezone

# ═══════════════ ADX (تنها نسخه) ═══════════════
def calc_adx(candles, period=14):
    if len(candles) < period * 2:
        return None
    trs, pdms, mdms = [], [], []
    for i in range(1, len(candles)):
        h, l = candles[i]["h"], candles[i]["l"]
        ph, pl, pc = candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
        up, dn = h - ph, pl - l
        pdms.append(up if (up > dn and up > 0) else 0)
        mdms.append(dn if (dn > up and dn > 0) else 0)
    if len(trs) < period: return None
    atr = sum(trs[:period]) / period
    ps, ms = sum(pdms[:period]), sum(mdms[:period])
    dxs = []
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        ps = ps - ps/period + pdms[i]
        ms = ms - ms/period + mdms[i]
        if atr == 0: dx = 0
        else:
            pdi = 100 * ps / (atr * period)
            mdi = 100 * ms / (atr * period)
            dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0
        dxs.append(dx)
    if len(dxs) < period: return None
    adx = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        adx = (adx * (period - 1) + dxs[i]) / period
    return adx

# ═══════════════ Regime Classification ═══════════════
REGIME_TREND_THRESHOLD = 25
REGIME_RANGE_THRESHOLD = 20
REGIME_WINDOW_CANDLES = 60  # فقط 60 کندل اخیر

def detect_regime(candles, i=None, window=None):
    """رژیم بازار در لحظه i. اگر i=None، آخرین کندل."""
    if window is None:
        window = REGIME_WINDOW_CANDLES
    if i is None:
        i = len(candles) - 1
    if i < window: return "UNKNOWN"
    sub = candles[max(0, i-window):i+1]
    adx = calc_adx(sub, 14)
    if adx is None: return "UNKNOWN"
    if adx > REGIME_TREND_THRESHOLD: return "TREND"
    if adx < REGIME_RANGE_THRESHOLD: return "RANGE"
    return "NEUTRAL"

# ═══════════════ Strategy Activation Rules ═══════════════
STRATEGY_RULES = {
    "M31":              {"TREND", "RANGE", "NEUTRAL"},
    "M62_PriceMomentum": {"TREND"},
    "M40_Pullback":     {"RANGE"},
    "A20_SuperTrend":   {"TREND", "RANGE"},
    "A8_Grid":          {"RANGE"},
}

def should_activate_strategy(strategy_name, regime):
    return regime in STRATEGY_RULES.get(strategy_name, {"TREND", "RANGE", "NEUTRAL"})

# ═══════════════ Bootstrap P-Value (تنها نسخه) ═══════════════
def bootstrap_p(rets, block_size=6, iterations=1000, seed=42):
    n = len(rets)
    if n < 15: return 1.0
    mean = sum(rets) / n
    if mean <= 0: return 1.0
    std = math.sqrt(sum((r - mean)**2 for r in rets) / (n - 1))
    if std == 0: return 0.0
    rng = random.Random(seed)
    better = 0
    for _ in range(iterations):
        sample = [rng.gauss(0, std) for _ in range(n)]
        if sum(sample) / n >= mean:
            better += 1
    return better / iterations

# ═══════════════ Holm-Bonferroni (تنها نسخه) ═══════════════
def holm_bonferroni(p_vals, alpha=0.05):
    n = len(p_vals)
    order = sorted(range(n), key=lambda i: p_vals[i])
    passed = [False] * n
    for k, idx in enumerate(order):
        if p_vals[idx] <= alpha / (n - k):
            passed[idx] = True
        else:
            break
    return passed

# ═══════════════ Version ═══════════════
VERSION = "1.0.0"
VERSION_DATE = "2026-10-31"

def get_version_info():
    return {"version": VERSION, "date": VERSION_DATE}
