"""Diagnose v4a failures — which windows lost and why."""
import sys
sys.path.insert(0, "scripts")
from regime_bot_v2 import load, daily_rets
from regime_bot_v4 import simulate_v4

tmn, tether = load()
all_rets = {a: daily_rets(p) for a, p in tmn.items()}
all_rets["TETHER"] = daily_rets(tether)

windows = [
    ("W1 Feb-May 2023", "2023-02-01", "2023-05-01"),
    ("W2 Aug-Nov 2023", "2023-08-01", "2023-11-01"),
    ("W3 Feb-May 2024", "2024-02-01", "2024-05-01"),
    ("W4 Aug-Nov 2024", "2024-08-01", "2024-11-01"),
    ("W5 Feb-May 2025", "2025-02-01", "2025-05-01"),
    ("W6 Aug 2025-Feb 2026", "2025-08-01", "2026-02-01"),
]

print(f"{'Window':<22} {'v2':>10} {'v4a':>10} {'v4b':>10} {'Trails v4a':>12}")
print("=" * 70)
for name, s, e in windows:
    r2 = simulate_v4(s, e, tmn, tether, all_rets, 7, 14, trail_pct=-999)
    r4a = simulate_v4(s, e, tmn, tether, all_rets, 7, 14, trail_pct=-10)
    r4b = simulate_v4(s, e, tmn, tether, all_rets, 7, 14, trail_pct=-15)
    if r2 and r4a and r4b:
        diff_a = r4a['return'] - r2['return']
        mark = "✅" if diff_a > 0 else "⚠️" if diff_a > -5 else "❌"
        print(f"{name:<22} {r2['return']:>+8.1f}% {r4a['return']:>+8.1f}% "
              f"{r4b['return']:>+8.1f}% {r4a['trails']:>6} {mark}")

print("\n" + "=" * 70)
print("تحلیل:")
print("  اگر v4a در W5 (May 2025) بهتر است ولی در W1/W2/W6 بدتر:")
print("    → trail در slow-bleed کمک می‌کند ولی در bull recovery ضرر می‌زند")
print("  اگر v4a در همه پنجره‌ها بهتر است:")
print("    → چرا wins 4/6 شد؟ (باگ در شمارش یا پنجره ناشناخته)")
