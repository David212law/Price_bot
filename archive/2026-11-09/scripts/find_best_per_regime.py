"""Find best strategy per regime — the test we should have done from start."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import load, daily_rets, rolling_mean, rolling_std, detect_regime
from regime_bot_v4 import simulate_v4

# ─── Strategy definitions ───

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
    return {a: 1.0/len(top) for a, _ in top} if top else {"TETHER": 1.0}

def breakout_n(tmn, date, n=20, top_n=3):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < n + 5: continue
        pn = p[past[-1]]
        prev_max = max(p[d] for d in past[-n-1:-1])
        if pn > prev_max: cands.append(a)
    return {a: 1.0/len(cands) for a in cands[:top_n]} if cands else {"TETHER": 1.0}

def ma_cross(tmn, date, fast=20, slow=50, top_n=3):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < slow + 5: continue
        mf = rolling_mean(p, date, fast)
        ms = rolling_mean(p, date, slow)
        if mf is None or ms is None: continue
        if mf > ms: cands.append(a)
    return {a: 1.0/len(cands) for a in cands[:top_n]} if cands else {"TETHER": 1.0}

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
    top = cands[:3]
    return {a: 1.0/len(top) for a, _ in top} if top else {"TETHER": 1.0}

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
    top = cands[:3]
    return {a: 1.0/len(top) for a, _ in top} if top else {"TETHER": 1.0}

def bh_btc(tmn, date): return {"BTC": 1.0}
def bh_bnb(tmn, date): return {"BNB": 1.0}
def bh_eth(tmn, date): return {"ETH": 1.0}
def tether_only(tmn, date): return {"TETHER": 1.0}

STRATEGIES = {
    "mom10":   lambda t,d: mom_nd(t,d,10),
    "mom20":   lambda t,d: mom_nd(t,d,20),
    "mom30":   lambda t,d: mom_nd(t,d,30),
    "mom60":   lambda t,d: mom_nd(t,d,60),
    "break20": lambda t,d: breakout_n(t,d,20),
    "break50": lambda t,d: breakout_n(t,d,50),
    "ma20_50": lambda t,d: ma_cross(t,d,20,50),
    "ma50_200":lambda t,d: ma_cross(t,d,50,200),
    "rsi_mr":  rsi_mr,
    "bb_mr":   bb_mr,
    "bh_btc":  bh_btc,
    "bh_bnb":  bh_bnb,
    "bh_eth":  bh_eth,
    "tether":  tether_only,
}

def simulate(fn, tmn, all_rets, dates):
    return [sum(w * all_rets.get(a, {}).get(d, 0) for a, w in fn(tmn, d).items()) for d in dates]

def stats(daily):
    if not daily: return {"total":0,"dd":0,"sharpe":0,"mean":0}
    eq=peak=1.0; dd=0
    for r in daily:
        eq *= (1+r/100); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    m=sum(daily)/len(daily)
    s=(sum((x-m)**2 for x in daily)/len(daily))**0.5
    return {"total":(eq-1)*100,"dd":dd,"sharpe":(m/s)*(365**0.5) if s>0 else 0,"mean":m}

def main():
    print("="*94)
    print(" FIND BEST STRATEGY PER REGIME — the test we should have done from start")
    print("="*94)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    all_dates = sorted(all_rets["TETHER"].keys())
    split = all_dates[int(len(all_dates)*0.7)]

    print(f"\nData: {len(all_dates)} days ({all_dates[0]} -> {all_dates[-1]})")
    print(f"TRAIN: {all_dates[0]} -> {split}  |  TEST: {split} -> {all_dates[-1]}")

    regimes = {d: detect_regime(tmn["BTC"], d) for d in all_dates}
    regimes = {d: r for d, r in regimes.items() if r}

    print("\n" + "="*94)
    print(" STEP 1: For each regime, rank 14 strategies on TRAIN")
    print("="*94)

    strategy_daily = {name: dict(zip(all_dates, simulate(fn, tmn, all_rets, all_dates))) for name, fn in STRATEGIES.items()}

    best_per_regime = {}
    for regime in ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]:
        train_dates = [d for d in all_dates if d < split and regimes.get(d)==regime]
        if len(train_dates) < 15:
            best_per_regime[regime] = ("tether", 0.0)
            print(f"\n  {regime}: only {len(train_dates)} train days — using tether")
            continue
        scores = {name: sum(strategy_daily[name].get(d,0) for d in train_dates)/len(train_dates) for name in STRATEGIES}
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        best_per_regime[regime] = ranked[0]
        print(f"\n  {regime}  ({len(train_dates)} train days)")
        for i, (name, score) in enumerate(ranked[:4], 1):
            mark = " ⬅ BEST" if i == 1 else ""
            print(f"    {i}. {name:<12} {score:>+8.4f}%/day{mark}")

    print("\n" + "="*94)
    print(" STEP 2: Apply best_per_regime on TEST (never seen)")
    print("="*94)
    test_dates = [d for d in all_dates if d >= split]

    combined = []
    for d in test_dates:
        r = regimes.get(d)
        if r is None: combined.append(0); continue
        name = best_per_regime.get(r, ("tether",0))[0]
        combined.append(strategy_daily[name].get(d, 0))
    s_comb = stats(combined)

    print(f"\n  {'Strategy':<22} {'Total':>10} {'DD':>8} {'Sharpe':>8} {'Mean/day':>10}")
    print("  " + "-"*64)
    print(f"  {'REGIME_COMBINED':<22} {s_comb['total']:>+8.1f}% {s_comb['dd']:>6.1f}% {s_comb['sharpe']:>7.2f} {s_comb['mean']:>+8.4f}%")
    for name in STRATEGIES:
        daily = [strategy_daily[name].get(d,0) for d in test_dates]
        s = stats(daily)
        print(f"  {name:<22} {s['total']:>+8.1f}% {s['dd']:>6.1f}% {s['sharpe']:>7.2f} {s['mean']:>+8.4f}%")

    bh_btc_daily = [all_rets["BTC"].get(d,0) for d in test_dates]
    s_bh = stats(bh_btc_daily)
    r_v4a = simulate_v4(test_dates[0], test_dates[-1], tmn, tether, all_rets, 7, 14, trail_pct=-10)

    print("\n" + "-"*64)
    print(f"  {'B&H BTC-TMN':<22} {s_bh['total']:>+8.1f}% {s_bh['dd']:>6.1f}% {s_bh['sharpe']:>7.2f} {s_bh['mean']:>+8.4f}%")
    if r_v4a:
        print(f"  {'v4a (baseline)':<22} {r_v4a['return']:>+8.1f}% {r_v4a['dd']:>6.1f}% {r_v4a['sharpe']:>7.2f}")

    print("\n" + "="*94)
    print(" INTERPRETATION")
    print("="*94)
    print(f"\n  BEST_PER_REGIME  vs  B&H BTC:  {s_comb['total']:+.1f}%  vs  {s_bh['total']:+.1f}%   diff: {s_comb['total']-s_bh['total']:+.1f}%")
    if r_v4a:
        print(f"  BEST_PER_REGIME  vs  v4a:      {s_comb['total']:+.1f}%  vs  {r_v4a['return']:+.1f}%   diff: {s_comb['total']-r_v4a['return']:+.1f}%")

    print("\n  چه چیزی یاد گرفتیم:")
    for regime in ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]:
        name = best_per_regime.get(regime, ("?",0))[0]
        was_v4a = "momentum" if regime in ["BULL_STRONG","BULL"] else "meanreversion" if regime=="FLAT" else "tether"
        match = "SAME" if was_v4a in name or (regime in ["BEAR","CRASH"] and name=="tether") else "DIFFERENT"
        print(f"    {regime:<14}: our v4a used {was_v4a:<14} | test says best is {name:<10} [{match}]")

    print("\n  نتیجه نهایی:")
    if s_comb['total'] > s_bh['total'] and (r_v4a is None or s_comb['total'] > r_v4a['return']):
        print("  ✅ regime-aware با انتخاب درست استراتژی، از B&H و v4a بهتر است")
    elif s_comb['total'] > s_bh['total']:
        print("  🟡 regime-aware بهتر از B&H است ولی v4a بهتر است (چرا؟)")
    else:
        print("  ❌ regime-aware از B&H بدتر است — regime detection یا انتخاب استراتژی مشکل دارد")

if __name__ == "__main__":
    main()
