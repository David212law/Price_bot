"""v3 = v2 + emergency crash detector (fast exit on big drop)."""
import sys
sys.path.insert(0, "scripts")
from regime_bot_v2 import (
    load, daily_rets, detect_regime, regime_to_strategy,
    compute_holdings, holdings_equal, FEE
)
from datetime import datetime


def simulate_v3(start, end, tmn, tether, all_rets, hysteresis, cooldown,
                crash_threshold=-15.0, crash_lookback=3):
    """v3 adds emergency crash override."""
    dates = [d for d in sorted(all_rets["TETHER"].keys()) if start <= d <= end]
    if len(dates) < 10: return None
    holdings = {"TETHER": 1.0}
    current_strategy = "TETHER"
    pending_strategy = None
    pending_count = 0
    days_since_switch = 999
    daily = []
    switch_count = 0
    crash_triggers = 0

    for date in dates:
        regime = detect_regime(tmn["BTC"], date)

        # ── Emergency crash check ──
        btc_past = [d for d in sorted(tmn["BTC"].keys()) if d < date][-crash_lookback:]
        crash_signal = False
        if len(btc_past) >= crash_lookback:
            p0 = tmn["BTC"][btc_past[0]]
            p1 = tmn["BTC"][btc_past[-1]]
            if p0 > 0:
                crash_ret = (p1/p0 - 1) * 100
                if crash_ret < crash_threshold:
                    crash_signal = True

        if regime is None and not crash_signal:
            daily.append(0.0); days_since_switch += 1
            continue

        strategy = regime_to_strategy(regime) if regime else "DEFENSIVE"

        # Emergency override: if crash → 100% tether immediately
        if crash_signal and current_strategy != "DEFENSIVE":
            new_h = {"TETHER": 1.0}
            if not holdings_equal(holdings, new_h):
                holdings = new_h
                current_strategy = "DEFENSIVE"
                daily.append(-FEE * 100)
                days_since_switch = 0
                switch_count += 1
                crash_triggers += 1
                pending_strategy = None
                pending_count = 0
                continue

        if strategy != current_strategy:
            if pending_strategy == strategy:
                pending_count += 1
            else:
                pending_strategy = strategy
                pending_count = 1
        else:
            pending_strategy = None
            pending_count = 0

        dr = 0.0
        for a, w in holdings.items():
            if a == "TETHER": continue
            if date in all_rets.get(a, {}):
                dr += w * all_rets[a][date]

        if (pending_count >= hysteresis and
            days_since_switch >= cooldown and
            strategy != current_strategy):
            new_h = compute_holdings(strategy, tmn, date)
            if not holdings_equal(holdings, new_h):
                holdings = new_h
                current_strategy = strategy
                dr -= FEE * 100
                days_since_switch = 0
                switch_count += 1
                pending_strategy = None
                pending_count = 0

        daily.append(dr)
        days_since_switch += 1

    eq = 1.0; peak = 1.0; max_dd = 0
    for r in daily:
        eq *= (1 + r/100)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak-eq)/peak*100)
    total = (eq-1)*100
    mean = sum(daily)/len(daily)
    std = (sum((r-mean)**2 for r in daily)/len(daily))**0.5 if daily else 0
    sharpe = (mean/std)*(365**0.5) if std > 0 else 0
    return {
        "return": total, "dd": max_dd, "sharpe": sharpe,
        "switches": switch_count, "crashes": crash_triggers,
    }


def main():
    print("=" * 84)
    print(" v3 — v2 + emergency crash detector")
    print("=" * 84)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)

    windows = [
        ("2023-02-01","2023-05-01"), ("2023-08-01","2023-11-01"),
        ("2024-02-01","2024-05-01"), ("2024-08-01","2024-11-01"),
        ("2025-02-01","2025-05-01"), ("2025-08-01","2026-02-01"),
    ]
    crashes = [
        ("ATH collapse",   "2021-11-15","2022-01-25"),
        ("Pre-LUNA bear",  "2022-04-01","2022-05-01"),
        ("LUNA crash",     "2022-05-01","2022-06-15"),
        ("Summer 2022",    "2022-06-15","2022-09-01"),
        ("FTX collapse",   "2022-11-01","2022-12-15"),
        ("Post-FTX",       "2022-12-15","2023-01-15"),
    ]

    configs = [
        ("v2 (h=7, no crash)", 7, 14, -999),   # no crash override
        ("v3a (-10%/3d)",      7, 14, -10),
        ("v3b (-15%/3d)",      7, 14, -15),
        ("v3c (-20%/3d)",      7, 14, -20),
        ("v3d (-15%/5d)",      7, 14, -15),    # different lookback? no, uses 3
    ]

    # ── Test windows ──
    print(f"\n  6-window test:")
    print(f"  {'Config':<22} {'AVG':>8} {'WINS':>6} {'Worst':>8} {'SW':>5} {'Crash':>6}")
    print("  " + "-" * 66)
    for name, h, c, crash_thresh in configs[:4]:  # same lookback
        returns = []
        total_sw = 0; total_cr = 0
        for s, e in windows:
            if crash_thresh == -999:
                # v2 without crash → call v3 with disabled crash (thresh very low)
                r = simulate_v3(s, e, tmn, tether, all_rets, h, c, crash_threshold=-999)
            else:
                r = simulate_v3(s, e, tmn, tether, all_rets, h, c, crash_threshold=crash_thresh)
            if r:
                returns.append(r["return"])
                total_sw += r["switches"]
                total_cr += r["crashes"]
        avg = sum(returns)/len(returns)
        wins = sum(1 for x in returns if x > 0)
        print(f"  {name:<22} {avg:>+7.1f}% {wins:>4}/6 {min(returns):>+7.1f}% {total_sw:>5} {total_cr:>6}")

    # ── Crisis test ──
    print(f"\n  Crisis test (return/DD):")
    print(f"  {'Event':<18} {'v2':>12} {'v3b(-15%)':>14}")
    print("  " + "-" * 50)
    for cname, s, e in crashes:
        r2 = simulate_v3(s, e, tmn, tether, all_rets, 7, 14, crash_threshold=-999)
        r3 = simulate_v3(s, e, tmn, tether, all_rets, 7, 14, crash_threshold=-15)
        if r2 and r3:
            print(f"  {cname:<18} {r2['return']:>+6.1f}/{r2['dd']:>4.1f}% {r3['return']:>+6.1f}/{r3['dd']:>4.1f}%")

    # May 2025 special attention
    print(f"\n  May 2025 (the bad case):")
    r2 = simulate_v3("2025-02-01","2025-05-01", tmn, tether, all_rets, 7, 14, -999)
    r3 = simulate_v3("2025-02-01","2025-05-01", tmn, tether, all_rets, 7, 14, -15)
    print(f"    v2 (no crash):  return {r2['return']:+.1f}%  DD {r2['dd']:.1f}%  switches {r2['switches']}")
    print(f"    v3b (-15%/3d):  return {r3['return']:+.1f}%  DD {r3['dd']:.1f}%  crashes {r3['crashes']}")


if __name__ == "__main__":
    main()
