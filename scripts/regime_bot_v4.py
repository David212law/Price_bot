"""v4 = v2 + trailing stop from peak (better for slow bleeds)."""
import sys
sys.path.insert(0, "scripts")
from regime_bot_v2 import (
    load, daily_rets, detect_regime, regime_to_strategy,
    compute_holdings, holdings_equal, FEE
)


def simulate_v4(start, end, tmn, tether, all_rets, hysteresis, cooldown,
                trail_pct=-20.0, trail_lookback=30):
    """v4 adds trailing stop: exit if BTC drops X% from recent peak."""
    dates = [d for d in sorted(all_rets["TETHER"].keys()) if start <= d <= end]
    if len(dates) < 10: return None
    holdings = {"TETHER": 1.0}
    current_strategy = "TETHER"
    pending_strategy = None
    pending_count = 0
    days_since_switch = 999
    daily = []
    switch_count = 0
    trail_triggers = 0

    btc_dates = sorted(tmn["BTC"].keys())

    for date in dates:
        regime = detect_regime(tmn["BTC"], date)

        # ── Trailing stop check ──
        btc_past = [d for d in btc_dates if d <= date][-trail_lookback:]
        trail_signal = False
        if len(btc_past) >= trail_lookback // 2:
            peak = max(tmn["BTC"][d] for d in btc_past)
            current = tmn["BTC"][btc_past[-1]]
            if peak > 0:
                drawdown = (current / peak - 1) * 100
                if drawdown < trail_pct:
                    trail_signal = True

        if regime is None and not trail_signal:
            daily.append(0.0); days_since_switch += 1
            continue

        strategy = regime_to_strategy(regime) if regime else "DEFENSIVE"

        # Trailing stop override
        if trail_signal and current_strategy != "DEFENSIVE":
            new_h = {"TETHER": 1.0}
            if not holdings_equal(holdings, new_h):
                holdings = new_h
                current_strategy = "DEFENSIVE"
                daily.append(-FEE * 100)
                days_since_switch = 0
                switch_count += 1
                trail_triggers += 1
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

    eq = 1.0; peak_eq = 1.0; max_dd = 0
    for r in daily:
        eq *= (1 + r/100)
        peak_eq = max(peak_eq, eq)
        max_dd = max(max_dd, (peak_eq-eq)/peak_eq*100)
    total = (eq-1)*100
    mean = sum(daily)/len(daily)
    std = (sum((r-mean)**2 for r in daily)/len(daily))**0.5 if daily else 0
    sharpe = (mean/std)*(365**0.5) if std > 0 else 0
    return {"return": total, "dd": max_dd, "sharpe": sharpe,
            "switches": switch_count, "trails": trail_triggers}


def main():
    print("=" * 84)
    print(" v4 — v2 + trailing stop from 30-day peak")
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
        ("ATH collapse","2021-11-15","2022-01-25"),
        ("Pre-LUNA","2022-04-01","2022-05-01"),
        ("LUNA","2022-05-01","2022-06-15"),
        ("Summer 2022","2022-06-15","2022-09-01"),
        ("FTX","2022-11-01","2022-12-15"),
        ("May 2025","2025-02-01","2025-05-01"),
    ]

    configs = [
        ("v2 (no trail)",  -999),
        ("v4a (-10%)",     -10),
        ("v4b (-15%)",     -15),
        ("v4c (-20%)",     -20),
        ("v4d (-25%)",     -25),
    ]

    print(f"\n  6-window test:")
    print(f"  {'Config':<18} {'AVG':>8} {'WINS':>6} {'Worst':>8} {'SW':>4} {'Trails':>7}")
    print("  " + "-" * 62)
    for name, thresh in configs:
        returns, total_sw, total_tr = [], 0, 0
        for s, e in windows:
            r = simulate_v4(s, e, tmn, tether, all_rets, 7, 14, trail_pct=thresh)
            if r:
                returns.append(r["return"])
                total_sw += r["switches"]
                total_tr += r["trails"]
        avg = sum(returns)/len(returns)
        wins = sum(1 for x in returns if x > 0)
        print(f"  {name:<18} {avg:>+7.1f}% {wins:>4}/6 {min(returns):>+7.1f}% {total_sw:>4} {total_tr:>7}")

    print(f"\n  Crisis + May 2025 (return / DD):")
    print(f"  {'Event':<16} {'v2':>14} {'v4c(-20%)':>16}")
    print("  " + "-" * 50)
    for cname, s, e in crashes:
        r2 = simulate_v4(s, e, tmn, tether, all_rets, 7, 14, trail_pct=-999)
        r4 = simulate_v4(s, e, tmn, tether, all_rets, 7, 14, trail_pct=-20)
        if r2 and r4:
            print(f"  {cname:<16} {r2['return']:>+6.1f}/{r2['dd']:>4.1f}% {r4['return']:>+6.1f}/{r4['dd']:>4.1f}%")


if __name__ == "__main__":
    main()
