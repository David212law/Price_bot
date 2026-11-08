"""Regime bot v2 — fix fee bleed via: merge similar regimes, hysteresis, cooldown."""
import json
from datetime import datetime

FEE = 0.006


def load():
    crypto = json.load(open("data/crypto_5y_usd.json"))
    usd_irr = json.load(open("data/usd_irr_tgju.json"))
    tmn = {}
    for sym, prices in crypto.items():
        if not sym.endswith("-USD"): continue
        base = sym[:-4]
        tmn[base] = {d: p * usd_irr[d]/10 for d, p in prices.items() if d in usd_irr}
    tether = {d: usd_irr[d]/10 for d in usd_irr}
    return tmn, tether


def daily_rets(prices):
    r = {}
    dates = sorted(prices.keys())
    for i in range(1, len(dates)):
        d0, d1 = dates[i-1], dates[i]
        try:
            if (datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d0, "%Y-%m-%d")).days != 1: continue
        except: continue
        if prices[d0] > 0:
            r[d1] = (prices[d1]/prices[d0] - 1) * 100
    return r


def rolling_mean(p, date, w):
    past = [p[d] for d in sorted(p.keys()) if d <= date][-w:]
    return sum(past)/len(past) if past else None


def rolling_std(p, date, w):
    past = [p[d] for d in sorted(p.keys()) if d <= date][-w:]
    if len(past) < w: return None
    m = sum(past)/len(past)
    return (sum((x-m)**2 for x in past)/len(past))**0.5


def detect_regime(btc, date):
    past = [d for d in sorted(btc.keys()) if d < date]
    if len(past) < 60: return None
    p_now = btc[past[-1]]
    p_30 = btc[past[-30]]
    ret_30 = (p_now/p_30 - 1)*100
    rets = []
    for i in range(-30, -1):
        if i-1 >= -len(past):
            d1, d0 = past[i], past[i-1]
            try:
                if (datetime.strptime(d1,"%Y-%m-%d") - datetime.strptime(d0,"%Y-%m-%d")).days != 1: continue
            except: continue
            if btc[d0] > 0: rets.append((btc[d1]/btc[d0]-1)*100)
    if len(rets) < 15: return None
    vol = (sum((r-sum(rets)/len(rets))**2 for r in rets)/len(rets))**0.5
    if ret_30 > 15 and vol < 6: return "BULL_STRONG"
    if ret_30 > 5: return "BULL"
    if ret_30 > -5: return "FLAT"
    if ret_30 > -15: return "BEAR"
    return "CRASH"


def regime_to_strategy(regime):
    """FIX 1: merge similar regimes — no fee between BULL_STRONG↔BULL, BEAR↔CRASH."""
    if regime in ("BULL_STRONG", "BULL"): return "MOMENTUM"
    if regime == "FLAT": return "MEANREV"
    if regime in ("BEAR", "CRASH"): return "DEFENSIVE"
    return "TETHER"


def momentum_cands(tmn, date):
    out = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < 60: continue
        pn, p30 = p[past[-1]], p[past[-30]]
        ma50 = rolling_mean(p, date, 50)
        if ma50 is None: continue
        r30 = (pn/p30 - 1)*100
        if r30 > 0 and pn > ma50:
            out.append((a, r30))
    out.sort(key=lambda x: -x[1])
    return [a for a,_ in out]


def meanrev_cands(tmn, date):
    out = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < 40: continue
        pn = p[past[-1]]
        ma = rolling_mean(p, date, 20)
        sd = rolling_std(p, date, 20)
        if not ma or not sd or sd == 0: continue
        z = (pn - ma) / sd
        if z < -2: out.append((a, z))
    out.sort(key=lambda x: x[1])
    return [a for a,_ in out]


def compute_holdings(strategy, tmn, date):
    """FIX 1: single set per strategy (no BULL/BULL_STRONG distinction)."""
    if strategy == "TETHER":
        return {"TETHER": 1.0}
    if strategy == "MOMENTUM":
        c = momentum_cands(tmn, date)[:3]
        if c: return {a: 1.0/len(c) for a in c}
        return {"TETHER": 1.0}
    if strategy == "MEANREV":
        c = meanrev_cands(tmn, date)[:3]
        if c: return {a: 1.0/len(c) for a in c}
        return {"TETHER": 1.0}
    if strategy == "DEFENSIVE":
        # FIX 2: merge BEAR and CRASH → 100% tether (no BCH switch between them)
        return {"TETHER": 1.0}
    return {"TETHER": 1.0}


