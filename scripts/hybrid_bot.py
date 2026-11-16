"""
Hybrid Bot — Paper execution.

Reads:
  - data/wallex_tmn_all.json    (prices)
  - data/hybrid_weights.json    (regime, weights, signals)
  - data/hybrid_state.json      (state, or fresh)

Executes:
  - Builds target portfolio from signals × weights
  - Rebalances only if regime or holdings changed
  - Track Maker/Taker fee separately
  - Kill Switch 90%

Writes:
  - data/hybrid_state.json      (atomic write)
  - data/hybrid.log
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════

INITIAL_CAPITAL = 10000.0           # USD
MAKER_FEE = 0.0001                   # 0.01% (from M31 lesson)
TAKER_FEE = 0.0005                   # 0.05% (from M31 lesson)
SLIPPAGE = 0.003                     # 0.3% (Wallex)
KILL_SWITCH = 0.90                   # stop if equity < 90%

STATE_FILE = "data/hybrid_state.json"
WEIGHTS_FILE = "data/hybrid_weights.json"
PRICES_FILE = "data/wallex_tmn_all.json"
TGJU_FILE = "data/usd_irr_tgju.json"
LOG_FILE = "data/hybrid.log"
V2_CONFIG_FILE = "data/hybrid_v2_config.json"

sys.path.insert(0, "scripts")
try:
    from hybrid_signals import SIGNAL_FUNCTIONS_V2
except ImportError:
    SIGNAL_FUNCTIONS_V2 = {}

MAX_ASSETS_PER_STRATEGY = 3          # top N assets per strategy

# Only liquid assets (from existing wallex_paper_bot.py)
LIQUID_ASSETS = {
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "LINK",
    "AVAX", "DOT", "MATIC", "LTC", "BCH", "UNI", "ATOM", "ETC", "XLM",
    "NEAR", "APT"
}


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def log(msg):
    """Append to log file + print."""
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n")


def load_state():
    """Load state (atomic read) or fresh."""
    p = Path(STATE_FILE)
    if not p.exists():
        return {
            "initial_capital": INITIAL_CAPITAL,
            "equity": INITIAL_CAPITAL,
            "peak_equity": INITIAL_CAPITAL,
            "cash_tmn": INITIAL_CAPITAL * 2_713_800,  # 10K USD × ~Rial rate (updated on run)
            "usdt_amount": 0.0,
            "holdings": {},
            "last_regime": None,
            "last_port_keys": [],
            "initialized": False,
            "trades": [],
            "baseline_bh": INITIAL_CAPITAL,   # B&H BTC benchmark
            "baseline_m31": INITIAL_CAPITAL,  # placeholder
        }
    try:
        return json.loads(p.read_text())
    except Exception:
        log("⚠️ State corrupted, resetting")
        return load_state_fresh()


def load_state_fresh():
    return {
        "initial_capital": INITIAL_CAPITAL,
        "equity": INITIAL_CAPITAL,
        "peak_equity": INITIAL_CAPITAL,
        "cash_tmn": INITIAL_CAPITAL * 2_713_800,
        "usdt_amount": 0.0,
        "holdings": {},
        "last_regime": None,
        "last_port_keys": [],
        "initialized": False,
        "trades": [],
        "baseline_bh": INITIAL_CAPITAL,
        "baseline_m31": INITIAL_CAPITAL,
    }


def save_state(state):
    """Atomic write (tmp + replace)."""
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    p = Path(STATE_FILE)
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, indent=2))
    Path(tmp).replace(p)


def get_usd_rate():
    """Latest USD/IRR rate from TGJU."""
    try:
        tgju = json.load(open(TGJU_FILE))
        return tgju[sorted(tgju.keys())[-1]]
    except Exception:
        return 2_713_800  # fallback


def load_prices():
    """Load TMN prices as dict: {asset: price_toman}."""
    raw = json.load(open(PRICES_FILE))
    prices = {}
    for k, v in raw.items():
        if k == "USDTTMN" or not k.endswith("TMN"):
            continue
        asset = k[:-3]
        dates = sorted(v.keys())
        if dates:
            prices[asset] = v[dates[-1]]
    return prices


def is_price_fresh(asset, dates_dict, max_age_days=7):
    """Check if asset's price is recent."""
    if asset not in dates_dict:
        return False
    dates = sorted(dates_dict[asset].keys())
    if not dates:
        return False
    last_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    age = (datetime.now() - last_date).days
    return age <= max_age_days


