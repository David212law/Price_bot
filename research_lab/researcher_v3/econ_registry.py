"""D-553: Economic Registry — strategies with economic roles + per-asset defaults."""
import json
from pathlib import Path

REGISTRY_PATH = Path("strategies/registry/econ_registry.json")

DEFAULT_REGISTRY = {
    "version": "2.0",
    "created": "2026-11-06",
    "design_principle": "Economic role + per-asset defaults + regime compatibility",
    "roles": {
        "funding_carry": {
            "thesis_fa": "پول از funding rate مثبت جابه‌جا می‌شود",
            "compatible_regimes": ["TREND_UP", "TREND_DOWN", "RANGE_LOW_VOL"],
            "fails_in": ["CRISIS_NEGATIVE_FUNDING", "CRISIS_VOL_SPIKE"],
        },
        "mean_reversion": {
            "thesis_fa": "بازگشت به میانگین در بازار رِنج",
            "compatible_regimes": ["RANGE_LOW_VOL", "RANGE_MED_VOL"],
            "fails_in": ["TREND_UP", "TREND_DOWN"],
        },
        "trend_following": {
            "thesis_fa": "پیروی از روند در بازار ترند",
            "compatible_regimes": ["TREND_UP", "TREND_DOWN"],
            "fails_in": ["RANGE_LOW_VOL", "CRISIS_VOL_SPIKE"],
        },
        "momentum": {
            "thesis_fa": "مومنتوم در بازار emerging",
            "compatible_regimes": ["TREND_UP"],
            "fails_in": ["RANGE_LOW_VOL", "CRISIS_NEGATIVE_FUNDING"],
        },
        "cash": {
            "thesis_fa": "سرمایه در cash",
            "compatible_regimes": ["CRISIS_NEGATIVE_FUNDING", "CRISIS_VOL_SPIKE"],
            "fails_in": [],
        },
    },
    "strategies": {
        "M31": {
            "role": "funding_carry",
            "default": True,
            "hedge_required": True,
        },
        "KELTNER_REV": {
            "role": "mean_reversion",
            "hedge_required": False,
        },
        "M31_MOMENTUM": {
            "role": "momentum",
            "default": False,
            "deprecated": True,
            "deprecated_reason": "corr=0.999 with M31 (D-522)",
        },
    },
    "per_asset_baselines": {
        "BTC-USD": {"default": "Breakout", "thesis": "speculative, needs trend"},
        "Gold": {"default": "Buy&Hold", "thesis": "store of value"},
        "Oil": {"default": "MeanRev", "thesis": "commodity cycles"},
        "SP500": {"default": "Breakout", "thesis": "secular bull"},
        "Iran_BTC": {"default": "Momentum", "thesis": "emerging asset"},
        "USDTTMN": {"default": "Breakout", "thesis": "Toman market"},
    },
}

def load_registry():
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text())
        except Exception:
            pass
    return DEFAULT_REGISTRY

def save_registry(registry):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False))

def get_strategies_for_regime(registry, regime):
    result = []
    for name, meta in registry["strategies"].items():
        if meta.get("deprecated"):
            continue
        role = meta["role"]
        if role in registry["roles"]:
            if regime in registry["roles"][role]["compatible_regimes"]:
                result.append({"strategy": name, "role": role, "meta": meta})
    return result

def get_default_for_asset(registry, asset):
    if asset in registry["per_asset_baselines"]:
        return registry["per_asset_baselines"][asset]["default"]
    return "Buy&Hold"

if __name__ == "__main__":
    reg = load_registry()
    print(f"Registry version: {reg['version']}")
    print(f"Strategies: {list(reg['strategies'].keys())}")
    print(f"Assets: {list(reg['per_asset_baselines'].keys())}")
