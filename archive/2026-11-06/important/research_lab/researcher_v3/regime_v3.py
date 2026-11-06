"""D-553: Regime Detector v3 — per-asset thresholds."""
from datetime import datetime, timezone

PER_ASSET_THRESHOLDS = {
    "BTC-USD":   {"vol_low": 0.020, "vol_high": 0.040, "vol_spike": 0.070},
    "ETH-USD":   {"vol_low": 0.025, "vol_high": 0.050, "vol_spike": 0.080},
    "SOL-USD":   {"vol_low": 0.030, "vol_high": 0.060, "vol_spike": 0.100},
    "Gold":      {"vol_low": 0.008, "vol_high": 0.015, "vol_spike": 0.025},
    "Oil":       {"vol_low": 0.015, "vol_high": 0.030, "vol_spike": 0.050},
    "SP500":     {"vol_low": 0.007, "vol_high": 0.015, "vol_spike": 0.025},
    "USDTTMN":   {"vol_low": 0.003, "vol_high": 0.008, "vol_spike": 0.015},
    "Iran_BTC":  {"vol_low": 0.030, "vol_high": 0.060, "vol_spike": 0.100},
    "DEFAULT":   {"vol_low": 0.020, "vol_high": 0.040, "vol_spike": 0.070},
}

FUNDING_NEGATIVE = -0.0002
FUNDING_VOL_HIGH = 0.0005
TREND_THRESHOLD = 0.08
ADX_TREND = 30
MA_PERIOD = 50
CONFIRM_DAYS = 3

def detect_regime(asset, prices, funding_history, current_date, adx=None):
    thresh = PER_ASSET_THRESHOLDS.get(asset, PER_ASSET_THRESHOLDS["DEFAULT"])
    dates = sorted([d for d in prices.keys() if d <= current_date])[-60:]
    if len(dates) < MA_PERIOD:
        return {"regime": "UNKNOWN", "confidence": 0, "signals": {}}
    returns = []
    for i in range(1, len(dates)):
        p0 = prices[dates[i-1]]
        p1 = prices[dates[i]]
        if p0 > 0:
            returns.append((p1 - p0) / p0)
    if len(returns) < 20:
        return {"regime": "UNKNOWN", "confidence": 0, "signals": {}}
    recent = returns[-20:]
    mean_r = sum(recent) / len(recent)
    var = sum((r - mean_r)**2 for r in recent) / len(recent)
    current_vol = var ** 0.5
    trend_7d = sum(returns[-7:]) if len(returns) >= 7 else 0
    ma50 = sum([prices[d] for d in dates[-MA_PERIOD:]]) / MA_PERIOD
    current_price = prices[dates[-1]]
    below_ma = current_price < ma50
    f_dates = sorted([d for d in funding_history.keys() if d <= current_date])[-7:]
    f_vals = [funding_history[d] for d in f_dates]
    f_mean = sum(f_vals) / len(f_vals) if f_vals else 0
    f_vol = 0
    if f_vals:
        f_var = sum((f - f_mean)**2 for f in f_vals) / len(f_vals)
        f_vol = f_var ** 0.5
    signals = {
        "vol": round(current_vol, 4),
        "trend_7d": round(trend_7d, 4),
        "funding_mean": round(f_mean, 6),
        "funding_vol": round(f_vol, 6),
        "below_ma50": below_ma,
        "adx": adx,
    }
    if f_mean < FUNDING_NEGATIVE:
        return {"regime": "CRISIS_NEGATIVE_FUNDING", "confidence": 0.9, "signals": signals}
    if current_vol > thresh["vol_spike"] or f_vol > FUNDING_VOL_HIGH:
        return {"regime": "CRISIS_VOL_SPIKE", "confidence": 0.8, "signals": signals}
    is_trending = (adx and adx > ADX_TREND) or abs(trend_7d) > TREND_THRESHOLD
    if is_trending and trend_7d > 0:
        return {"regime": "TREND_UP", "confidence": 0.7, "signals": signals}
    if is_trending and trend_7d < 0:
        return {"regime": "TREND_DOWN", "confidence": 0.7, "signals": signals}
    if current_vol < thresh["vol_low"]:
        return {"regime": "RANGE_LOW_VOL", "confidence": 0.7, "signals": signals}
    if current_vol < thresh["vol_high"]:
        return {"regime": "RANGE_MED_VOL", "confidence": 0.7, "signals": signals}
    return {"regime": "RANGE_HIGH_VOL", "confidence": 0.6, "signals": signals}

def detect_regime_series(asset, prices, funding_history, adx_series=None):
    results = {}
    for d in sorted(prices.keys())[MA_PERIOD + 20:]:
        adx = adx_series.get(d) if adx_series else None
        results[d] = detect_regime(asset, prices, funding_history, d, adx)
    return results
