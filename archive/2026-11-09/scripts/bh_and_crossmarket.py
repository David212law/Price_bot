"""Test 1: B&H comparison. Test 2: Cross-market BTC-USD."""
import sys
sys.path.insert(0, "scripts")
from regime_bot_v2 import load, daily_rets
from regime_bot_v4 import simulate_v4
import json

def main():
    print("=" * 90)
    print(" Test 1: B&H comparison | Test 2: Cross-market BTC-USD")
    print("=" * 90)

    tmn, tether = load()
    crypto_usd = json.load(open("data/crypto_5y_usd.json"))

    tmn_usd = {}
    for sym, prices in crypto_usd.items():
        if not sym.endswith("-USD"): continue
        tmn_usd[sym[:-4]] = dict(prices)

    usd_dates = sorted(tmn_usd["BTC"].keys())
    tether_usd = {d: 1.0 for d in usd_dates}

    all_rets_tmn = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets_tmn["TETHER"] = daily_rets(tether)
    all_rets_usd = {a: daily_rets(p) for a, p in tmn_usd.items()}
    all_rets_usd["TETHER"] = daily_rets(tether_usd)

    windows = [
        ("W1 Feb-May 2023", "2023-02-01", "2023-05-01"),
        ("W2 Aug-Nov 2023", "2023-08-01", "2023-11-01"),
        ("W3 Feb-May 2024", "2024-02-01", "2024-05-01"),
        ("W4 Aug-Nov 2024", "2024-08-01", "2024-11-01"),
        ("W5 Feb-May 2025", "2025-02-01", "2025-05-01"),
        ("W6 Aug 25-Feb 26", "2025-08-01", "2026-02-01"),
    ]

    def bh(prices, s, e):
        ds = sorted([d for d in prices if s <= d <= e])
        if len(ds) < 2: return None
        return (prices[ds[-1]]/prices[ds[0]] - 1) * 100

    print("\n" + "=" * 90)
    print(" TEST 1: v4a vs B&H (بازار ایران)")
    print("=" * 90)
    print(f"\n  {'Window':<20} {'v4a':>9} {'B&H BTC-TMN':>13} {'B&H TTR':>10} {'alpha vs BTC':>13}")
    print("  " + "-" * 82)

    alphas_tmn = []
    for name, s, e in windows:
        r = simulate_v4(s, e, tmn, tether, all_rets_tmn, 7, 14, trail_pct=-10)
        b_btc = bh(tmn["BTC"], s, e)
        b_ttr = bh(tether, s, e)
        if r and b_btc is not None:
            a = r["return"] - b_btc
            alphas_tmn.append(a)
            mark = "✅" if a > 0 else "❌"
            print(f"  {name:<20} {r['return']:>+7.1f}% {b_btc:>+11.1f}% {b_ttr:>+8.1f}% {a:>+11.1f}% {mark}")

    if alphas_tmn:
        pos = sum(1 for a in alphas_tmn if a > 0)
        print(f"\n  v4a > B&H BTC-TMN:  {pos}/{len(alphas_tmn)}  |  Avg alpha: {sum(alphas_tmn)/len(alphas_tmn):+.1f}%")

    print("\n" + "=" * 90)
    print(" TEST 2: v4a روی BTC-USD خالص (بازار جهانی)")
    print("=" * 90)
    print(f"  USD data: {len(usd_dates)} روز ({usd_dates[0]} → {usd_dates[-1]})")
    print(f"\n  {'Window':<20} {'v4a':>9} {'B&H BTC-USD':>13} {'alpha vs BTC':>13}")
    print("  " + "-" * 62)

    alphas_usd = []
    for name, s, e in windows:
        r = simulate_v4(s, e, tmn_usd, tether_usd, all_rets_usd, 7, 14, trail_pct=-10)
        b_btc = bh(tmn_usd["BTC"], s, e)
        if r and b_btc is not None:
            a = r["return"] - b_btc
            alphas_usd.append(a)
            mark = "✅" if a > 0 else "❌"
            print(f"  {name:<20} {r['return']:>+7.1f}% {b_btc:>+11.1f}% {a:>+11.1f}% {mark}")

    if alphas_usd:
        pos = sum(1 for a in alphas_usd if a > 0)
        print(f"\n  v4a > B&H BTC-USD:  {pos}/{len(alphas_usd)}  |  Avg alpha: {sum(alphas_usd)/len(alphas_usd):+.1f}%")

    print("\n" + "=" * 90)
    print(" FINAL")
    print("=" * 90)
    p_tmn = sum(1 for a in alphas_tmn if a > 0) if alphas_tmn else 0
    p_usd = sum(1 for a in alphas_usd if a > 0) if alphas_usd else 0

    if p_tmn >= 4 and p_usd >= 4:
        print("\n  ✅ alpha واقعی + عمومی — v4a در هر دو بازار از B&H بهتر")
        print("     قدم بعد: Fee-adjusted + Walk-forward ۵ ساله")
    elif p_tmn >= 4 and p_usd < 4:
        print("\n  🟡 Iran-specific — alpha فقط در TMN")
        print("     ماهیت احتمالی: carry ارزی (لانگ USD/IRR)")
        print("     قدم بعد: بازتعریف به‌عنوان Iran-carry، نه regime-edge")
    elif p_tmn < 4 and p_usd >= 4:
        print("\n  🟡 Unusual — alpha در USD ولی نه TMN")
        print("     نیاز به بررسی")
    else:
        print("\n  ❌ v4a از B&H بدتر است در هر دو بازار")
        print("     ۹ ساعت کار، به artifact رسید")
        print("     توصیه: پرونده IR-REG بسته (D-17), برگشت به M31 hedged")

if __name__ == "__main__":
    main()
