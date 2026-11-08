"""Regime-aware multi-strategy bot — walk-forward validation."""
import json
from datetime import datetime, timedelta
from collections import Counter

FEE_ROUNDTRIP = 0.006  # 0.6% Wallex


def load_data():
    crypto = json.load(open("data/crypto_5y_usd.json"))
    usd_irr = json.load(open("data/usd_irr_tgju.json"))
    tmn = {}
    for sym, prices in crypto.items():
        if not sym.endswith("-USD"):
            continue
        base = sym[:-4]
        tmn[base] = {d: p * usd_irr[d] / 10 for d, p in prices.items() if d in usd_irr}
    tether = {d: usd_irr[d] / 10 for d in usd_irr}
    return tmn, tether


def daily_rets(prices):
    r = {}
    dates = sorted(prices.keys())
    for i in range(1, len(dates)):
        d0, d1 = dates[i - 1], dates[i]
        try:
            if (datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d0, "%Y-%m-%d")).days != 1:
                continue
        except:
            continue
        if prices[d0] > 0:
            r[d1] = (prices[d1] / prices[d0] - 1) * 100
    return r


def rolling_mean(prices, date, window):
    past = [prices[d] for d in sorted(prices.keys()) if d <= date][-window:]
    return sum(past) / len(past) if past else None


def rolling_std(prices, date, window):
    past = [prices[d] for d in sorted(prices.keys()) if d <= date][-window:]
    if len(past) < window:
        return None
    m = sum(past) / len(past)
    return (sum((p - m) ** 2 for p in past) / len(past)) ** 0.5


def detect_regime(btc_prices, date):
    """Multi-signal regime: BTC 30d momentum + volatility."""
    past_dates = [d for d in sorted(btc_prices.keys()) if d < date]
    if len(past_dates) < 60:
        return None
    p_now = btc_prices[past_dates[-1]]
    p_30 = btc_prices[past_dates[-30]]
    p_60 = btc_prices[past_dates[-60]]
    ret_30 = (p_now / p_30 - 1) * 100
    # Volatility: std of last 30 daily returns
    rets_30 = []
    for i in range(-30, -1):
        if i - 1 >= -len(past_dates):
            d1 = past_dates[i]
            d0 = past_dates[i - 1]
            try:
                if (datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d0, "%Y-%m-%d")).days != 1:
                    continue
            except:
                continue
            if btc_prices[d0] > 0:
                rets_30.append((btc_prices[d1] / btc_prices[d0] - 1) * 100)
    if len(rets_30) < 15:
        return None
    vol = (sum((r - sum(rets_30) / len(rets_30)) ** 2 for r in rets_30) / len(rets_30)) ** 0.5
    # Combined
    if ret_30 > 15 and vol < 6:
        return "BULL_STRONG"
    if ret_30 > 5:
        return "BULL"
    if ret_30 > -5:
        return "FLAT"
    if ret_30 > -15:
        return "BEAR"
    return "CRASH"


def momentum_candidates(tmn, date):
    """Return assets in strong uptrend, sorted by 30d return."""
    cands = []
    for asset, prices in tmn.items():
        past = [d for d in sorted(prices.keys()) if d <= date]
        if len(past) < 60:
            continue
        p_now = prices[past[-1]]
        p_30 = prices[past[-30]]
        ma50 = rolling_mean(prices, date, 50)
        if ma50 is None:
            continue
        ret_30 = (p_now / p_30 - 1) * 100
        if ret_30 > 0 and p_now > ma50:
            cands.append((asset, ret_30))
    cands.sort(key=lambda x: -x[1])
    return [a for a, _ in cands]


def meanrev_candidates(tmn, date):
    """Return assets below MA20 - 2σ."""
    cands = []
    for asset, prices in tmn.items():
        past = [d for d in sorted(prices.keys()) if d <= date]
        if len(past) < 40:
            continue
        p_now = prices[past[-1]]
        ma20 = rolling_mean(prices, date, 20)
        sd20 = rolling_std(prices, date, 20)
        if ma20 is None or sd20 is None or sd20 == 0:
            continue
        z = (p_now - ma20) / sd20
        if z < -2:
            cands.append((asset, z))
    cands.sort(key=lambda x: x[1])  # most oversold first
    return [a for a, _ in cands]


