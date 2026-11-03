"""Unified strategy registry — all 40 strategies in one place."""
from strategies.library.trend import TREND_STRATEGIES
from strategies.library.mean_reversion import MR_STRATEGIES
from strategies.library.momentum import MOMENTUM_STRATEGIES
from strategies.library.volatility import VOL_STRATEGIES
from strategies.library.volume import VOLUME_STRATEGIES
from strategies.library.funding import FUNDING_STRATEGIES
from strategies.library.exotic import CANDLE_STRATEGIES as EXOTIC_STRATEGIES

# Strategies that use candles (price-based)
CANDLE_STRATEGIES = {}
CANDLE_STRATEGIES.update(TREND_STRATEGIES)
CANDLE_STRATEGIES.update(MR_STRATEGIES)
CANDLE_STRATEGIES.update(MOMENTUM_STRATEGIES)
CANDLE_STRATEGIES.update(VOL_STRATEGIES)
CANDLE_STRATEGIES.update(VOLUME_STRATEGIES)
CANDLE_STRATEGIES.update(EXOTIC_STRATEGIES)

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

# D-508: Expansion strategies (Phase 1: Trend)
try:
    from strategies.library.expansion_generated import TREND_STRATEGIES as _EXP_TREND
    CANDLE_STRATEGIES.update(_EXP_TREND)
    ALL_STRATEGIES.update(_EXP_TREND)
    print(f"[registry] D-508 expansion: +{len(_EXP_TREND)} trend strategies")
except ImportError as _e:
    print(f"[registry] D-508 expansion not loaded: {_e}")

# D-508: Expansion Phase 2 (MR + Momentum + Vol + Volume + Funding proxies)
try:
    from strategies.library.expansion_phase2 import PHASE2_CANDLE as _EXP_PHASE2
    CANDLE_STRATEGIES.update(_EXP_PHASE2)
    ALL_STRATEGIES.update(_EXP_PHASE2)
    print(f"[registry] D-508 phase2: +{len(_EXP_PHASE2)} strategies")
except ImportError as _e:
    print(f"[registry] D-508 phase2 not loaded: {_e}")
