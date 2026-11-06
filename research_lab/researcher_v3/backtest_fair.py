"""D-571: Fair backtest with D-552 simulated M31 hedged returns."""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

RET = Path("research_lab/logs/profiles/returns_matrices")
ROLE_COMBOS = Path("research_lab/logs/researcher_v3/role_combos.json")
CRISIS_CACHE = Path("data/crisis_test_cache.json")
FUNDING_DIR = Path("exchanges/hyperliquid/data")

REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE_LOW", "RANGE_MED",
           "RANGE_HIGH", "CRISIS_VOL", "CRISIS_NEGATIVE"]


def sharpe(vals):
    if len(vals) < 10: return 0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return (m/sd)*(365**0.5) if sd > 0 else 0

def max_dd(vals):
    eq = 1.0; peak = 1.0; dd = 0
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


def load_funding_hl():
    """Load HL BTC funding (sum per day)."""
    by_day = defaultdict(float)
    for p in [FUNDING_DIR / "BTC_funding.json",
              Path("data/hyperliquid/BTC_funding.json")]:
        if not p.exists(): continue
        try:
            raw = json.loads(p.read_text())
            if isinstance(raw, list):
                for it in raw:
                    if not isinstance(it, dict): continue
                    t = it.get("t"); r = it.get("rate")
                    if t and r is not None:
                        ts = t/1000 if isinstance(t,(int,float)) and t>1e10 else t
                        if isinstance(ts, (int,float)):
                            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                        else:
                            d = str(t)[:10]
                        by_day[d] += float(r)
            return dict(by_day)
        except: pass
    return {}


def simulate_m31_hedged(prices, funding):
    """D-552 simulator: 45% spot + 45% perp (short) + 10% cash."""
    common = sorted(set(prices.keys()) & set(funding.keys()))
    if len(common) < 60: return {}
    
    spot_units = 0.45 / prices[common[0]]
    perp_units = 0.45 / prices[common[0]]
    cash = 0.10
    equity = 1.0
    last_rebal = 0
    returns = {}
    
    for i in range(1, len(common)):
        d = common[i]
        p_today = prices[d]
        p_yest = prices[common[i-1]]
        
        funding_inc = perp_units * funding[d] * p_yest
        spot_pnl = spot_units * (p_today - p_yest)
        perp_pnl = -perp_units * (p_today - p_yest)
        
        daily_ret = (funding_inc + spot_pnl + perp_pnl) / equity if equity > 0 else 0
        
        # Fee on rebalance (every 30 days)
        if i - last_rebal >= 30:
            daily_ret -= 0.0007
            last_rebal = i
        
        returns[d] = daily_ret
        equity *= (1 + daily_ret)
    
    return returns


def load_btc_prices():
    if not CRISIS_CACHE.exists(): return {}
    try:
        data = json.loads(CRISIS_CACHE.read_text())
        return data.get("BTC-USD", {})
    except: return {}


def load_regime_map(prices):
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


def load_strategy_returns(name):
    if name == "CASH": return {}
    if name.startswith("M31_"):
        exch = name.split("_")[1]
        for f in (RET/exch).glob("M31_EMA_*_BTC*.json"):
            try: return json.loads(f.read_text())
            except: pass
        return {}
    parts = name.rsplit("_", 1)
    if len(parts) != 2: return {}
    strat, sym = parts
    for exch in ["hyperliquid", "aster", "kucoin"]:
        d = RET/exch
        if not d.exists(): continue
        for f in d.glob(f"{strat}_*_{sym}.json"):
            try: return json.loads(f.read_text())
            except: pass
    return {}


