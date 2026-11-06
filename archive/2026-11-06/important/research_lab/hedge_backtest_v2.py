"""D-552 v2: Hedge backtest with correct funding (sum per day) and real HL fees."""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# Real Hyperliquid fees
HL_PERP_TAKER = 0.00035  # 0.035%
HL_SPOT_TAKER = 0.00035  # 0.035%
# Per rebalance: sell spot (0.035%) + adjust perp (0.035%) = ~0.07%


def load_funding_daily(exchange, symbol):
    """Sum all funding records per day (correct method)."""
    for p in [Path(f"data/{exchange}/{symbol}_funding.json"),
              Path(f"exchanges/{exchange}/data/{symbol}_funding.json")]:
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text())
            by_day = defaultdict(float)
            if isinstance(raw, list):
                for it in raw:
                    if not isinstance(it, dict):
                        continue
                    t = it.get("t") or it.get("timestamp")
                    r = it.get("rate") or it.get("fundingRate")
                    if t is None or r is None:
                        continue
                    if isinstance(t, (int, float)):
                        ts = t/1000 if t > 1e10 else t
                        d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    else:
                        d = str(t)[:10]
                    by_day[d] += float(r)
            elif isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, (int, float)):
                        by_day[str(k)[:10]] += float(v)
            return dict(by_day)
        except Exception as e:
            print(f"  [err funding] {e}")
    return {}


def load_prices_daily(exchange, symbol):
    """Load daily close prices from 4h or 1d."""
    for p in [Path(f"data/{exchange}/{symbol}_1d.json"),
              Path(f"exchanges/{exchange}/data/{symbol}_4h.json"),
              Path(f"data/{exchange}/{symbol}_4h.json")]:
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text())
            by_day = {}
            for c in raw:
                if not isinstance(c, dict):
                    continue
                t = c.get("t") or c.get("timestamp")
                cl = c.get("c") or c.get("close")
                if t is None or cl is None:
                    continue
                try:
                    ts = int(t)/1000 if int(t) > 1e10 else int(t)
                except Exception:
                    continue
                d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                by_day[d] = float(cl)
            return by_day
        except Exception as e:
            print(f"  [err price] {e}")
    return {}


def stats(vals):
    if not vals:
        return {"sr": 0, "dd": 0, "ret": 0, "n": 0}
    n = len(vals)
    m = sum(vals) / n
    v = sum((x - m) ** 2 for x in vals) / n
    sd = v ** 0.5
    sr = (m / sd) * (365 ** 0.5) if sd > 0 else 0
    eq = [1.0]
    for r in vals:
        eq.append(eq[-1] * (1 + r))
    ret = (eq[-1] - 1) * 100
    peak = eq[0]
    dd = 0
    for e in eq:
        if e > peak:
            peak = e
        cur = (peak - e) / peak * 100 if peak > 0 else 0
        if cur > dd:
            dd = cur
    return {"sr": sr, "dd": dd, "ret": ret, "n": n}


def simulate_hedge(funding, prices, fee_rt=0.0007, rebalance_days=30):
    """Long 45% spot + short 45% perp."""
    common = sorted(set(funding.keys()) & set(prices.keys()))
    if len(common) < 60:
        return [], {}
    
    spot_w = 0.45
    perp_w = 0.45
    returns = []
    equity = 1.0
    spot_units = spot_w / prices[common[0]]
    perp_units = perp_w / prices[common[0]]
    last_rebalance = 0
    fee_events = 0
    funding_total = 0.0
    
    for i in range(1, len(common)):
        d = common[i]
        p_today = prices[d]
        p_yest = prices[common[i-1]]
        
        # funding (sum of 3 per day)
        funding_inc = perp_units * funding[d] * p_yest
        spot_pnl = spot_units * (p_today - p_yest)
        perp_pnl = -perp_units * (p_today - p_yest)
        
        daily_ret = (funding_inc + spot_pnl + perp_pnl) / equity if equity > 0 else 0
        
        if i - last_rebalance >= rebalance_days:
            daily_ret -= fee_rt
            fee_events += 1
            last_rebalance = i
        
        returns.append(daily_ret)
        funding_total += funding_inc / equity if equity > 0 else 0
        equity *= (1 + daily_ret)
    
    s = stats(returns)
    s["funding_contrib"] = funding_total * 100
    s["fee_events"] = fee_events
    s["fee_total"] = fee_events * fee_rt * 100
    return returns, s


