"""D-550: Regime Detector v2 — economic signals, not data fitting.

Detects market regime from:
  - funding_rate (7-day mean)
  - funding_vol (7-day std)
  - btc_vol (14-day realized volatility)
  - btc_trend (7-day cumulative return)
  - adx (14-day trend strength)

Output: one of 8 regimes (see registry.json).

Design: NO optimization, NO data fitting. Pure economic thresholds.
"""
from datetime import datetime, timezone
from pathlib import Path
import json


# ═══ Economic thresholds (NOT fitted to data) ═══
FUNDING_NEGATIVE = -0.0002      # funding < -0.01% → negative regime
FUNDING_POSITIVE_STRONG = 0.0003 # funding > 0.03% → strong positive
FUNDING_VOL_HIGH = 0.0005        # funding std > 0.05% → unstable
BTC_VOL_LOW = 0.02             # < 1.5% daily → low vol
BTC_VOL_HIGH = 0.04             # > 3% daily → high vol
BTC_VOL_SPIKE = 0.07            # > 5% daily → crisis
TREND_THRESHOLD = 0.08          # 7-day return > 3% → trending
ADX_TREND = 30                  # ADX > 25 → trend


def detect_regime(funding_history, btc_rets_history, adx=None):
    """Detect regime from past data.
    
    Args:
        funding_history: list of recent funding rates (last 7 days)
        btc_rets_history: list of recent BTC daily returns (last 14 days)
        adx: current ADX (optional)
    
    Returns:
        dict with regime, confidence, signals
    """
    signals = {}
    
    # ═══ Funding signals ═══
    if funding_history and len(funding_history) >= 3:
        f_mean = sum(funding_history) / len(funding_history)
        f_var = sum((f - f_mean)**2 for f in funding_history) / len(funding_history)
        f_vol = f_var ** 0.5
    else:
        f_mean, f_vol = 0, 0
    
    signals["funding_mean"] = round(f_mean, 6)
    signals["funding_vol"] = round(f_vol, 6)
    
    # ═══ BTC signals ═══
    if btc_rets_history and len(btc_rets_history) >= 7:
        b_mean = sum(btc_rets_history) / len(btc_rets_history)
        b_var = sum((r - b_mean)**2 for r in btc_rets_history) / len(btc_rets_history)
        b_vol = b_var ** 0.5
        b_trend = sum(btc_rets_history[-7:])
    else:
        b_vol, b_trend = 0, 0
    
    signals["btc_vol"] = round(b_vol, 6)
    signals["btc_trend"] = round(b_trend, 6)
    signals["adx"] = adx
    
    # ═══ Regime classification (economic rules) ═══
    # Priority: CRISIS > TREND > RANGE
    if f_mean < FUNDING_NEGATIVE:
        return {"regime": "CRISIS_NEGATIVE_FUNDING", "confidence": 0.9, "signals": signals}
    
    if b_vol > BTC_VOL_SPIKE or f_vol > FUNDING_VOL_HIGH:
        return {"regime": "CRISIS_VOL_SPIKE", "confidence": 0.8, "signals": signals}
    
    is_trending = (adx and adx > ADX_TREND) or abs(b_trend) > TREND_THRESHOLD
    if is_trending and b_trend > 0:
        return {"regime": "TREND_UP", "confidence": 0.7, "signals": signals}
    if is_trending and b_trend < 0:
        return {"regime": "TREND_DOWN", "confidence": 0.7, "signals": signals}
    
    if b_vol < BTC_VOL_LOW:
        return {"regime": "RANGE_LOW_VOL", "confidence": 0.7, "signals": signals}
    if b_vol < BTC_VOL_HIGH:
        return {"regime": "RANGE_MED_VOL", "confidence": 0.7, "signals": signals}
    
    return {"regime": "RANGE_HIGH_VOL", "confidence": 0.6, "signals": signals}


def detect_from_files(exchange="aster", symbol="BTCUSDT"):
    """Convenience: detect regime from local files."""
    from datetime import datetime, timezone
    
    funding_paths = [
        f"exchanges/{exchange}/data/{symbol}_funding.json",
        f"data/{exchange}/{symbol}_funding.json"
    ]
    prices_paths = [
        f"data/{exchange}/{symbol}_1d.json",
    ]
    
    funding_hist = []
    for p in funding_paths:
        if Path(p).exists():
            try:
                data = json.loads(Path(p).read_text())
                if isinstance(data, dict):
                    dates = sorted(data.keys())[-7:]
                    funding_hist = [data[d] for d in dates if isinstance(data[d], (int, float))]
                elif isinstance(data, list):
                    vals = []
                    for item in data[-21:]:  # last 21 records (7 days * 3 per day)
                        if isinstance(item, dict):
                            r = item.get("rate") or item.get("fundingRate")
                            if r is not None: vals.append(float(r))
                    funding_hist = vals[-7:]
                break
            except Exception:
                pass
    
    btc_rets = []
    btc_prices = {}
    for p in prices_paths:
        if Path(p).exists():
            try:
                data = json.loads(Path(p).read_text())
                for c in data[-15:]:
                    if isinstance(c, dict):
                        t = c.get("t") or c.get("timestamp")
                        cl = c.get("c") or c.get("close")
                        if t and cl:
                            d = str(t)[:10]
                            btc_prices[d] = float(cl)
                dates = sorted(btc_prices.keys())
                for i in range(1, len(dates)):
                    btc_rets.append((btc_prices[dates[i]] - btc_prices[dates[i-1]]) / btc_prices[dates[i-1]])
                break
            except Exception:
                pass
    
    return detect_regime(funding_hist, btc_rets)


if __name__ == "__main__":
    result = detect_from_files()
    print(f"Regime: {result['regime']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Signals: {result['signals']}")