def main():
    print("\n[1] Loading prices + funding...")
    prices = load_btc_prices()
    funding = load_funding_hl()
    print(f"  prices: {len(prices)} days")
    print(f"  funding: {len(funding)} days")
    
    print("\n[2] Simulating M31 hedged (D-552)...")
    m31_hedged = simulate_m31_hedged(prices, funding)
    print(f"  {len(m31_hedged)} days with real M31 hedged returns")
    if m31_hedged:
        vals = list(m31_hedged.values())
        print(f"  M31 hedged SR (real): {sharpe(vals):.2f}")
        print(f"  M31 hedged total: {total_return(vals):+.1f}%")
        print(f"  M31 hedged DD: {max_dd(vals):.1f}%")
    
    print("\n[3] Building regime map...")
    regime_map = load_regime_map(prices)
    for r in REGIMES:
        n = sum(1 for v in regime_map.values() if v == r)
        if n: print(f"  {r}: {n} days")
    
    print("\n[4] Loading role_combos...")
    combos = json.loads(ROLE_COMBOS.read_text()).get("combos", {})
    
    print("\n[5] Testing combos vs M31 HEDGED (fair)...")
    print()
    print(f"{'Regime':<15} {'Type':<14} {'Days':>5} {'SR':>7} {'DD':>7} {'Total':>8}")
    print("-" * 65)
    
    results = {}
    for regime in REGIMES:
        if regime not in combos: continue
        combo = combos[regime]
        components = combo["components"]
        
        regime_days = sorted([d for d, r in regime_map.items() if r == regime])
        if len(regime_days) < 15: continue  # lowered from 30
        
        strat_rets = {}
        for c in components:
            name = c["strategy"]
            if name == "CASH": continue
            rets = load_strategy_returns(name)
            if rets:
                strat_rets[name] = (rets, c["weight"])
        
        if not strat_rets: continue
        
        all_strat_dates = None
        for name, (rets, w) in strat_rets.items():
            if all_strat_dates is None:
                all_strat_dates = set(rets.keys())
            else:
                all_strat_dates &= set(rets.keys())
        
        # Common days must also have M31 hedged data
        common = sorted(set(regime_days) & all_strat_dates & set(m31_hedged.keys()))
        if len(common) < 15: continue
        
        combo_daily = []
        for d in common:
            ret = 0
            for name, (rets, w) in strat_rets.items():
                ret += w * rets.get(d, 0)
            combo_daily.append(ret)
        
        m31_daily = [m31_hedged.get(d, 0) for d in common]
        
        combo_sr = sharpe(combo_daily)
        combo_dd = max_dd(combo_daily)
        combo_total = total_return(combo_daily)
        
        m31_sr = sharpe(m31_daily)
        m31_dd = max_dd(m31_daily)
        m31_total = total_return(m31_daily)
        
        combo_wins = combo_sr > m31_sr
        
        results[regime] = {
            "n_days": len(common),
            "combo": {"sr": combo_sr, "dd": combo_dd, "total": combo_total},
            "m31_hedged": {"sr": m31_sr, "dd": m31_dd, "total": m31_total},
            "winner": "combo" if combo_wins else "m31",
        }
        
        print(f"{regime:<15} {'combo':<14} {len(common):>5} {combo_sr:>7.2f} {combo_dd:>6.2f}% {combo_total:>+7.1f}%")
        print(f"{regime:<15} {'M31 hedged':<14} {len(common):>5} {m31_sr:>7.2f} {m31_dd:>6.2f}% {m31_total:>+7.1f}%")
        marker = "✅ combo WINS" if combo_wins else "⚠️ M31 wins"
        print(f"{regime:<15} {'WINNER':<14}       {marker}")
        print()
    
    print("=" * 65)
    print(" 🎯 SUMMARY")
    print("=" * 65)
    combo_wins = sum(1 for r in results.values() if r["winner"] == "combo")
    m31_wins = sum(1 for r in results.values() if r["winner"] == "m31")
    print(f"  Combo wins: {combo_wins}")
    print(f"  M31 wins:   {m31_wins}")
    print(f"  Tested:     {len(results)} regimes")
    print()
    print("  ⚠️ Caveat: M31 hedged is simulated (D-552)")
    print("     Real forward Paper is the true test")
    
    out = Path("research_lab/logs/researcher_v3/backtest_fair.json")
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "M31 hedged (D-552) vs combo",
        "results": results,
    }, indent=2))
    print(f"\n  💾 saved: {out}")


if __name__ == "__main__":
    main()
