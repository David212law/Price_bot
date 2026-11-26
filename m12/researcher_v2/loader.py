"""M12 Researcher v2 — loader (تنها منبع برای load/transform).

قبل از این، `_load` و `to_candles` در prefilter.py و researcher.py تکرار شده بود.
حالا فقط اینجاست.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORE = _HERE.parent
_ROOT = _CORE.parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from calc import regime_label


def load_prices(
    path: str | Path,
    suffix: str | None = None,
    min_length: int = 300,
) -> dict[str, list[float]]:
    """بارگیری قیمت‌ها از یک فایل JSON."""
    path = Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    out: dict[str, list[float]] = {}
    for key, value in raw.items():
        if not isinstance(value, (list, dict)):
            continue
        if len(value) < min_length:
            continue
        if suffix:
            if not key.endswith(suffix):
                continue
            symbol = key[: -len(suffix)]
        else:
            symbol = key
        if isinstance(value, dict):
            items = sorted(value.items(), key=lambda kv: kv[0])
            prices = [float(x) for _, x in items]
        else:
            prices = [float(x) for x in value]
        if len(prices) >= min_length:
            out[symbol] = prices
    return out


def label_regimes(btc_prices: list[float], lookback: int = 30) -> list[str | None]:
    """برچسب‌گذاری regime برای هر روز بر اساس BTC."""
    regimes: list[str | None] = [None] * len(btc_prices)
    for i in range(lookback + 1, len(btc_prices)):
        change = btc_prices[i] / btc_prices[i - lookback] - 1
        regimes[i] = regime_label(change)
    return regimes


def to_candles(prices: list[float]) -> list[dict]:
    """تبدیل لیست قیمت به candles."""
    from .config import START_MS, DAY_MS, SPREAD
    return [
        {
            "t": START_MS + i * DAY_MS,
            "o": p,
            "h": p * (1 + SPREAD),
            "l": p * (1 - SPREAD),
            "c": p,
            "v": 1.0,
        }
        for i, p in enumerate(prices)
    ]


def load_all_markets(data_dir: str = "data") -> dict[str, dict[str, list[float]]]:
    """بارگیری همه بازارها: TMN, USDT, GLOBAL."""
    return {
        "TMN": load_prices(os.path.join(data_dir, "wallex_tmn_all.json"), "TMN"),
        "USDT": load_prices(os.path.join(data_dir, "wallex_usdt_all.json"), "USDT"),
        "GLOBAL": load_prices(os.path.join(data_dir, "crypto_5y_usd.json")),
    }


__all__ = ["load_prices", "label_regimes", "to_candles", "load_all_markets"]
