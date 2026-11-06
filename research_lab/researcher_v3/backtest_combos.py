"""D-570: Real backtest of combo proposals using returns_matrices."""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

RET = Path("research_lab/logs/profiles/returns_matrices")
ROLE_COMBOS = Path("research_lab/logs/researcher_v3/role_combos.json")

REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE_LOW", "RANGE_MED",
           "RANGE_HIGH", "CRISIS_VOL", "CRISIS_NEGATIVE"]

def sharpe(vals):
    if len(vals) < 10: return 0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return (m/sd)*(365**0.5) if sd > 0 else 0

def max_dd(vals):
    eq = 1.0
    peak = 1.0
    dd = 0
    for r in vals:
        eq *= (1+r)
        if eq > peak: peak = eq
        cur = (peak-eq)/peak*100 if peak > 0 else 0
        if cur > dd: dd = cur
    return dd

def total_return(vals):
    eq = 1.0
    for r in vals: eq *= (1+r)
    return (eq-1)*100

def load_strategy_returns(strategy_name):
    """Load returns for a strategy. Tries to find file in any exchange."""
    if strategy_name == "CASH":
        return {}
    
    # Special handling for M31 names
    if strategy_name.startswith("M31_"):
        exch = strategy_name.split("_")[1]  # M31_hyperliquid → hyperliquid
        for f in (RET/exch).glob("M31_EMA_*_BTC*.json"):
            try: return json.loads(f.read_text())
            except: pass
        return {}
    
    # Try to match strategy + symbol in any exchange
    # e.g., "KELTNER_REV_ETHUSDT" → aster
    parts = strategy_name.rsplit("_", 1)
    if len(parts) != 2: return {}
    strat, sym = parts
    
    for exch in ["hyperliquid", "aster", "kucoin"]:
        d = RET/exch
        if not d.exists(): continue
        for f in d.glob(f"{strat}_*_{sym}.json"):
            try: return json.loads(f.read_text())
            except: pass
    
    return {}

def load_regime_map():
    """Build regime map from crisis cache prices."""
    cache = Path("data/crisis_test_cache.json")
    if not cache.exists(): return {}
    data = json.loads(cache.read_text())
    prices = data.get("BTC-USD", {})
    if not prices: return {}
    
    dates = sorted(prices.keys())
    if len(dates) < 65: return {}
    
    rets = []
    for i in range(1, len(dates)):
        p0, p1 = prices[dates[i-1]], prices[dates[i]]
        if p0 > 0: rets.append((p1-p0)/p0)
    
    regime_map = {}
    for i in range(64, len(dates)):
        d = dates[i]
        recent = rets[max(0, i-20):i]
        if len(recent) < 20: continue
        m = sum(recent)/len(recent)
        var = sum((r-m)**2 for r in recent)/len(recent)
        vol = var**0.5
        trend = sum(recent[-7:]) if len(recent) >= 7 else 0
        ma = sum([prices[dates[j]] for j in range(i-50, i)])/50
        price = prices[dates[i-1]]
        below = price < ma
        
        if vol > 0.045: regime_map[d] = "CRISIS_VOL"
        elif trend > 0.08 and not below: regime_map[d] = "TREND_UP"
        elif trend < -0.08 and below: regime_map[d] = "TREND_DOWN"
        elif vol < 0.02: regime_map[d] = "RANGE_LOW"
        elif vol < 0.04: regime_map[d] = "RANGE_MED"
        else: regime_map[d] = "RANGE_HIGH"
    
    return regime_map

