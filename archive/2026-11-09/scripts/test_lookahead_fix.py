"""Test look-ahead fix: decision at T-1, return at T."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import load, daily_rets, rolling_mean, detect_regime

def mom_decide(tmn, date, n=20, top_n=3):
    """Decide at 'date' using ONLY data up to and including 'date' (close)."""
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

def main():
    print("="*80)
    print(" TEST LOOK-AHEAD FIX — decision at T-1 close, return at T")
    print("="*80)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    dates = sorted(all_rets["TETHER"].keys())
    split = dates[int(len(dates)*0.7)]
    test_dates = [d for d in dates if d >= split]

    print(f"\nTest period: {test_dates[0]} -> {test_dates[-1]} ({len(test_dates)} days)")

    # ── OLD (buggy): decide today, apply to today's return ──
    old_daily = []
    for d in test_dates:
        holdings = mom_decide(tmn, d, n=20)  # BUG: uses today
        r = 0.0
        for a in holdings:
            r += (1.0/len(holdings)) * all_rets[a].get(d, 0) if holdings else 0
        old_daily.append(r if holdings else 0)

    # ── NEW (fixed): decide yesterday, apply to today's return ──
    new_daily = []
    prev_holdings = []
    for i, d in enumerate(test_dates):
        # Apply yesterday's decision to today's return
        if prev_holdings:
            r = sum((1.0/len(prev_holdings)) * all_rets[a].get(d, 0) for a in prev_holdings)
        else:
            r = 0  # in tether
        new_daily.append(r)
        # Make decision today for tomorrow
        prev_holdings = mom_decide(tmn, d, n=20)

    def stats(daily):
        eq=peak=1.0; dd=0
        for r in daily:
            eq *= (1+r/100); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
        m=sum(daily)/len(daily)
        s=(sum((x-m)**2 for x in daily)/len(daily))**0.5
        return (eq-1)*100, dd, (m/s)*(365**0.5) if s>0 else 0

    old_tot, old_dd, old_sh = stats(old_daily)
    new_tot, new_dd, new_sh = stats(new_daily)

    # B&H benchmark
    bh_daily = [all_rets["BTC"].get(d, 0) for d in test_dates]
    bh_tot, bh_dd, bh_sh = stats(bh_daily)

    print(f"\n  {'Strategy':<30} {'Total':>15} {'DD':>8} {'Sharpe':>8}")
    print("  " + "-"*65)
    print(f"  {'OLD (buggy, look-ahead)':<30} {old_tot:>+13.1f}% {old_dd:>6.1f}% {old_sh:>7.2f}")
    print(f"  {'NEW (fixed, no look-ahead)':<30} {new_tot:>+13.1f}% {new_dd:>6.1f}% {new_sh:>7.2f}")
    print(f"  {'B&H BTC-TMN':<30} {bh_tot:>+13.1f}% {bh_dd:>6.1f}% {bh_sh:>7.2f}")

    print(f"\n  Fix effect:")
    print(f"    Old return: {old_tot:+.1f}%")
    print(f"    New return: {new_tot:+.1f}%")
    print(f"    Difference: {old_tot - new_tot:+.1f}% (باید بزرگ باشد اگه باگ واقعی بود)")

    print(f"\n  Verdict:")
    if old_tot > 10000 and new_tot < 5000:
        print(f"  ✅ باگ واقعی بود. Fix کار می‌کند.")
        print(f"  ✅ حالا می‌توانیم ۱۴ استراتژی را با اطمینان تست کنیم.")
    elif abs(old_tot - new_tot) < 100:
        print(f"  ⚠️ تفاوت کم — شاید باگ جای دیگری بود")
    else:
        print(f"  🟡 تفاوت متوسط — نیاز به بررسی")

    print(f"\n  مقایسه fix شده با B&H:")
    if new_tot > bh_tot:
        print(f"  ✅ mom20 (fix) از B&H بهتر: {new_tot:.1f}% vs {bh_tot:.1f}%")
    else:
        print(f"  ❌ mom20 (fix) از B&H بدتر: {new_tot:.1f}% vs {bh_tot:.1f}%")

if __name__ == "__main__":
    main()
