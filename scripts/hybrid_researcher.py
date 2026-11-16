"""
Hybrid Researcher — 12 strategies, 12 regimes, static weights.

Philosophy (from M31 lesson):
  - NO optimization (no FDR, no Sharpe²)
  - Static weight allocation per regime
  - Fee-aware (Maker 0.01%, Taker 0.05%)
  - Detects current regime from BTC

Output: data/hybrid_weights.json
"""

import json
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts")
from hybrid_signals import SIGNAL_FUNCTIONS


# ═══════════════════════════════════════════════════════════════════
# 12 REGIMES
# ═══════════════════════════════════════════════════════════════════

REGIMES = [
    "BULL_STRONG", "BULL_NORMAL", "BULL_WEAK", "BULL_CALM",
    "FLAT_UP", "FLAT_DOWN", "FLAT_VOLATILE", "FLAT_CALM",
    "BEAR_MILD", "BEAR_NORMAL", "BEAR_VOLATILE", "CRASH",
]


# ═══════════════════════════════════════════════════════════════════
# 4 FAMILIES, 12 STRATEGIES (matching hybrid_signals.py)
# ═══════════════════════════════════════════════════════════════════

STRATEGY_MAP = {
    "TREND":    ["ema_cross_20_50", "macd_12_26", "donchian_20"],
    "MEAN_REV": ["bb_20_2", "rsi_14", "zscore_20"],
    "MOMENTUM": ["roc_10", "momentum_sma_20", "rsi_momentum_14"],
    "BREAKOUT": ["atr_breakout_14", "bb_squeeze_20", "donchian_break_20"],
}


# ═══════════════════════════════════════════════════════════════════
# STATIC ALLOCATION MATRIX (from M31 lesson: fixed, not optimized)
# ═══════════════════════════════════════════════════════════════════

REGIME_ALLOCATION = {
    # BULL family
    "BULL_STRONG":  {"TREND": 0.40, "MEAN_REV": 0.00, "MOMENTUM": 0.30, "BREAKOUT": 0.20, "CASH": 0.10},
    "BULL_NORMAL":  {"TREND": 0.30, "MEAN_REV": 0.10, "MOMENTUM": 0.30, "BREAKOUT": 0.20, "CASH": 0.10},
    "BULL_WEAK":    {"TREND": 0.20, "MEAN_REV": 0.30, "MOMENTUM": 0.20, "BREAKOUT": 0.20, "CASH": 0.10},
    "BULL_CALM":    {"TREND": 0.10, "MEAN_REV": 0.40, "MOMENTUM": 0.10, "BREAKOUT": 0.30, "CASH": 0.10},
    # FLAT family
    "FLAT_UP":      {"TREND": 0.00, "MEAN_REV": 0.50, "MOMENTUM": 0.00, "BREAKOUT": 0.40, "CASH": 0.10},
    "FLAT_DOWN":    {"TREND": 0.00, "MEAN_REV": 0.60, "MOMENTUM": 0.00, "BREAKOUT": 0.30, "CASH": 0.10},
    "FLAT_VOLATILE":{"TREND": 0.00, "MEAN_REV": 0.50, "MOMENTUM": 0.10, "BREAKOUT": 0.30, "CASH": 0.10},
    "FLAT_CALM":    {"TREND": 0.00, "MEAN_REV": 0.40, "MOMENTUM": 0.00, "BREAKOUT": 0.20, "CASH": 0.40},
    # BEAR family
    "BEAR_MILD":    {"TREND": 0.00, "MEAN_REV": 0.30, "MOMENTUM": 0.00, "BREAKOUT": 0.20, "CASH": 0.50},
    "BEAR_NORMAL":  {"TREND": 0.00, "MEAN_REV": 0.10, "MOMENTUM": 0.00, "BREAKOUT": 0.10, "CASH": 0.80},
    "BEAR_VOLATILE":{"TREND": 0.00, "MEAN_REV": 0.00, "MOMENTUM": 0.00, "BREAKOUT": 0.00, "CASH": 1.00},
    "CRASH":        {"TREND": 0.00, "MEAN_REV": 0.00, "MOMENTUM": 0.00, "BREAKOUT": 0.00, "CASH": 1.00},
}


# ═══════════════════════════════════════════════════════════════════
# REGIME DETECTION (12 regimes, based on ret_30d + vol_14d)
# ═══════════════════════════════════════════════════════════════════