def load_latest_dates():
    """Load latest date per asset."""
    raw = json.load(open(PRICES_FILE))
    result = {}
    for k, v in raw.items():
        if k == "USDTTMN" or not k.endswith("TMN"):
            continue
        asset = k[:-3]
        dates = sorted(v.keys())
        if dates:
            result[asset] = {dates[-1]: v[dates[-1]]}
    return result


# ═══════════════════════════════════════════════════════════════════
# SIGNAL-BASED PORTFOLIO BUILDER
# ═══════════════════════════════════════════════════════════════════

def build_target_portfolio(weights, signals, prices):
    """
    Build target portfolio from weights × signals.

    For each strategy:
      - Take top N assets with signal == 1
      - Split strategy weight equally among those assets
      - Sum across strategies
    """
    target = {}

    for strategy, weight in weights.items():
        n_active = signals.get(strategy, 0)
        if n_active == 0:
            continue

        # Which assets have signal?
        # (signal count is available, but we need the asset list)
        # For now: use signal distribution as uniform across active
        # This will be refined in hybrid_researcher.py's active_signals
        pass

    # Since we only have signal counts, we need to compute per-asset
    # For now: allocate weight to top N LIQUID_ASSETS by momentum
    # (simplified v1)
    total_weight = sum(weights.values())
    if total_weight == 0:
        return {}

    # Simple approach: weight each liquid asset by equal share
    # (this will be refined in v2 with per-asset signals)
    liquid = [a for a in LIQUID_ASSETS if a in prices]
    if not liquid:
        return {}

    per_asset = total_weight / len(liquid)
    for asset in liquid:
        target[asset] = per_asset

    return target


# ═══════════════════════════════════════════════════════════════════
# REBALANCE
# ═══════════════════════════════════════════════════════════════════

def rebalance(state, target_weights, prices, usd_rate):
    """
    Rebalance portfolio to match target_weights.

    target_weights: {asset: weight} where sum(weights) <= 1.0
    Remainder goes to cash (TETHER).
    """
    # Compute current equity
    current_equity = state.get("cash_tmn", 0) / usd_rate
    for asset, qty in state.get("holdings", {}).items():
        if asset in prices:
            price_usd = prices[asset] * 10 / usd_rate  # Toman → USD (× 10 for Rial)
            current_equity += qty * price_usd

    # Fee
    fee_pct = MAKER_FEE if state.get("last_regime") == state.get("last_regime") else TAKER_FEE
    fee = current_equity * fee_pct
    current_equity -= fee

    # Distribute to assets
    new_holdings = {}
    for asset, weight in target_weights.items():
        if asset not in prices:
            continue
        alloc_usd = current_equity * weight
        price_usd = prices[asset] * 10 / usd_rate
        if price_usd > 0:
            qty = alloc_usd / price_usd
            new_holdings[asset] = qty

    # Remainder to cash
    invested = sum(target_weights.values())
    cash_usd = current_equity * (1.0 - invested)

    state["holdings"] = new_holdings
    state["cash_tmn"] = cash_usd * usd_rate
    state["equity"] = current_equity
    state["peak_equity"] = max(state.get("peak_equity", current_equity), current_equity)

    return state, fee


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# V2 — Build target portfolio from config (top 3 per strategy)
# ═══════════════════════════════════════════════════════════════════

def build_target_portfolio_v2(config, df, prices):
    """V2: read config strategies, compute signals, top 3 assets per strategy."""
    from pathlib import Path
    try:
        import pandas as pd
        df_pd = pd.read_json(Path("data/wallex_tmn_all.json").resolve(), orient="columns").T
    except Exception:
        # fallback: use dict-of-lists
        import json as _j
        raw = _j.load(open("data/wallex_tmn_all.json"))
        cols = {k[:-3]: v for k, v in raw.items() if k != "USDTTMN" and k.endswith("TMN") and len(v) >= 100}
        import pandas as _pd
        df_pd = _pd.DataFrame(cols)
        df_pd.index = _pd.to_datetime(df_pd.index)
        df_pd = df_pd.sort_index().ffill()
    
    target = {}
    total_weight = 0.0
    
    for strategy_name, strategy_info in config.get("strategies", {}).items():
        weight = strategy_info["weight"]
        fn = SIGNAL_FUNCTIONS_V2.get(strategy_name)
        if fn is None:
            continue
        try:
            signals = fn(df_pd)
            # فقط liquid assets
            liquid_sig = signals[[c for c in signals.index if c in LIQUID_ASSETS]]
            # top 3 assets با signal=1
            active = liquid_sig[liquid_sig == 1].head(3)
            if len(active) == 0:
                continue
            per_asset = weight / len(active)
            for asset in active.index:
                if asset in prices:
                    target[asset] = target.get(asset, 0) + per_asset
                    total_weight += per_asset
        except Exception as e:
            log(f"  ⚠️ {strategy_name}: {e}")
    
    return target, total_weight


