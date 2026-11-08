"""Test v2 on LUNA + FTX crashes — the two biggest crypto crashes."""
import sys
sys.path.insert(0, "scripts")
from regime_bot_v2 import load, daily_rets, simulate_v2

def main():
    print("=" * 84)
    print(" v2 on REAL CRASHES — LUNA + FTX")
    print("=" * 84)

    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)

    # Real crash windows
    crashes = [
        ("ATH collapse",   "2021-11-15", "2022-01-25"),
        ("Pre-LUNA bear",  "2022-04-01", "2022-05-01"),
        ("LUNA crash",     "2022-05-01", "2022-06-15"),
        ("Summer 2022",    "2022-06-15", "2022-09-01"),
        ("FTX collapse",   "2022-11-01", "2022-12-15"),
        ("Post-FTX",       "2022-12-15", "2023-01-15"),
        ("May 2025 (bad)", "2025-02-01", "2025-05-01"),
    ]

    print(f"\n  {'Event':<18} {'v2(h=7)':>10} {'v2(h=5)':>10} {'v1(h=0)':>10} {'Tether':>10}")
    print("  " + "-" * 62)

    for name, start, end in crashes:
        r7 = simulate_v2(start, end, tmn, tether, all_rets, 7, 14)
        r5 = simulate_v2(start, end, tmn, tether, all_rets, 5, 14)
        r1 = simulate_v2(start, end, tmn, tether, all_rets, 0, 0)
        if r7 and r5 and r1:
            print(f"  {name:<18} {r7['total_return']:>+9.1f}% {r5['total_return']:>+9.1f}% "
                  f"{r1['total_return']:>+9.1f}%    +0.0%")
            # DD analysis for h=7
            print(f"    └─ h=7 DD={r7['max_dd']:.1f}%, switches={r7['switches']}")

    print(f"\n{'='*84}")
    print(" INTERPRETATION")
    print("=" * 84)
    print("  اگر h=7 در LUNA/FTX نزدیک صفر یا مثبت است → v2 آماده Paper")
    print("  اگر h=7 در LUNA/FTX منفی بزرگ است → نیاز به defensive overlay")
    print("  اگر DD در LUNA/FTX > 10% است → Live Gate ممکن نیست")

if __name__ == "__main__":
    main()
