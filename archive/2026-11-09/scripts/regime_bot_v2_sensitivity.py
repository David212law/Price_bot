"""Sensitivity test — is h=5 a peak or a robust range?"""
import sys
sys.path.insert(0, "scripts")
from regime_bot_v2 import (
    load, daily_rets, simulate_v2
)

def main():
    print("=" * 84)
    print(" v2 Sensitivity — is h=5 fitted or robust?")
    print("=" * 84)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    windows = [
        ("2023-02-01","2023-05-01"), ("2023-08-01","2023-11-01"),
        ("2024-02-01","2024-05-01"), ("2024-08-01","2024-11-01"),
        ("2025-02-01","2025-05-01"), ("2025-08-01","2026-02-01"),
    ]
    print(f"\n  {'h':>3} {'c':>3} {'AVG':>8} {'WINS':>6} {'SW':>4} {'Worst':>8} {'Best':>8}")
    print("  " + "-" * 60)
    best_avg, best_cfg = -999, None
    for h in range(2, 10):
        for c in [7, 10, 14, 21]:
            returns, total_sw = [], 0
            for s, e in windows:
                r = simulate_v2(s, e, tmn, tether, all_rets, h, c)
                returns.append(r["total_return"] if r else 0)
                total_sw += r["switches"] if r else 0
            avg = sum(returns)/len(returns)
            wins = sum(1 for x in returns if x > 0)
            mark = ""
            if avg > best_avg:
                best_avg = avg; best_cfg = (h, c); mark = " ←"
            print(f"  {h:>3} {c:>3} {avg:>+7.1f}% {wins:>4}/6 {total_sw:>4} {min(returns):>+7.1f}% {max(returns):>+7.1f}%{mark}")
    print(f"\n  Best: h={best_cfg[0]}, c={best_cfg[1]} (avg {best_avg:+.1f}%)")
    print(f"\n  INTERPRETATION:")
    print(f"  - اگر h=4,5,6 همه avg > +7% → h=5 robust، نه fitted")
    print(f"  - اگر فقط h=5 پیک بود → fitted، نیاز به cross-validation")

if __name__ == "__main__":
    main()