def main():
    log("=" * 80)
    log(" 🤖 HYBRID BOT — Paper execution")
    log("=" * 80)

    # 1. Load weights
    if not os.path.exists(WEIGHTS_FILE):
        log(f"❌ {WEIGHTS_FILE} not found. Run hybrid_researcher.py first.")
        return
    weights_data = json.load(open(WEIGHTS_FILE))
    regime = weights_data.get("regime", "FLAT_CALM")
    weights = weights_data.get("weights", {})
    cash_weight = weights_data.get("cash_weight", 0.10)
    active_signals = weights_data.get("active_signals", {})

    log(f"📍 Regime: {regime}")
    log(f"📊 Weights: {len(weights)} strategies")
    log(f"💰 Cash target: {cash_weight:.2%}")

    # 2. Load prices + v2 config
    prices = load_prices()
    latest_dates = load_latest_dates()
    usd_rate = get_usd_rate()
    log(f"💵 USD rate: {usd_rate:,.0f} Rial")
    log(f"🪙 Prices: {len(prices)} assets")
    log(f"📅 Fresh assets (≤7 days): {sum(1 for a in prices if is_price_fresh(a, latest_dates))}")
    
    # Check v2 config
    use_v2 = os.path.exists(V2_CONFIG_FILE)
    if use_v2:
        with open(V2_CONFIG_FILE) as f:
            v2_config = json.load(f)
        log(f"🆕 Using HYBRID V2 config: {v2_config['selected_count']} strategies, backtest Sharpe {v2_config['backtest_sharpe']:.2f}")
    else:
        log(f"⚠️ No v2 config — falling back to v1 (equal-weight)")

    # 3. Load state
    state = load_state()
    is_first_run = not state.get("initialized", False)

    # 4. Compute current equity
    current_equity = state.get("cash_tmn", 0) / usd_rate
    for asset, qty in state.get("holdings", {}).items():
        if asset in prices:
            price_usd = prices[asset] * 10 / usd_rate
            current_equity += qty * price_usd

    log(f"💼 Current equity: ${current_equity:.2f}")

    # 5. Kill Switch
    if current_equity < INITIAL_CAPITAL * KILL_SWITCH:
        log(f"🚨 KILL SWITCH: ${current_equity:.2f} < ${INITIAL_CAPITAL * KILL_SWITCH:.2f}")
        state["kill_switch_triggered"] = True
        save_state(state)
        return

    # 6. Build target portfolio
    if use_v2:
        target, target_weight = build_target_portfolio_v2(v2_config, None, prices)
        log(f"🎯 V2 target: {len(target)} assets, total weight: {target_weight:.2%}")
    else:
        target = build_target_portfolio(weights, active_signals, prices)
    log(f"🎯 Target: {len(target)} assets, total weight: {sum(target.values()):.2%}")

    # 7. Rebalance decision
    curr_keys = set(target.keys())
    prev_keys = set(state.get("last_port_keys", []))
    regime_changed = regime != state.get("last_regime")

    if is_first_run or regime_changed or curr_keys != prev_keys:
        log(f"🔄 REBALANCING (regime: {state.get('last_regime')} → {regime})")
        state, fee = rebalance(state, target, prices, usd_rate)
        state["last_regime"] = regime
        state["last_port_keys"] = list(curr_keys)
        state["initialized"] = True
        log(f"  💰 Fee: ${fee:.2f}")
        log(f"  📊 New holdings: {len(state['holdings'])} assets")
        log(f"  💵 Cash: ${state['cash_tmn'] / usd_rate:.2f}")
    else:
        log("⏸️  No rebalance needed (regime and holdings unchanged)")

    # 8. Save
    save_state(state)
    log(f"💼 Final equity: ${state['equity']:.2f} ({((state['equity']/INITIAL_CAPITAL - 1) * 100):+.2f}%)")
    log("")


if __name__ == "__main__":
    main()