def main():
    print("\n[1] Loading role_combos.json...")
    combos_data = json.loads(ROLE_COMBOS.read_text())
    combos = combos_data.get("combos", {})
    print(f"  {len(combos)} combos")
    
    print("\n[2] Building regime map...")
    regime_map = load_regime_map()
    print(f"  {len(regime_map)} days with regime")
    for r in REGIMES:
        n = sum(1 for v in regime_map.values() if v == r)
        if n: print(f"    {r}: {n} days")
    
    print("\n[3] Testing each combo on real data...")
    print()
    print(f"{'Regime':<15} {'Type':<14} {'Days':>5} {'SR':>7} {'DD':>7} {'Total':>8}")
    print("-" * 65)
    
    results = {}
    for regime in REGIMES:
        if regime not in combos: continue
        combo = combos[regime]
        components = combo["components"]
        
        # Get regime days
        regime_days = sorted([d for d, r in regime_map.items() if r == regime])
        if len(regime_days) < 30: continue
        
        # Load all component returns
        strat_rets = {}
        for c in components:
            name = c["strategy"]
            if name == "CASH": continue
            rets = load_strategy_returns(name)
            if rets:
                strat_rets[name] = (rets, c["weight"])
        
        if not strat_rets:
            print(f"{regime:<15} {'(no data)':<14}")
            continue
        
        # Common days = regime days where all strategies have data
        all_strat_dates = None
        for name, (rets, w) in strat_rets.items():
            if all_strat_dates is None:
                all_strat_dates = set(rets.keys())
            else:
                all_strat_dates &= set(rets.keys())
        
        common = sorted(set(regime_days) & all_strat_dates)
        if len(common) < 30:
            print(f"{regime:<15} {'(n<30)':<14} {len(common):>5}")
            continue
        
        # Compute combo daily returns
        combo_daily = []
        for d in common:
            ret = 0
            for name, (rets, w) in strat_rets.items():
                ret += w * rets.get(d, 0)
            combo_daily.append(ret)
        
        # Also M31 alone for comparison
        m31_name = next((n for n in strat_rets if n.startswith("M31")), None)
        if m31_name:
            m31_rets = strat_rets[m31_name][0]
            m31_daily = [m31_rets.get(d, 0) for d in common]
        else:
            m31_daily = []
        
        # Metrics
        combo_sr = sharpe(combo_daily)
        combo_dd = max_dd(combo_daily)
        combo_total = total_return(combo_daily)
        
        m31_sr = sharpe(m31_daily) if m31_daily else 0
        m31_dd = max_dd(m31_daily) if m31_daily else 0
        m31_total = total_return(m31_daily) if m31_daily else 0
        
        # Winner
        combo_wins = combo_sr > m31_sr and combo_dd <= m31_dd * 1.2
        
        results[regime] = {
            "n_days": len(common),
            "combo": {"sr": combo_sr, "dd": combo_dd, "total": combo_total},
            "m31_alone": {"sr": m31_sr, "dd": m31_dd, "total": m31_total} if m31_daily else None,
            "winner": "combo" if combo_wins else "m31",
        }
        
        print(f"{regime:<15} {'combo':<14} {len(common):>5} {combo_sr:>7.2f} {combo_dd:>6.2f}% {combo_total:>+7.1f}%")
        if m31_daily:
            print(f"{regime:<15} {'M31 alone':<14} {len(common):>5} {m31_sr:>7.2f} {m31_dd:>6.2f}% {m31_total:>+7.1f}%")
            marker = "✅ combo" if combo_wins else "⚠️ M31"
            print(f"{regime:<15} {'WINNER':<14}       {marker}")
        print()
    
    # Summary
    print("=" * 65)
    print(" 🎯 SUMMARY")
    print("=" * 65)
    combo_wins = sum(1 for r in results.values() if r["winner"] == "combo")
    m31_wins = sum(1 for r in results.values() if r["winner"] == "m31")
    print(f"  Combo wins: {combo_wins}")
    print(f"  M31 wins:   {m31_wins}")
    print(f"  Tie/No data: {len(REGIMES) - combo_wins - m31_wins}")
    print()
    print("  ⚠️ Notes:")
    print("  - This uses returns_matrices (funding-only for M31)")
    print("  - M31 SR is INFLATED (real hedged M31 ~11, not 16)")
    print("  - Forward Paper test is the real answer")
    
    # Save
    out = Path("research_lab/logs/researcher_v3/backtest_results.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "real returns from returns_matrices",
        "caveat": "M31 in returns_matrices is funding-only (SR inflated)",
        "results": results,
    }, indent=2))
    print(f"\n  💾 saved: {out}")

if __name__ == "__main__":
    main()
