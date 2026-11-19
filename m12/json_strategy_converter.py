"""Convert all_strategies_unified.json → Python strategies.
Best-effort: only handles common patterns (ema_cross, rsi, bb, etc.)
Auto-skipped: unknown patterns."""
import json, os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
JSON_FILE = os.path.join(_ROOT, "data", "all_strategies_unified.json")
OUT_FILE = os.path.join(_HERE, "auto_strategies.py")

# Pattern → Python function generator
PATTERNS = {
    r"^ema_cross_(\d+)_(\d+)$": lambda m: f"ema_cross_{m[0]}_{m[1]}",
    r"^sma_cross_(\d+)_(\d+)$": lambda m: f"sma_cross_{m[0]}_{m[1]}",
    r"^rsi_(\d+)_(\d+)_(\d+)$": lambda m: f"rsi_{m[0]}_{m[1]}_{m[2]}",
    r"^bb_(\d+)_([\d.]+)$": lambda m: f"bb_{m[0]}_{m[1]}",
    r"^roc_(\d+)$": lambda m: f"roc_{m[0]}",
}

def main():
    if not os.path.exists(JSON_FILE):
        print(f"No {JSON_FILE}"); return
    
    raw = json.load(open(JSON_FILE))
    print(f"Loaded JSON: {type(raw).__name__}, keys: {len(raw) if isinstance(raw, (dict, list)) else '?'}")
    
    # Try to identify structure
    if isinstance(raw, dict) and "strategies" in raw:
        inner = raw["strategies"]
        if isinstance(inner, list):
            names = [s.get("name") or s.get("id") or f"s{i}" for i, s in enumerate(inner)]
        else:
            names = list(inner.keys())
    elif isinstance(raw, dict):
        names = list(raw.keys())
    elif isinstance(raw, list):
        names = [s.get("name") or s.get("id") or f"s{i}" for i, s in enumerate(raw)]
    else:
        print("Unknown structure"); return
    
    print(f"Found {len(names)} strategies")
    print(f"Sample: {names[:5]}")
    
    # Names are "exchange::STRATEGY_NAME::SYMBOL"
    from collections import Counter
    unique_strats = Counter()
    for n in names:
        parts = n.split("::")
        if len(parts) == 3:
            unique_strats[parts[1]] += 1
    
    print(f"Unique strategy types: {len(unique_strats)}")
    print(f"Sample: {list(unique_strats.keys())[:10]}")
    
    # Match against existing m12_strategies
    import sys
    sys.path.insert(0, _HERE)
    try:
        from m12_strategies import STRATEGIES
        existing = set(STRATEGIES.keys())
    except Exception:
        existing = set()
    
    matched = []  # available in our lib
    missing = []  # in JSON but not in lib
    for strat_name in unique_strats:
        # Normalize: EMA_CROSS → ema_cross
        normalized = strat_name.lower()
        # Try with symbol
        if normalized in existing:
            matched.append(strat_name)
        elif "ema_cross" in normalized and "ema_cross_20_50" in existing:
            matched.append(strat_name)
        else:
            missing.append(strat_name)
    
    print(f"Matched to existing lib: {len(matched)} unique types")
    print(f"Missing from lib: {len(missing)} unique types")
    print(f"Missing examples: {missing[:10]}")
    
    with open(OUT_FILE, "w") as f:
        f.write('"""Strategy coverage report."""\n')
        f.write(f"COVERED = {repr(sorted(set(matched)))}\n\n")
        f.write(f"MISSING = {repr(sorted(set(missing)))}\n")
    print(f"✅ Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