def simulate_m31_alone(funding, prices):
    common = sorted(set(funding.keys()) & set(prices.keys()))
    if len(common) < 60:
        return [], {}
    
    returns = []
    equity = 1.0
    perp_units = 1.0 / prices[common[0]]
    
    for i in range(1, len(common)):
        d = common[i]
        p_today = prices[d]
        p_yest = prices[common[i-1]]
        
        funding_inc = perp_units * funding[d] * p_yest
        perp_pnl = -perp_units * (p_today - p_yest)
        
        daily_ret = (funding_inc + perp_pnl) / equity if equity > 0 else 0
        returns.append(daily_ret)
        equity *= (1 + daily_ret)
    
    return returns, stats(returns)


def main():
    print("=" * 72)
    print(" D-552 v2: Correct funding (sum per day) + real HL fees")
    print("=" * 72)
    print(" Note: funding records are every 8h → sum per day is correct")
    print(" Real HL fees: perp taker 0.035% + spot taker 0.035% = 0.07%/rebalance")
    print("=" * 72)
    
    exchanges = [
        ("hyperliquid", "BTC", "BTC"),
        ("kucoin", "XBTUSDTM", "XBTUSDTM"),
        ("aster", "BTCUSDT", "BTCUSDT"),
    ]
    
    for exchange, sym_f, sym_p in exchanges:
        funding = load_funding_daily(exchange, sym_f)
        prices = load_prices_daily(exchange, sym_p)
        
        if not funding or not prices:
            print(f"\n{exchange}: NO DATA (funding={len(funding)}, prices={len(prices)})")
            continue
        
        common = sorted(set(funding) & set(prices))
        print(f"\n{exchange.upper()} {sym_f}:")
        print(f"  funding days: {len(funding)}, price days: {len(prices)}, common: {len(common)}")
        
        if len(common) < 100:
            print(f"  too few common days")
            continue
        
        # Verify funding magnitude
        funding_vals = [funding[d] for d in common]
        avg_funding = sum(funding_vals) / len(funding_vals)
        print(f"  avg daily funding: {avg_funding*100:.4f}%")
        print(f"  annualized funding: {avg_funding * 365 * 100:.2f}%")
        
        hedge_rets, hedge_stats = simulate_hedge(funding, prices)
        m31_rets, m31_stats = simulate_m31_alone(funding, prices)
        
        if not hedge_stats or not m31_stats:
            continue
        
        print(f"\n  {'Metric':<20} {'M31 alone':>14} {'Hedged':>14}")
        print(f"  {'-' * 50}")
        print(f"  {'Days':<20} {m31_stats['n']:>14} {hedge_stats['n']:>14}")
        print(f"  {'Total return':<20} {m31_stats['ret']:>+13.2f}% {hedge_stats['ret']:>+13.2f}%")
        print(f"  {'Sharpe':<20} {m31_stats['sr']:>14.2f} {hedge_stats['sr']:>14.2f}")
        print(f"  {'Max DD':<20} {m31_stats['dd']:>13.2f}% {hedge_stats['dd']:>13.2f}%")
        
        print(f"\n  Hedged breakdown:")
        print(f"    Funding:  {hedge_stats['funding_contrib']:+.2f}%")
        print(f"    Fees:     -{hedge_stats['fee_total']:.2f}% ({hedge_stats['fee_events']} events)")
        price_contrib = hedge_stats['ret'] - hedge_stats['funding_contrib'] + hedge_stats['fee_total']
        print(f"    Price:    {price_contrib:+.2f}% (should be ~0 for delta neutral)")
        
        print(f"\n  Verdict:")
        if hedge_stats['dd'] < m31_stats['dd'] * 0.5:
            print(f"    ✅ DD reduced by {m31_stats['dd'] - hedge_stats['dd']:.2f}pp")
        if abs(price_contrib) < 1.0:
            print(f"    ✅ Delta-neutral works (price contrib ~0)")
        if hedge_stats['sr'] > m31_stats['sr']:
            print(f"    ✅ Hedged Sharpe > M31 Sharpe")
        elif hedge_stats['sr'] > m31_stats['sr'] * 0.8:
            print(f"    🟡 Hedged Sharpe > 80% of M31")
        else:
            print(f"    ⚠️  Hedged Sharpe lower than M31")


if __name__ == "__main__":
    main()
