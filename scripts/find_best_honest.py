"""Honest per-regime strategy discovery — decision at T, return at T+1."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import load, daily_rets, rolling_mean, rolling_std, detect_regime

def mom_nd(tmn, date, n=30, top_n=3):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < n + 20: continue
        pn, pa = p[past[-1]], p[past[-n]]
        ma50 = rolling_mean(p, date, 50)
        if ma50 is None: continue
        r = (pn/pa - 1) * 100
        if r > 0 and pn > ma50:
            cands.append((a, r))
    cands.sort(key=lambda x: -x[1])
    top = cands[:top_n]
    return [a for a, _ in top] if top else []

def breakout_n(tmn, date, n=20, top_n=3):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < n + 5: continue
        pn = p[past[-1]]
        prev_max = max(p[d] for d in past[-n-1:-1])
        if pn > prev_max: cands.append(a)
    return cands[:top_n]

def ma_cross(tmn, date, fast=20, slow=50, top_n=3):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < slow + 5: continue
        mf = rolling_mean(p, date, fast)
        ms = rolling_mean(p, date, slow)
        if mf is None or ms is None: continue
        if mf > ms: cands.append(a)
    return cands[:top_n]

def rsi_mr(tmn, date, period=14):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < period + 5: continue
        gains = losses = 0
        for i in range(-period, 0):
            diff = p[past[i]] - p[past[i-1]]
            if diff > 0: gains += diff
            else: losses -= diff
        if losses == 0: continue
        rsi = 100 - 100/(1 + gains/losses)
        if rsi < 30: cands.append((a, rsi))
    cands.sort(key=lambda x: x[1])
    return [a for a, _ in cands[:3]]

def bb_mr(tmn, date, period=20, n_std=2):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < period + 5: continue
        ma = rolling_mean(p, date, period)
        sd = rolling_std(p, date, period)
        if not ma or not sd: continue
        pn = p[past[-1]]
        if pn < ma - n_std * sd:
            cands.append((a, (pn - ma) / sd))
    cands.sort(key=lambda x: x[1])
    return [a for a, _ in cands[:3]]

STRATEGIES = {
    "mom10":    lambda t,d: mom_nd(t,d,10),
    "mom20":    lambda t,d: mom_nd(t,d,20),
    "mom30":    lambda t,d: mom_nd(t,d,30),
    "mom60":    lambda t,d: mom_nd(t,d,60),
    "break20":  lambda t,d: breakout_n(t,d,20),
    "break50":  lambda t,d: breakout_n(t,d,50),
    "ma20_50":  lambda t,d: ma_cross(t,d,20,50),
    "ma50_200": lambda t,d: ma_cross(t,d,50,200),
    "rsi_mr":   rsi_mr,
    "bb_mr":    bb_mr,
    "bh_btc":   lambda t,d: ["BTC"],
    "bh_bnb":   lambda t,d: ["BNB"],
    "bh_eth":   lambda t,d: ["ETH"],
    "tether":   lambda t,d: [],
}

def main():
    print("="*94)
    print(" HONEST per-regime discovery — decision at T, return at T+1")
    print("="*94)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    dates = sorted(all_rets["TETHER"].keys())
    split = dates[int(len(dates)*0.7)]
    train = [d for d in dates if d < split]
    test = [d for d in dates if d >= split]

    print(f"\nData: {len(dates)} days ({dates[0]} -> {dates[-1]})")
    print(f"TRAIN: {train[0]} -> {train[-1]} ({len(train)} days)")
    print(f"TEST:  {test[0]} -> {test[-1]} ({len(test)} days)")

    # Precompute decisions for all strategies, all dates (decision uses data up to date)
    print("\nPrecomputing decisions (14 strategies x all dates)...")
    decisions = {name: {} for name in STRATEGIES}
    for name, fn in STRATEGIES.items():
        for i in range(1, len(dates)):
            d = dates[i]
            decisions[name][d] = fn(tmn, d)

    # Build daily returns: return at date d uses decision from date d-1
    print("Building honest daily returns...")
    strat_daily = {name: {} for name in STRATEGIES}
    for name in STRATEGIES:
        for i in range(1, len(dates)):
            d, d_prev = dates[i], dates[i-1]
            holds = decisions[name].get(d_prev, [])
            if not holds:
                strat_daily[name][d] = 0.0  # in tether
            else:
                w = 1.0 / len(holds)
                strat_daily[name][d] = sum(w * all_rets[a].get(d, 0) for a in holds)

    # Regime for each date
    regimes = {d: detect_regime(tmn["BTC"], d) for d in dates}
    regimes = {d: r for d, r in regimes.items() if r}

    # ── STEP 1: rank strategies per regime on TRAIN ──
    print("\n" + "="*94)
    print(" STEP 1: Rank 14 strategies per regime (TRAIN only, honest returns)")
    print("="*94)

    best_per_regime = {}
    for regime in ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]:
        rd = [d for d in train if regimes.get(d) == regime]
        if len(rd) < 20:
            print(f"\n  {regime}: only {len(rd)} train days — skipping (too few)")
            best_per_regime[regime] = "tether"
            continue
        scores = {}
        for name in STRATEGIES:
            scores[name] = sum(strat_daily[name].get(d,0) for d in rd) / len(rd)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        best_per_regime[regime] = ranked[0][0]
        print(f"\n  {regime}  ({len(rd)} train days)")
        for i, (name, sc) in enumerate(ranked[:5], 1):
            mark = " ⬅ BEST" if i == 1 else ""
            print(f"    {i}. {name:<12} {sc:>+8.4f}%/day{mark}")

    # ── STEP 2: Apply on TEST ──
    print("\n" + "="*94)
    print(" STEP 2: Apply best_per_regime on TEST (honest, no look-ahead)")
    print("="*94)

    combined = []
    for d in test:
        r = regimes.get(d)
        if r is None:
            combined.append(0); continue
        name = best_per_regime.get(r, "tether")
        combined.append(strat_daily[name].get(d, 0))

    def stats(daily):
        if not daily: return (0,0,0)
        eq=peak=1.0; dd=0
        for r in daily:
            eq *= (1+r/100); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
        m=sum(daily)/len(daily)
        s=(sum((x-m)**2 for x in daily)/len(daily))**0.5
        return ((eq-1)*100, dd, (m/s)*(365**0.5) if s>0 else 0)

    print(f"\n  {'Strategy':<22} {'Total':>10} {'DD':>7} {'Sharpe':>8}")
    print("  " + "-"*52)
    ct, cd, cs = stats(combined)
    print(f"  {'REGIME_COMBINED':<22} {ct:>+8.1f}% {cd:>5.1f}% {cs:>7.2f}")
    for name in STRATEGIES:
        d = [strat_daily[name].get(x,0) for x in test]
        t, dd, sh = stats(d)
        print(f"  {name:<22} {t:>+8.1f}% {dd:>5.1f}% {sh:>7.2f}")
    bh = [all_rets["BTC"].get(x,0) for x in test]
    bht, bhdd, bhsh = stats(bh)
    print(f"\n  {'B&H BTC-TMN':<22} {bht:>+8.1f}% {bhdd:>5.1f}% {bhsh:>7.2f}")

    print("\n" + "="*94)
    print(" FINAL VERDICT")
    print("="*94)
    print(f"\n  REGIME_COMBINED: {ct:+.1f}%  |  B&H: {bht:+.1f}%  |  diff: {ct-bht:+.1f}%")
    if ct > bht:
        print(f"  ✅ regime-aware از B&H بهتر است — ایده کار می‌کند!")
    else:
        print(f"  ❌ regime-aware از B&H بدتر است — با این داده/استراتژی‌ها، alpha ندارد")

    print(f"\n  Best per regime (selected from TRAIN):")
    for r in ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]:
        print(f"    {r:<14}: {best_per_regime.get(r,'?')}")

if __name__ == "__main__":
    main()
