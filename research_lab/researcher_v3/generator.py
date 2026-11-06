"""D-558: Strategy Generator — Generate variants from existing edges.

NOT from scratch — parameter sweep on M31 and Keltner (the 2 proven edges).
This is honest: we only have 2 real edges, so generator produces their variants.
"""
import json
from pathlib import Path
from datetime import datetime, timezone


# Only 2 real edges (D-543, D-552): M31 (funding) + Keltner (mean reversion)
GENERATOR_SPECS = {
    "M31": {
        "thesis": "funding_carry",
        "base_strategy": "M31_EMA",
        "variants": [
            {"lookback": 7, "label": "M31_fast"},
            {"lookback": 20, "label": "M31_normal"},
            {"lookback": 50, "label": "M31_slow"},
        ],
        "exchanges": ["hyperliquid", "aster", "kucoin"],
        "symbols": ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"],
    },
    "Keltner": {
        "thesis": "mean_reversion",
        "base_strategy": "KELTNER_REV",
        "variants": [
            {"period": 14, "mult": 1.5, "label": "Keltner_fast"},
            {"period": 20, "mult": 2.0, "label": "Keltner_normal"},
            {"period": 30, "mult": 2.5, "label": "Keltner_slow"},
        ],
        "exchanges": ["hyperliquid", "aster", "kucoin"],
        "symbols": ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"],
    },
}


def generate_strategies():
    """Generate strategy candidates (parameter variants of 2 real edges)."""
    candidates = []
    for edge_name, spec in GENERATOR_SPECS.items():
        for variant in spec["variants"]:
            for exch in spec["exchanges"]:
                for sym in spec["symbols"]:
                    candidates.append({
                        "edge": edge_name,
                        "thesis": spec["thesis"],
                        "base": spec["base_strategy"],
                        "variant": variant["label"],
                        "params": {k: v for k, v in variant.items() if k != "label"},
                        "exchange": exch,
                        "symbol": sym,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    })
    return candidates


def main():
    candidates = generate_strategies()
    out = Path("research_lab/logs/researcher_v3/generated_candidates.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_candidates": len(candidates),
        "candidates": candidates,
    }, indent=2))
    print(f"✅ Generated {len(candidates)} candidates")
    print(f"   (M31 variants: {len([c for c in candidates if c['edge']=='M31'])})")
    print(f"   (Keltner variants: {len([c for c in candidates if c['edge']=='Keltner'])})")
    print(f"   → {out}")


if __name__ == "__main__":
    main()
