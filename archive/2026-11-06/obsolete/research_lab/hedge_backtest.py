"""D-552: Hedge M31 Backtest — compares M31-alone vs delta-neutral hedge."""
import json
from pathlib import Path
from datetime import datetime, timezone


def load_funding(exchange, symbol):
    for p in [Path(f"data/{exchange}/{symbol}_funding.json"),
              Path(f"exchanges/{exchange}/data/{symbol}_funding.json")]:
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text())
            out = {}
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, (int, float)):
                        out[str(k)[:10]] = float(v)
            elif isinstance(raw, list):
                for it in raw:
                    if not isinstance(it, dict):
                        continue
                    t = it.get("t") or it.get("timestamp")
                    r = it.get("rate") or it.get("fundingRate")
                    if t and r is not None:
                        if isinstance(t, (int, float)):
                            ts = t/1000 if t > 1e10 else t
                            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                        else:
                            d = str(t)[:10]
                        out[d] = float(r)
            return out
        except Exception:
            continue
    return {}


def load_prices(exchange, symbol):
    for p in [Path(f"data/{exchange}/{symbol}_1d.json"),
              Path(f"exchanges/{exchange}/data/{symbol}_4h.json")]:
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text())
            out = {}
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
                out[d] = float(cl)
            return out
        except Exception:
            continue
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


def simulate_hedge(funding, prices, fee_rt=0.003, rebalance_days=30):
    """Long spot + short perp. Returns (daily_returns_list, stats_dict)."""
    common = sorted(set(funding.keys()) & set(prices.keys()))
    if len(common) < 60:
        return [], {}
    
    spot_w = 0.45
    perp_w = 0.45
    cash_w = 0.10
    
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
        
        funding_inc = perp_units * funding[d] * p_yest
        spot_pnl = spot_units * (p_today - p_yest)
        perp_pnl = -perp_units * (p_today - p_yest)
        
        daily_ret = (funding_inc + spot_pnl + perp_pnl) / equity if equity > 0 else 0
        
        # Rebalance fee
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
    """100% short perp only. Returns (daily_returns_list, stats_dict)."""
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
    print(" D-552: Hedge M31 Backtest")
    print("=" * 72)
    
    exchanges = [
        ("aster", "BTCUSDT", "BTC"),
        ("hyperliquid", "BTC", "BTC"),
        ("kucoin", "XBTUSDTM", "XBTUSDTM"),
    ]
    
    for exchange, sym_funding, sym_price in exchanges:
        funding = load_funding(exchange, sym_funding)
        prices = load_prices(exchange, sym_price)
        
        if not funding or not prices:
            print(f"\n{exchange}: NO DATA")
            continue
        
        print(f"\n{exchange.upper()} {sym_funding}:")
        print(f"  funding days: {len(funding)}, price days: {len(prices)}")
        
        hedge_rets, hedge_stats = simulate_hedge(funding, prices)
        m31_rets, m31_stats = simulate_m31_alone(funding, prices)
        
        if not hedge_stats or not m31_stats:
            print(f"  insufficient overlap: {len(set(funding) & set(prices))} common days")
            continue
        
        print(f"\n  {'Metric':<20} {'M31 alone':>12} {'Hedged':>12}")
        print(f"  {'-' * 46}")
        print(f"  {'Days':<20} {m31_stats['n']:>12} {hedge_stats['n']:>12}")
        print(f"  {'Total return':<20} {m31_stats['ret']:>+11.2f}% {hedge_stats['ret']:>+11.2f}%")
        print(f"  {'Sharpe':<20} {m31_stats['sr']:>12.2f} {hedge_stats['sr']:>12.2f}")
        print(f"  {'Max DD':<20} {m31_stats['dd']:>11.2f}% {hedge_stats['dd']:>11.2f}%")
        
        if 'funding_contrib' in hedge_stats:
            print(f"\n  Hedged breakdown:")
            print(f"    Funding contribution: {hedge_stats['funding_contrib']:+.2f}%")
            print(f"    Fee events: {hedge_stats['fee_events']} (total {hedge_stats['fee_total']:.2f}%)")
            price_contrib = hedge_stats['ret'] - hedge_stats['funding_contrib'] + hedge_stats['fee_total']
            print(f"    Price contribution (should be ~0): {price_contrib:+.2f}%")
        
        print(f"\n  Verdict:")
        dd_reduction = m31_stats['dd'] - hedge_stats['dd']
        if hedge_stats['dd'] < m31_stats['dd'] * 0.5:
            print(f"    ✅ Hedge reduced DD by {dd_reduction:.2f}pp")
        elif hedge_stats['dd'] < m31_stats['dd']:
            print(f"    🟡 Hedge slightly reduced DD ({dd_reduction:.2f}pp)")
        else:
            print(f"    ❌ Hedge did not reduce DD")
        
        if hedge_stats['sr'] > m31_stats['sr'] * 0.8:
            print(f"    ✅ Hedge kept Sharpe > 80% of unhedged")
        else:
            print(f"    ⚠️  Hedge reduced Sharpe by {(1 - hedge_stats['sr']/m31_stats['sr'])*100:.0f}%")


if __name__ == "__main__":
    main()
