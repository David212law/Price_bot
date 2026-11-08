"""Comprehensive robot test — Part A: strategies, Part B: detection, Part C: system."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import load, daily_rets, rolling_mean, rolling_std, detect_regime

FEE = 0.006

def mom30(tmn, date, top_n=3):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < 50: continue
        pn, pa = p[past[-1]], p[past[-30]]
        ma50 = rolling_mean(p, date, 50)
        if ma50 is None: continue
        r = (pn/pa - 1) * 100
        if r > 0 and pn > ma50:
            cands.append((a, r))
    cands.sort(key=lambda x: -x[1])
    return [a for a, _ in cands[:top_n]] if cands else []

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
    return [a for a, _ in cands[:3]] if cands else []

def ma50_200(tmn, date):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < 205: continue
        mf = rolling_mean(p, date, 50)
        ms = rolling_mean(p, date, 200)
        if mf is None or ms is None: continue
        if mf > ms: cands.append(a)
    return cands[:3] if cands else []

def bh_btc(tmn, date): return ["BTC"]
def tether_only(tmn, date): return []

STRATEGIES = {
    "mom30": mom30, "bb_mr": bb_mr, "ma50_200": ma50_200,
    "bh_btc": bh_btc, "tether": tether_only,
}

def holdings_ret(holds, all_rets, date):
    if not holds: return 0.0
    w = 1.0 / len(holds)
    return sum(w * all_rets[a].get(date, 0) for a in holds)

def stats(daily):
    if not daily: return {"total":0, "dd":0, "sharpe":0, "n":0}
    eq=peak=1.0; dd=0
    for r in daily:
        eq *= (1+r/100); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    m=sum(daily)/len(daily)
    s=(sum((x-m)**2 for x in daily)/len(daily))**0.5 if len(daily)>1 else 0
    return {"total":(eq-1)*100, "dd":dd, "sharpe":(m/s)*(365**0.5) if s>0 else 0, "n":len(daily)}

def main():
    print("="*100)
    print(" COMPREHENSIVE ROBOT TEST — Strategy + Detection + System")
    print("="*100)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    dates = sorted(all_rets["TETHER"].keys())
    date_to_idx = {d: i for i, d in enumerate(dates)}
    split_idx = int(len(dates)*0.7)
    split = dates[split_idx]
    train = [d for d in dates if d < split]
    test = [d for d in dates if d >= split]

    print(f"\nData: {len(dates)} days ({dates[0]} -> {dates[-1]})")
    print(f"TRAIN: {len(train)} days  |  TEST: {len(test)} days")

    print("\nPrecomputing honest strategy returns...")
    strat_rets = {name: {} for name in STRATEGIES}
    for i in range(1, len(dates)):
        d, d_prev = dates[i], dates[i-1]
        for name, fn in STRATEGIES.items():
            strat_rets[name][d] = holdings_ret(fn(tmn, d_prev), all_rets, d)

    regimes = {d: detect_regime(tmn["BTC"], d) for d in dates}
    regimes = {d: r for d, r in regimes.items() if r}

    # PART A
    print("\n" + "="*100)
    print(" PART A — Strategy quality per regime (TRAIN, honest)")
    print("="*100)
    best_per_regime = {}
    for regime in ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]:
        td = [d for d in train if regimes.get(d) == regime]
        if len(td) < 20:
            print(f"\n  {regime}: {len(td)} train days — too few, using tether")
            best_per_regime[regime] = "tether"
            continue
        scores = {n: sum(strat_rets[n].get(d,0) for d in td)/len(td) for n in STRATEGIES}
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        best_per_regime[regime] = ranked[0][0]
        print(f"\n  {regime} ({len(td)} days):")
        for i, (n, sc) in enumerate(ranked, 1):
            print(f"    {i}. {n:<10} {sc:>+8.4f}%/day{' ⬅' if i==1 else ''}")

    print("\n  best_per_regime:")
    for r in ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]:
        print(f"    {r:<14} → {best_per_regime[r]}")

    # PART B
    print("\n" + "="*100)
    print(" PART B — Regime detection quality (vs what actually happened next 30d)")
    print("="*100)
    def fwd_regime(date):
        idx = date_to_idx.get(date)
        if idx is None or idx + 30 >= len(dates): return None
        p_now = tmn["BTC"].get(date)
        p_fut = tmn["BTC"].get(dates[idx+30])
        if not p_now or not p_fut or p_now <= 0: return None
        r = (p_fut/p_now - 1) * 100
        if r > 15: return "BULL_STRONG"
        if r > 5: return "BULL"
        if r > -5: return "FLAT"
        if r > -15: return "BEAR"
        return "CRASH"

    matches, total, conf = 0, 0, {}
    for d in test:
        rp, rf = regimes.get(d), fwd_regime(d)
        if rp is None or rf is None: continue
        total += 1
        if rp == rf: matches += 1
        conf[(rp, rf)] = conf.get((rp, rf), 0) + 1

    acc = matches/total*100 if total > 0 else 0
    print(f"\n  Days evaluated: {total}")
    print(f"  Accuracy (detector == forward): {matches}/{total} ({acc:.1f}%)")
    labels = ["BULL_STRONG","BULL","FLAT","BEAR","CRASH"]
    print(f"\n  {'detector↓ / future→':<14} " + " ".join(f"{l:>11}" for l in labels))
    for l1 in labels:
        row = f"  {l1:<14} "
        for l2 in labels:
            row += f"{conf.get((l1,l2),0):>11} "
        print(row)

    # PART C
    print("\n" + "="*100)
    print(" PART C — System performance (TEST)")
    print("="*100)

    # Robot: hysteresis + cooldown + fee
    robot, cur_r, pending, pend_c, days_since = [], None, None, 0, 999
    for d in test:
        r = regimes.get(d)
        if r is None:
            robot.append(0); days_since += 1; continue
        # Switch check FIRST
        fee_today = 0
        if (pending == r and pend_c + 1 >= 7 and days_since >= 14 and r != cur_r):
            cur_r = r; days_since = 0; fee_today = FEE*100
            pending = None; pend_c = 0
        elif r != cur_r:
            if pending == r: pend_c += 1
            else: pending = r; pend_c = 1
        else:
            pending = None; pend_c = 0
        s = best_per_regime.get(cur_r, "tether") if cur_r else "tether"
        robot.append(strat_rets[s].get(d, 0) - fee_today)
        days_since += 1

    # NoHyst
    nohyst, cur_n = [], None
    for d in test:
        r = regimes.get(d)
        if r is None: nohyst.append(0); continue
        fee = FEE*100 if r != cur_n else 0
        cur_n = r
        nohyst.append(strat_rets[best_per_regime.get(r,"tether")].get(d,0) - fee)

    # Oracle_Look: perfect foresight
    oracle, cur_o = [], None
    for d in test:
        rf = fwd_regime(d)
        if rf is None: oracle.append(0); continue
        fee = FEE*100 if rf != cur_o else 0
        cur_o = rf
        oracle.append(strat_rets[best_per_regime.get(rf,"tether")].get(d,0) - fee)

    bh = [all_rets["BTC"].get(d, 0) for d in test]

    print(f"\n  {'Config':<28} {'Total':>12} {'DD':>8} {'Sharpe':>8}")
    print("  " + "-"*60)
    R = {}
    for name, daily in [("Robot (hyst+fee)", robot), ("Robot_NoHyst", nohyst),
                          ("Oracle_Look", oracle), ("B&H BTC", bh)]:
        s = stats(daily); R[name] = s
        print(f"  {name:<28} {s['total']:>+10.1f}% {s['dd']:>6.1f}% {s['sharpe']:>7.2f}")

    singles = {n: stats([strat_rets[n].get(d,0) for d in test]) for n in STRATEGIES}
    best_single_name = max(singles.items(), key=lambda x: x[1]["sharpe"])[0]
    bs = singles[best_single_name]
    print(f"\n  Best single ({best_single_name}): {bs['total']:+.1f}% DD={bs['dd']:.1f}% Sharpe={bs['sharpe']:.2f}")

    print("\n" + "="*100)
    print(" FINAL VERDICT")
    print("="*100)
    r = R["Robot (hyst+fee)"]; n = R["Robot_NoHyst"]; o = R["Oracle_Look"]; b = R["B&H BTC"]
    print(f"\n  1. Detection accuracy: {acc:.1f}%  ({'✅' if acc>60 else '🟡' if acc>40 else '❌'})")
    print(f"  2. Cost of hysteresis:   Robot {r['total']:+.1f}% vs NoHyst {n['total']:+.1f}%")
    print(f"  3. Cost of detection:    Robot {r['total']:+.1f}% vs Oracle {o['total']:+.1f}%")
    print(f"  4. Robot vs B&H:         Robot {r['total']:+.1f}% (Sh {r['sharpe']:.2f}) vs B&H {b['total']:+.1f}% (Sh {b['sharpe']:.2f})")
    print(f"\n  OVERALL:")
    if r['total'] > b['total'] and r['sharpe'] > b['sharpe']:
        print(f"  ✅✅✅ Robot beats B&H on all metrics — ready for Paper")
    elif r['sharpe'] > b['sharpe']:
        print(f"  🟡 Robot better Sharpe, lower return — defensive")
    elif r['total'] > b['total']:
        print(f"  🟡 Robot higher return, more risk — aggressive")
    else:
        print(f"  ❌ Robot worse than B&H — needs redesign")

if __name__ == "__main__":
    main()
