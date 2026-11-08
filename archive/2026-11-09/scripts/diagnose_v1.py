"""Diagnose regime_bot_v1: every switch logged, fee impact, whipsaw detection."""
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

def rolling_mean(prices, date, w):
    past = [prices[d] for d in sorted(prices.keys()) if d <= date][-w:]
    return sum(past)/len(past) if past else None

def rolling_std(prices, date, w):
    past = [prices[d] for d in sorted(prices.keys()) if d <= date][-w:]
    if len(past) < w: return None
    m = sum(past)/len(past)
    return (sum((p-m)**2 for p in past)/len(past))**0.5

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

def simulate_with_log(start, end, tmn, tether, all_rets):
    dates = sorted(set(all_rets["TETHER"].keys()))
    dates = [d for d in dates if start <= d <= end]
    if len(dates) < 10: return None

    holdings = {"TETHER": 1.0}
    last_regime = None
    log = []
    daily = []

    for date in dates:
        regime = detect_regime(tmn["BTC"], date)
        if regime is None:
            daily.append(0.0)
            continue

        # Today return
        dr = 0.0
        for a, w in holdings.items():
            if a == "TETHER": continue
            if date in all_rets.get(a, {}):
                dr += w * all_rets[a][date]

        if regime != last_regime:
            new_holdings = {"TETHER": 1.0}
            if regime == "BULL_STRONG":
                c = momentum_cands(tmn, date)[:2]
                if c: new_holdings = {a: 1.0/len(c) for a in c}
            elif regime == "BULL":
                c = momentum_cands(tmn, date)[:3]
                if c: new_holdings = {a: 1.0/len(c) for a in c}
            elif regime == "FLAT":
                c = meanrev_cands(tmn, date)[:3]
                if c: new_holdings = {a: 1.0/len(c) for a in c}
            elif regime == "BEAR":
                new_holdings = {"TETHER": 0.5, "BCH": 0.5}

            changed = set(new_holdings.keys()) != set(holdings.keys())
            log.append({
                "date": date,
                "from_regime": last_regime,
                "to_regime": regime,
                "from_assets": list(holdings.keys()),
                "to_assets": list(new_holdings.keys()),
                "changed": changed,
                "fee_cost_pct": FEE*100 if changed else 0,
            })
            if changed:
                dr -= FEE*100  # Apply fee

            holdings = new_holdings
            last_regime = regime

        daily.append(dr)

    return {"daily": daily, "log": log, "dates": dates}

def main():
    print("=" * 84)
    print(" DIAGNOSE v1 — why 3/6 windows failed?")
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

    total_switches = 0
    total_fee = 0.0
    regime_counts = {}
    for s, e in windows:
        r = simulate_with_log(s, e, tmn, tether, all_rets)
        if not r: continue
        switches = [l for l in r["log"] if l["changed"]]
        fee_paid = sum(l["fee_cost_pct"] for l in switches)
        # Net return
        eq = 1.0
        for d in r["daily"]: eq *= (1+d/100)
        total_ret = (eq-1)*100

        print(f"\nWindow {s} → {e}")
        print(f"  Return: {total_ret:+.1f}%  |  Switches: {len(switches)}  |  Fee: {fee_paid:.2f}%")
        for l in switches[:10]:  # show first 10
            print(f"    {l['date']}  {l['from_regime']}→{l['to_regime']:<12} "
                  f"{','.join(l['from_assets'][:2]):<20} → {','.join(l['to_assets'][:2])}")
        total_switches += len(switches)
        total_fee += fee_paid
        for l in r["log"]:
            regime_counts[l["to_regime"]] = regime_counts.get(l["to_regime"], 0) + 1

    print(f"\n{'='*84}")
    print(" SUMMARY")
    print("=" * 84)
    print(f"  Total switches:  {total_switches}")
    print(f"  Total fee paid:  {total_fee:.1f}%")
    print(f"  Avg fee/switch:  {total_fee/total_switches:.2f}%")
    print(f"\n  Regime transitions observed:")
    for regime, count in sorted(regime_counts.items(), key=lambda x: -x[1]):
        print(f"    {regime:<14} {count:>3} times")

    print(f"\n  HYPOTHESIS CHECK:")
    if total_fee > 30:
        print(f"  ✅ Fee is major problem: {total_fee:.1f}% total across windows")
    else:
        print(f"  ⚠️ Fee not main issue ({total_fee:.1f}%)")
    if total_switches / len(windows) > 10:
        print(f"  ✅ Too many switches: {total_switches/len(windows):.0f}/window")
    else:
        print(f"  ⚠️ Switch count moderate ({total_switches/len(windows):.0f}/window)")

if __name__ == "__main__":
    main()
