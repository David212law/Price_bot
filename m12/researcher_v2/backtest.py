"""M12 Researcher v2 — backtest (evaluate)."""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORE = _HERE.parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from .loader import to_candles
from .config import FEE, REGIMES, START_MS, DAY_MS


def evaluate(symbols, btc_regimes, fee, n_btc, oos_start_idx=None, strategies=None):
    """backtest همه استراتژی‌ها."""
    from m12_strategies import STRATEGIES as DEFAULT_STRATEGIES

    if strategies is None:
        strategies = DEFAULT_STRATEGIES

    result = {s: {r: {"won": [], "ret": []} for r in REGIMES} for s in strategies}
    n_ok = 0

    for sym, prices in symbols.items():
        prices = prices[-n_btc:]
        if len(prices) < 300:
            continue
        n_ok += 1
        candles = to_candles(prices)

        for sname, sfn in strategies.items():
            try:
                trades = sfn(candles) or []
            except Exception:
                continue
            for t in trades:
                entry = t.get("t")
                if entry is None:
                    continue
                idx = int((entry - START_MS) / DAY_MS)
                if idx < 0 or idx >= n_btc:
                    continue
                if oos_start_idx is not None and idx >= oos_start_idx:
                    continue
                r = btc_regimes[idx]
                if r is None:
                    continue
                net = t["ret"] - fee
                result[sname][r]["won"].append(1 if net > 0 else 0)
                result[sname][r]["ret"].append(net)

    return result, n_ok


__all__ = ["evaluate"]


if __name__ == "__main__":
    from .loader import load_all_markets, label_regimes
    from .config import MAX_SYMBOLS, SPLIT_PCT
    from .metrics import compute_all_metrics
    from .export import export_full_report

    print("═══ backtest test ═══")
    markets = load_all_markets("data")
    print(f"TMN: {len(markets['TMN'])}  USDT: {len(markets['USDT'])}  GLOBAL: {len(markets['GLOBAL'])}")

    btc = markets["TMN"].get("BTC", [])
    if not btc:
        print("❌ BTC missing")
        sys.exit(1)

    btc_regimes = label_regimes(btc)
    n_btc = len(btc)
    split_idx = int(n_btc * SPLIT_PCT)
    print(f"BTC: {n_btc} days, SPLIT={split_idx}")

    tmn = dict(sorted(markets["TMN"].items(), key=lambda x: -len(x[1]))[:MAX_SYMBOLS])
    print(f"\n[TMN] backtest روی {len(tmn)} نماد...")

    result, n_ok = evaluate(tmn, btc_regimes, FEE["TMN"], n_btc, split_idx)
    print(f"✅ n_ok: {n_ok}/{len(tmn)}")

    metrics_df = compute_all_metrics(result)
    print(f"\nmetrics: {len(metrics_df)} rows")

    paths = export_full_report("results", metrics_df, {}, f"# Report\nTMN: {n_ok}\n", "backtest")
    print(f"\n✅ Export:")
    for k, v in paths.items():
        if v and v.exists():
            print(f"  {k}: {v}")