def simulate(start_date, end_date, tmn, tether, all_rets):
    """Run regime bot over date range. Returns daily portfolio returns."""
    dates = sorted(set(all_rets["TETHER"].keys()))
    dates = [d for d in dates if start_date <= d <= end_date]
    if len(dates) < 30:
        return None

    daily_returns = []
    holdings = {"TETHER": 1.0}
    switches = 0
    last_regime = None

    for date in dates:
        regime = detect_regime(tmn["BTC"], date) if "BTC" in tmn else None
        if regime is None:
            daily_returns.append(0.0)
            continue

        # Compute today's portfolio return (before rebalance)
        day_ret = 0.0
        for asset, w in holdings.items():
            if asset == "TETHER":
                continue
            if date in all_rets.get(asset, {}):
                day_ret += w * all_rets[asset][date]
            # tether returns 0 by definition (base)

        daily_returns.append(day_ret)

        # Rebalance if regime changed
        if regime != last_regime:
            new_holdings = {"TETHER": 1.0}
            if regime in ("BULL_STRONG", "BULL"):
                n = 2 if regime == "BULL_STRONG" else 3
                cands = momentum_candidates(tmn, date)
                if cands:
                    w = 1.0 / len(cands[:n])
                    new_holdings = {a: w for a in cands[:n]}
            elif regime == "FLAT":
                cands = meanrev_candidates(tmn, date)
                if cands:
                    w = 1.0 / min(3, len(cands))
                    new_holdings = {a: w for a in cands[:3]}
            elif regime == "BEAR":
                new_holdings = {"TETHER": 0.5, "BCH": 0.5}
            # CRASH: 100% tether

            # Only count switch if changed
            if set(new_holdings.keys()) != set(holdings.keys()):
                switches += 1
                # Fee on rebalance
                if daily_returns:
                    daily_returns[-1] -= FEE_ROUNDTRIP * 100
            holdings = new_holdings
            last_regime = regime

    if not daily_returns:
        return None

    # Cumulative
    eq = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in daily_returns:
        eq *= (1 + r / 100)
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100
        max_dd = max(max_dd, dd)

    total_ret = (eq - 1) * 100
    mean_d = sum(daily_returns) / len(daily_returns)
    std_d = (sum((r - mean_d) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
    sharpe = (mean_d / std_d) * (365 ** 0.5) if std_d > 0 else 0

    return {
        "days": len(daily_returns),
        "total_return": total_ret,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "switches": switches,
        "mean_daily": mean_d,
    }


def simulate_baseline(start_date, end_date, all_rets, strategy="tether"):
    """Baseline: tether only, or momentum-only."""
    dates = sorted(set(all_rets["TETHER"].keys()))
    dates = [d for d in dates if start_date <= d <= end_date]
    if not dates:
        return None

    daily_returns = []
    for date in dates:
        if strategy == "tether":
            daily_returns.append(0.0)
        elif strategy == "momentum":
            # Simple: BTC if 30d > 0, else tether
            btc_dates = sorted([d for d in all_rets["BTC"].keys() if d <= date])
            if len(btc_dates) < 31:
                daily_returns.append(0.0)
                continue
            p0 = None
            # Use all_rets directly
            # Not trivial here — skip for simplicity
            daily_returns.append(all_rets["BTC"].get(date, 0))

    eq = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in daily_returns:
        eq *= (1 + r / 100)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100)
    total_ret = (eq - 1) * 100
    mean_d = sum(daily_returns) / len(daily_returns) if daily_returns else 0
    std_d = (sum((r - mean_d) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5 if daily_returns else 0
    return {
        "days": len(daily_returns),
        "total_return": total_ret,
        "sharpe": (mean_d / std_d) * (365 ** 0.5) if std_d > 0 else 0,
        "max_dd": max_dd,
    }


def main():
    print("=" * 84)
    print(" Regime-aware multi-strategy bot — walk-forward validation")
    print("=" * 84)

    tmn, tether = load_data()
    all_series = dict(tmn)
    all_series["TETHER"] = tether
    all_rets = {name: daily_rets(s) for name, s in all_series.items()}

    # Walk-forward windows
    windows = [
        ("2023-02-01", "2023-05-01"),  # test 1 (post FTX recovery)
        ("2023-08-01", "2023-11-01"),  # test 2
        ("2024-02-01", "2024-05-01"),  # test 3 (ETF rally)
        ("2024-08-01", "2024-11-01"),  # test 4
        ("2025-02-01", "2025-05-01"),  # test 5
        ("2025-08-01", "2026-02-01"),  # test 6
    ]

    print(f"\n  {'Window':<24} {'Bot':>12} {'Tether':>10} {'DD%':>8} {'Sharpe':>10} {'Switch':>8}")
    print("  " + "-" * 76)

    bot_totals = []
    tether_totals = []

    for start, end in windows:
        r_bot = simulate(start, end, tmn, tether, all_rets)
        r_teth = simulate_baseline(start, end, all_rets, "tether")
        if r_bot and r_teth:
            print(f"  {start}→{end}  {r_bot['total_return']:>+10.1f}% "
                  f"{r_teth['total_return']:>+8.1f}% {r_bot['max_dd']:>7.1f}% "
                  f"{r_bot['sharpe']:>9.2f} {r_bot['switches']:>7}")
            bot_totals.append(r_bot['total_return'])
            tether_totals.append(r_teth['total_return'])

    # Summary
    if bot_totals:
        print(f"\n{'='*84}")
        print(" Summary across all test windows")
        print("=" * 84)
        avg_bot = sum(bot_totals) / len(bot_totals)
        avg_teth = sum(tether_totals) / len(tether_totals)
        wins = sum(1 for b, t in zip(bot_totals, tether_totals) if b > t)
        print(f"  Avg bot return:    {avg_bot:+.1f}%")
        print(f"  Avg tether return: {avg_teth:+.1f}%")
        print(f"  Bot beats tether:  {wins}/{len(bot_totals)} windows")
        print(f"  Compounded bot:    {(1+avg_bot/100)**12 - 1:+.0%} / year (approx)")

    # Save
    output = {
        "windows": [
            {"start": s, "end": e} for s, e in windows
        ],
        "bot_totals": bot_totals,
        "tether_totals": tether_totals,
    }
    json.dump(output, open("data/regime_bot_v1_results.json", "w"), indent=2)
    print(f"\n  Saved data/regime_bot_v1_results.json")


if __name__ == "__main__":
    main()
