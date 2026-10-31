"""Unified strategy registry — all 40 strategies in one place."""
from strategies.library.trend import TREND_STRATEGIES
from strategies.library.mean_reversion import MR_STRATEGIES
from strategies.library.momentum import MOMENTUM_STRATEGIES
from strategies.library.volatility import VOL_STRATEGIES
from strategies.library.volume import VOLUME_STRATEGIES
from strategies.library.funding import FUNDING_STRATEGIES

# Strategies that use candles (price-based)
CANDLE_STRATEGIES = {}
CANDLE_STRATEGIES.update(TREND_STRATEGIES)
CANDLE_STRATEGIES.update(MR_STRATEGIES)
CANDLE_STRATEGIES.update(MOMENTUM_STRATEGIES)
CANDLE_STRATEGIES.update(VOL_STRATEGIES)
CANDLE_STRATEGIES.update(VOLUME_STRATEGIES)

# Strategies that use funding data
FUNDING_STRATS = dict(FUNDING_STRATEGIES)

ALL_STRATEGIES = {**CANDLE_STRATEGIES, **FUNDING_STRATS}

def get_strategy(name):
    """Return (func, param_grid) for a strategy name."""
    if name in CANDLE_STRATEGIES:
        func, grid = CANDLE_STRATEGIES[name]
        return func, grid, "candle"
    if name in FUNDING_STRATS:
        func, grid = FUNDING_STRATS[name]
        return func, grid, "funding"
    raise KeyError(f"Unknown strategy: {name}")

def list_strategies():
    """Return list of (name, kind)."""
    out = []
    for name in CANDLE_STRATEGIES:
        out.append((name, "candle"))
    for name in FUNDING_STRATS:
        out.append((name, "funding"))
    return out

def expand_param_grid(grid):
    """Expand param grid to list of dicts. E.g. {"a":[1,2], "b":[3]} -> [{a:1,b:3},{a:2,b:3}]"""
    if not grid: return [{}]
    keys = list(grid.keys())
    combos = [{}]
    for k in keys:
        new = []
        for v in grid[k]:
            for c in combos:
                nc = dict(c); nc[k] = v
                new.append(nc)
        combos = new
    return combos

print(f"[registry] {len(CANDLE_STRATEGIES)} candle strategies, {len(FUNDING_STRATS)} funding strategies")
print(f"[registry] Total: {len(ALL_STRATEGIES)} strategies")