def detect_regime(df):
    """Detect current regime from BTC data."""
    btc = df["BTC"] if "BTC" in df.columns else df.iloc[:, 0]
    ret_30 = float(btc.pct_change(30).iloc[-1])
    vol_14 = float(btc.pct_change().rolling(14).std().iloc[-1] * (365 ** 0.5))

    if ret_30 > 0.20 and vol_14 < 1.0:  return "BULL_STRONG"
    if ret_30 > 0.10 and vol_14 < 0.6:  return "BULL_NORMAL"
    if ret_30 > 0.05 and vol_14 < 0.4:  return "BULL_WEAK"
    if ret_30 > 0.02:                    return "BULL_CALM"
    if ret_30 > -0.02 and vol_14 < 0.3:  return "FLAT_CALM"
    if ret_30 > -0.02 and vol_14 < 0.6:  return "FLAT_VOLATILE"
    if ret_30 > -0.02:                    return "FLAT_UP"
    if ret_30 > -0.05:                    return "BEAR_MILD"
    if ret_30 > -0.10:                    return "BEAR_NORMAL"
    if ret_30 > -0.25:                    return "BEAR_VOLATILE"
    return "CRASH"


# ═══════════════════════════════════════════════════════════════════
# COMPUTE WEIGHTS (static, from matrix)
# ═══════════════════════════════════════════════════════════════════

def compute_weights(regime):
    """Compute per-strategy weight based on regime allocation."""
    alloc = REGIME_ALLOCATION[regime]
    weights = {}
    for family, family_weight in alloc.items():
        if family == "CASH":
            continue
        strats = STRATEGY_MAP[family]
        if not strats:
            continue
        per_strat = family_weight / len(strats)
        for strat in strats:
            weights[strat] = round(per_strat, 6)
    return weights


# ═══════════════════════════════════════════════════════════════════
# VALIDATION — verify matrix integrity
# ═══════════════════════════════════════════════════════════════════

def validate_matrix():
    """Verify each regime's allocation sums to 1.0."""
    errors = []
    for regime in REGIMES:
        total = sum(REGIME_ALLOCATION[regime].values())
        if abs(total - 1.0) > 0.001:
            errors.append(f"{regime}: sum={total:.4f} (expected 1.0)")
    return errors


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 80)
    print(" 🔬 HYBRID RESEARCHER — 12 strategies × 12 regimes")
    print("=" * 80)

    # 1. Validate matrix
    errors = validate_matrix()
    if errors:
        print("❌ Matrix validation failed:")
        for e in errors:
            print(f"  {e}")
        return
    print("✅ Matrix: all 12 regimes sum to 1.0")
    print()

    # 2. Load data
    try:
        raw = json.load(open("data/wallex_tmn_all.json"))
        df_dict = {}
        for k, v in raw.items():
            if k == "USDTTMN":
                continue
            if not k.endswith("TMN"):
                continue
            if len(v) < 100:
                continue
            df_dict[k[:-3]] = pd.Series(v)
        df = pd.DataFrame(df_dict)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().ffill()
        print(f"✅ Data: {len(df.columns)} assets × {len(df)} days")
    except Exception as e:
        print(f"❌ Data load failed: {e}")
        return

    # 3. Detect current regime
    regime = detect_regime(df)
    print(f"📍 Current regime: {regime}")
    print()

    # 4. Compute weights
    weights = compute_weights(regime)
    cash_weight = REGIME_ALLOCATION[regime].get("CASH", 0)
    print(f"📊 Weights ({len(weights)} strategies + {cash_weight:.2f} cash):")
    for s in sorted(weights.keys()):
        print(f"  {s:25s}: {weights[s]:.4f}")
    print(f"  {'CASH':25s}: {cash_weight:.4f}")
    print()

    # 5. Compute current signals (how many assets active per strategy)
    print("🎯 Current signals (active assets per strategy):")
    active_signals = {}
    for name, fn in SIGNAL_FUNCTIONS.items():
        try:
            sig = fn(df)
            n_active = int(sig.sum()) if hasattr(sig, "sum") else 0
            active_signals[name] = n_active
            print(f"  {name:25s}: {n_active}/{len(sig)} assets")
        except Exception as e:
            print(f"  {name:25s}: ❌ {e}")
            active_signals[name] = 0
    print()

    # 6. Save output
    output = {
        "regime": regime,
        "weights": weights,
        "cash_weight": cash_weight,
        "active_signals": active_signals,
        "total_cash_target": cash_weight,
        "last_update": pd.Timestamp.now().isoformat(),
    }
    os.makedirs("data", exist_ok=True)
    with open("data/hybrid_weights.json", "w") as f:
        json.dump(output, f, indent=2)
    print("✅ Saved to data/hybrid_weights.json")


if __name__ == "__main__":
    main()
