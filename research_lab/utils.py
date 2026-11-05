"""D-531: Shared utility functions. Single source of truth."""
import json
from pathlib import Path


def sharpe(vals, periods=365):
    if not vals or len(vals) < 10:
        return 0.0
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / len(vals)
    sd = var ** 0.5
    return (m / sd) * (periods ** 0.5) if sd > 0 else 0.0


def corr(a, b, dates):
    if len(dates) < 30:
        return 0.0
    va = [a.get(d, 0.0) for d in dates]
    vb = [b.get(d, 0.0) for d in dates]
    ma = sum(va) / len(va)
    mb = sum(vb) / len(vb)
    cov = sum((va[i] - ma) * (vb[i] - mb) for i in range(len(va)))
    sa = sum((x - ma) ** 2 for x in va) ** 0.5
    sb = sum((x - mb) ** 2 for x in vb) ** 0.5
    return round(cov / (sa * sb), 3) if sa * sb > 0 else 0.0


def compute_momentum(history, lookback=6):
    if len(history) < lookback * 2:
        return None
    recent = [r["rate"] for r in history[-lookback:]]
    older = [r["rate"] for r in history[:lookback]]
    return sum(recent) / len(recent), sum(older) / len(older), history[-1]["rate"]


def load_returns_file(exchange, strategy, hash_val, symbol):
    p = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}/{strategy}_{hash_val}_{symbol}.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}
