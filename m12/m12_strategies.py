"""M12 Strategies — auto-built from full project registry (all candle strategies + param variants)."""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from strategies.library.registry import CANDLE_STRATEGIES, expand_param_grid

def _make(func, combo):
    def run(candles, _f=func, _c=combo):
        try:
            return _f(candles, **_c) if _c else _f(candles)
        except Exception:
            return []
    return run

def _combo_key(combo):
    return "__".join(f"{k}{v}" for k, v in combo.items())

STRATEGIES = {}
for name, (func, grid) in CANDLE_STRATEGIES.items():
    combos = expand_param_grid(grid or {})
    for combo in combos:
        variant = f"{name}__{_combo_key(combo)}" if combo else name
        STRATEGIES[variant] = _make(func, combo)

if __name__ == "__main__":
    print(f"Loaded {len(STRATEGIES)} strategy variants into STRATEGIES")
    print("Sample:", list(STRATEGIES)[:10])