def holdings_equal(h1, h2):
    """Compare if holdings are materially the same."""
    if set(h1.keys()) != set(h2.keys()): return False
    return all(abs(h1[k] - h2[k]) < 0.01 for k in h1)


def simulate_v2(start, end, tmn, tether, all_rets, hysteresis, cooldown):
    dates = [d for d in sorted(all_rets["TETHER"].keys()) if start <= d <= end]
    if len(dates) < 10: return None

    holdings = {"TETHER": 1.0}
    current_strategy = "TETHER"
    pending_strategy = None
    pending_count = 0
    days_since_switch = 999
    daily = []
    switch_count = 0

    for date in dates:
        regime = detect_regime(tmn["BTC"], date)
        if regime is None:
            daily.append(0.0); days_since_switch += 1
            continue

        strategy = regime_to_strategy(regime)

        # FIX 3: hysteresis — regime must be stable for N days
        if strategy != current_strategy:
            if pending_strategy == strategy:
                pending_count += 1
            else:
                pending_strategy = strategy
                pending_count = 1
        else:
            pending_strategy = None
            pending_count = 0

        # Today return
        dr = 0.0
        for a, w in holdings.items():
            if a == "TETHER": continue
            if date in all_rets.get(a, {}):
                dr += w * all_rets[a][date]

        # FIX 4: cooldown — no switch if switched recently
        if (pending_count >= hysteresis and
            days_since_switch >= cooldown and
            strategy != current_strategy):
            new_holdings = compute_holdings(strategy, tmn, date)
            if not holdings_equal(holdings, new_holdings):
                holdings = new_holdings
                current_strategy = strategy
                dr -= FEE * 100
                days_since_switch = 0
                switch_count += 1
                pending_strategy = None
                pending_count = 0

        daily.append(dr)
        days_since_switch += 1

    eq = 1.0
    peak = 1.0
    max_dd = 0
    for r in daily:
        eq *= (1 + r/100)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak-eq)/peak*100)
    total = (eq-1)*100
    mean = sum(daily)/len(daily)
    std = (sum((r-mean)**2 for r in daily)/len(daily))**0.5
    sharpe = (mean/std)*(365**0.5) if std > 0 else 0

    return {
        "days": len(daily),
        "total_return": total,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "switches": switch_count,
        "fee_paid": switch_count * FEE * 100,
    }


def main():
    print("=" * 84)
    print(" Regime bot v2 — fee-optimized with hysteresis & cooldown")
    print("=" * 84)

    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)

    windows = [
        ("2023-02-01", "2023-05-01"),
        ("2023-08-01", "2023-11-01"),
        ("2024-02-01", "2024-05-01"),
        ("2024-08-01", "2024-11-01"),
        ("2025-02-01", "2025-05-01"),
        ("2025-08-01", "2026-02-01"),
    ]

    configs = [
        ("v1_baseline (h=0, c=0)",      0,  0),
        ("v2a (h=0, c=7)",              0,  7),
        ("v2b (h=3, c=7)",              3,  7),
        ("v2c (h=3, c=14)",             3, 14),
        ("v2d (h=5, c=14)",             5, 14),
        ("v2e (h=5, c=21)",             5, 21),
    ]

    print(f"\n  {'Config':<26} " + " ".join(f"{s[5:10]:>8}" for s, _ in windows) + f" {'AVG':>8} {'WINS':>6} {'SW':>4}")
    print("  " + "-" * 82)

    for name, h, c in configs:
        returns = []
        total_switches = 0
        for s, e in windows:
            r = simulate_v2(s, e, tmn, tether, all_rets, h, c)
            if r:
                returns.append(r["total_return"])
                total_switches += r["switches"]
            else:
                returns.append(0)
        avg = sum(returns)/len(returns)
        wins = sum(1 for r in returns if r > 0)
        line = f"  {name:<26} "
        for r in returns:
            line += f"{r:>+7.1f}% "
        line += f"{avg:>+7.1f}% {wins:>4}/6 {total_switches:>5}"
        print(line)

    print(f"\n{'='*84}")
    print(" INTERPRETATION")
    print("=" * 84)
    print("  - اگر v2b (h=3,c=7) بهتر از v1 بود → hysteresis+cooldown کار می‌کند")
    print("  - اگر avg > +10% و wins >= 5/6 → استراتژی آماده Paper است")
    print("  - اگر هنوز 3/6 یا کمتر → مشکل ساختاری‌تر است")


if __name__ == "__main__":
    main()
