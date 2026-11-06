"""D-550: Hybrid Manager — selects strategies by regime.

Philosophy:
  - Strategies are chosen by ECONOMIC ROLE, not by backtested SR.
  - The regime determines which strategies are active.
  - No optimization. No fitting. Pure rule-based.

Input: regime (from detector) + registry
Output: list of (strategy, weight) for this regime

Note: This manager does NOT execute trades. It only produces
      a portfolio recommendation. Paper bots consume it.
"""
import json
from pathlib import Path


REGISTRY_PATH = Path("strategies/registry/registry.json")


def load_registry():
    if not REGISTRY_PATH.exists():
        return None
    return json.loads(REGISTRY_PATH.read_text())


def select_portfolio(regime, registry=None):
    """Given a regime, return active strategies with normalized weights.
    
    Returns:
        {
            "regime": str,
            "strategies": [{"name": str, "weight": float}, ...],
            "total_weight": float,
            "notes": str
        }
    """
    if registry is None:
        registry = load_registry()
    if registry is None:
        return {"error": "registry not found"}
    
    if regime not in registry["regimes"]:
        return {"error": f"unknown regime: {regime}"}
    
    active = []
    for name, meta in registry["strategies"].items():
        w = meta["regime_weights"].get(regime, 0)
        if w > 0:
            active.append({"name": name, "weight": w})
    
    # Normalize to sum = 1.0
    total = sum(s["weight"] for s in active)
    if total > 0:
        for s in active:
            s["weight"] = round(s["weight"] / total, 3)
    
    return {
        "regime": regime,
        "strategies": active,
        "total_weight_before_norm": round(total, 3),
        "n_active": len(active)
    }


def describe_portfolio(regime):
    """Human-readable portfolio description."""
    portfolio = select_portfolio(regime)
    if "error" in portfolio:
        return f"ERROR: {portfolio['error']}"
    
    lines = [f"Regime: {regime}"]
    for s in portfolio["strategies"]:
        lines.append(f"  {s['weight']*100:>5.1f}%  {s['name']}")
    return "\n".join(lines)


if __name__ == "__main__":
    from research_lab.regime_detector_v2 import detect_from_files
    
    result = detect_from_files()
    regime = result["regime"]
    
    print(f"Detected regime: {regime}")
    print(f"Confidence: {result['confidence']}")
    print()
    print("Active portfolio:")
    print(describe_portfolio(regime))
