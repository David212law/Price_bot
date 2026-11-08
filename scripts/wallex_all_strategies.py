"""300+ strategies on Wallex (TMN + USDT), honest backtest, per-regime, fee-included."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import daily_rets, rolling_mean, rolling_std
from collections import Counter

FEE = 0.006


def build_sweep():
    """Build 305+ strategies from parameter sweeps."""
    S = {}
    # mom_nd: 11 n × 5 top_n × 2 (ma_filter) = 110
    for n in [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 250]:
        for top in [1, 2, 3, 4, 5]:
            for filt in [True, False]:
                key = f"mom{n}_t{top}_{'ma' if filt else 'no'}"
                S[key] = (("mom", n, top, filt), )
    # break_n: 7 n × 5 top_n = 35
    for n in [10, 20, 30, 50, 100, 150, 200]:
        for top in [1, 2, 3, 4, 5]:
            S[f"brk{n}_t{top}"] = (("brk", n, top),)
    # ma_cross: 7 combos × 5 top = 35
    for f, s in [(5,20),(10,30),(20,50),(50,200),(100,200),(20,100),(30,90)]:
        for top in [1, 2, 3, 4, 5]:
            S[f"ma{f}_{s}_t{top}"] = (("ma", f, s, top),)
    # rsi_mr: 5 period × 5 threshold = 25
    for p in [7, 14, 21, 28, 35]:
        for th in [20, 25, 30, 35, 40]:
            S[f"rsi{p}_{th}"] = (("rsi_mr", p, th),)
    # bb_mr: 5 period × 5 n_std = 25
    for p in [10, 15, 20, 30, 40]:
        for ns in [1.5, 2, 2.5, 3, 3.5]:
            S[f"bb{p}_{ns}"] = (("bb", p, ns),)
    # rsi_rev: 5 period × 5 threshold = 25
    for p in [7, 14, 21, 28, 35]:
        for th in [60, 65, 70, 75, 80]:
            S[f"rsir{p}_{th}"] = (("rsi_rev", p, th),)
    # vol_break: 5
    for n in [10, 20, 30, 50, 100]:
        S[f"vol{n}"] = (("vol", n),)
    # trend: 5
    for n in [20, 50, 100, 150, 200]:
        S[f"trend{n}"] = (("trend", n),)
    # btfd: 15 (5 dip × 3 hold)
    for dip in [5, 10, 15, 20, 30]:
        for hold in [5, 10, 20]:
            S[f"btfd{dip}_h{hold}"] = (("btfd", dip, hold),)
    # equal_weight: 5
    for n in [2, 3, 5, 8, 10]:
        S[f"eq{n}"] = (("eq", n),)
    # calendar: 5
    S["mon"] = (("cal", "mon"),)
    S["tue"] = (("cal", "tue"),)
    S["wed"] = (("cal", "wed"),)
    S["eom"] = (("cal", "eom"),)
    S["bom"] = (("cal", "bom"),)
    # pairs: 5
    S["pair_btc_eth"] = (("pair", "BTC", "ETH"),)
    S["pair_btc_bnb"] = (("pair", "BTC", "BNB"),)
    S["pair_eth_bnb"] = (("pair", "ETH", "BNB"),)
    S["pair_btc_xrp"] = (("pair", "BTC", "XRP"),)
    S["pair_btc_trx"] = (("pair", "BTC", "TRX"),)
    # benchmarks: 10
    for a in ["BTC", "ETH", "BNB", "XRP", "TRX", "SOL", "DOGE", "ADA", "LINK", "AVAX"]:
        S[f"bh_{a}"] = (("bh", a),)
    S["tether"] = (("tether",),)
    return S


def resolve(fn_tuple, tmn, tether, date):
    """Execute strategy decision -> return list of asset names."""
    # Unwrap if tuple-in-tuple
    if isinstance(fn_tuple, tuple) and len(fn_tuple) == 1 and isinstance(fn_tuple[0], tuple):
        fn_tuple = fn_tuple[0]
    kind = fn_tuple[0]
    if kind == "mom":
        _, n, top, filt = fn_tuple
        cands = []
        for a, p in tmn.items():
            past = [d for d in sorted(p.keys()) if d <= date]
            if len(past) < n + 20: continue
            pn, pa = p[past[-1]], p[past[-n]]
            r = (pn/pa - 1) * 100
            if r > 0:
                if filt:
                    ma50 = rolling_mean(p, date, 50)
                    if ma50 and pn > ma50: cands.append((a, r))
                else:
                    cands.append((a, r))
        cands.sort(key=lambda x: -x[1])
        return [a for a,_ in cands[:top]]
    if kind == "brk":
        _, n, top = fn_tuple
        cands = []
        for a, p in tmn.items():
            past = [d for d in sorted(p.keys()) if d <= date]
            if len(past) < n + 5: continue
            pn = p[past[-1]]
            prev_max = max(p[d] for d in past[-n-1:-1])
            if pn > prev_max: cands.append(a)
        return cands[:top]
    if kind == "ma":
        _, f, s, top = fn_tuple
        cands = []
        for a, p in tmn.items():
            past = [d for d in sorted(p.keys()) if d <= date]
            if len(past) < s + 5: continue
            mf = rolling_mean(p, date, f); ms = rolling_mean(p, date, s)
            if mf and ms and mf > ms: cands.append(a)
        return cands[:top]
    if kind == "rsi_mr":
        _, p, th = fn_tuple
        cands = []
        for a, pr in tmn.items():
            past = [d for d in sorted(pr.keys()) if d <= date]
            if len(past) < p + 5: continue
            g = l = 0
            for i in range(-p, 0):
                d = pr[past[i]] - pr[past[i-1]]
                if d > 0: g += d
                else: l -= d
            if l == 0: continue
            rsi = 100 - 100/(1 + g/l)
            if rsi < th: cands.append((a, rsi))
        cands.sort(key=lambda x: x[1])
        return [a for a,_ in cands[:3]]
    if kind == "rsi_rev":
        _, p, th = fn_tuple
        cands = []
        for a, pr in tmn.items():
            past = [d for d in sorted(pr.keys()) if d <= date]
            if len(past) < p + 5: continue
            g = l = 0
            for i in range(-p, 0):
                d = pr[past[i]] - pr[past[i-1]]
                if d > 0: g += d
                else: l -= d
            if l == 0: continue
            rsi = 100 - 100/(1 + g/l)
            if rsi > th: cands.append((a, -rsi))
        cands.sort(key=lambda x: -x[1])
        return [a for a,_ in cands[:3]]
    if kind == "bb":
        _, p, ns = fn_tuple
        cands = []
        for a, pr in tmn.items():
            past = [d for d in sorted(pr.keys()) if d <= date]
            if len(past) < p + 5: continue
            ma = rolling_mean(pr, date, p); sd = rolling_std(pr, date, p)
            if not ma or not sd: continue
            pn = pr[past[-1]]
            if pn < ma - ns * sd: cands.append((a, (pn-ma)/sd))
        cands.sort(key=lambda x: x[1])
        return [a for a,_ in cands[:3]]
    if kind == "vol":
        _, n = fn_tuple
        cands = []
        for a, p in tmn.items():
            past = [d for d in sorted(p.keys()) if d <= date]
            if len(past) < n + 5: continue
            pn = p[past[-1]]
            rets = [(p[past[i]]/p[past[i-1]] - 1) for i in range(-n, 0)]
            v = (sum((r-sum(rets)/len(rets))**2 for r in rets)/len(rets))**0.5
            ret_1d = (pn/p[past[-2]] - 1)
            if ret_1d > 2 * v and ret_1d > 0: cands.append(a)
        return cands[:3]
    if kind == "trend":
        _, n = fn_tuple
        cands = []
        for a, p in tmn.items():
            past = [d for d in sorted(p.keys()) if d <= date]
            if len(past) < n + 5: continue
            ma = rolling_mean(p, date, n)
            if ma and p[past[-1]] > ma * 1.02: cands.append(a)
        return cands[:3]
    if kind == "btfd":
        _, dip, hold = fn_tuple
        cands = []
        for a, p in tmn.items():
            past = [d for d in sorted(p.keys()) if d <= date]
            if len(past) < 30: continue
            pn = p[past[-1]]
            p_5ago = p[past[-6]] if len(past) >= 6 else pn
            dip_pct = (pn/p_5ago - 1) * 100
            if dip_pct < -dip: cands.append(a)
        return cands[:3]
    if kind == "eq":
        _, n = fn_tuple
        return list(tmn.keys())[:n]
    if kind == "cal":
        _, which = fn_tuple
        from datetime import datetime
        try: dt = datetime.strptime(date, "%Y-%m-%d")
        except: return []
        wd = dt.weekday()
        dom = dt.day
        if which == "mon" and wd == 0: return ["BTC"]
        if which == "tue" and wd == 1: return ["BTC"]
        if which == "wed" and wd == 2: return ["BTC"]
        if which == "eom" and dom >= 25: return ["BTC"]
        if which == "bom" and dom <= 5: return ["BTC"]
        return []
    if kind == "pair":
        _, a1, a2 = fn_tuple
        return [a1, a2]
    if kind == "bh":
        _, a = fn_tuple
        return [a] if a in tmn else []
    if kind == "tether":
        return []
    return []


def main():
    print("="*100)
    print(" WALLEX ALL STRATEGIES — TMN + USDT, 300+, honest, per regime")
    print("="*100)

    strategies = build_sweep()
    print(f"\nStrategies built: {len(strategies)}")

    results_summary = {}

    for market in ["TMN", "USDT"]:
        print("\n" + "="*100)
        print(f" MARKET: {market}")
        print("="*100)

        fname = f"data/wallex_{market.lower()}_all.json"
        if not os.path.exists(fname):
            print(f"  {fname} not found — skip")
            continue
        data = json.load(open(fname))

        # Build {base: prices} dict
        suffix = market
        tmn = {}
        for sym, prices in data.items():
            if sym == "USDTTMN": continue
            if not sym.endswith(suffix): continue
            base = sym[:-len(suffix)]
            if len(prices) >= 100:  # need at least 100 days
                tmn[base] = prices

        tether = data.get("USDTTMN") or data.get("USDTUSDT") or {}
        if market == "USDT" and not tether:
            # For USDT market, tether base is stable
            tether = {d: 1.0 for d in (list(tmn.values())[0].keys() if tmn else [])}

        print(f"  Assets loaded: {len(tmn)}")
        if not tmn: continue

        all_rets = {a: daily_rets(p) for a, p in tmn.items()}
        all_rets["TETHER"] = daily_rets(tether)
        dates = sorted(all_rets["TETHER"].keys())
        if len(dates) < 200:
            print(f"  only {len(dates)} days — skip")
            continue

        print(f"  Days: {len(dates)} ({dates[0]} -> {dates[-1]})")

        # Precompute strategy returns
        print(f"\n  Precomputing {len(strategies)} strategies × {len(dates)} days...")
        strat_rets = {n: {} for n in strategies}

        for i in range(1, len(dates)):
            d, dp = dates[i], dates[i-1]
            for name, fn in strategies.items():
                holds = resolve(fn[0] if isinstance(fn, tuple) and len(fn) == 1 else fn, tmn, tether, dp)
                if not holds:
                    strat_rets[name][d] = 0.0
                else:
                    w = 1.0 / len(holds)
                    strat_rets[name][d] = sum(w * all_rets[a].get(d, 0) for a in holds)

        # Regime detection
        def regime_of(date):
            btc = tmn.get("BTC")
            if not btc: return None
            past = [d for d in sorted(btc.keys()) if d <= date]
            if len(past) < 30: return None
            ret = (btc[past[-1]]/btc[past[-30]] - 1) * 100
            if ret > 15: return "BULL_STRONG"
            if ret > 5: return "BULL"
            if ret > -5: return "FLAT"
            if ret > -15: return "BEAR"
            return "CRASH"

        regimes = {d: regime_of(d) for d in dates}
        regimes = {d: r for d, r in regimes.items() if r}

        split_idx = int(len(dates) * 0.7)
        split_date = dates[split_idx]
        train = [d for d in dates if d < split_date and d in regimes]
        test = [d for d in dates if d >= split_date and d in regimes]

        print(f"\n  TRAIN: {len(train)} days  |  TEST: {len(test)} days  |  split: {split_date}")

        if len(train) < 30 or len(test) < 30:
            print("  Insufficient regime days — skip")
            continue

        # Rank per regime on TRAIN
        print(f"\n  Ranking {len(strategies)} strategies per regime...")
        best_per_regime = {}
        for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
            rd = [d for d in train if regimes[d] == regime]
            if len(rd) < 15:
                best_per_regime[regime] = "tether"
                print(f"    {regime}: {len(rd)} train days — tether")
                continue
            scores = {n: sum(strat_rets[n].get(d, 0) for d in rd)/len(rd) for n in strategies}
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            best_per_regime[regime] = ranked[0][0]
            print(f"    {regime} ({len(rd)}d): best={ranked[0][0]} ({ranked[0][1]:+.4f}%/d), 2nd={ranked[1][0]}, 3rd={ranked[2][0]}")

        # Apply on TEST with fee
        combined = []
        cur = "tether"
        total_fee = 0.0
        switches = 0
        for d in test:
            idx = dates.index(d)
            prev = dates[idx-1] if idx > 0 else None
            r_prev = regimes.get(prev) if prev else None
            strat = best_per_regime.get(r_prev, "tether") if r_prev else "tether"
            ret = strat_rets[strat].get(d, 0)
            if strat != cur:
                ret -= FEE * 100 * 0.5
                total_fee += FEE * 100 * 0.5
                switches += 1
                cur = strat
            combined.append(ret)

        def stats(daily):
            if not daily: return (0, 0, 0)
            eq = peak = 1.0; dd = 0
            for r in daily:
                eq *= (1 + r/100); peak = max(peak, eq); dd = max(dd, (peak-eq)/peak*100)
            m = sum(daily)/len(daily)
            s = (sum((x-m)**2 for x in daily)/len(daily))**0.5 if len(daily) > 1 else 0
            return ((eq-1)*100, dd, (m/s)*(365**0.5) if s > 0 else 0)

        ct, cdd, csh = stats(combined)

        bh_btc_daily = [all_rets.get("BTC", {}).get(d, 0) for d in test]
        bht, bhdd, bhsh = stats(bh_btc_daily)

        print(f"\n  RESULTS on TEST:")
        print(f"    RegimeCombined: {ct:+.1f}% (DD {cdd:.1f}%, Sharpe {csh:.2f}), switches={switches}, fee={total_fee:.1f}%")
        print(f"    B&H BTC-TMN:    {bht:+.1f}% (DD {bhdd:.1f}%, Sharpe {bhsh:.2f})")
        print(f"    Excess:         {ct-bht:+.1f}%")

        # Top 10 best single on test (honest)
        test_bests = []
        for n in strategies:
            daily = [strat_rets[n].get(d, 0) for d in test]
            t, dd, sh = stats(daily)
            test_bests.append((n, t, dd, sh))
        test_bests.sort(key=lambda x: -x[3])
        print(f"\n  Top 5 single (by Sharpe):")
        for n, t, dd, sh in test_bests[:5]:
            print(f"    {n:<20} {t:>+10.1f}% (DD {dd:.1f}%, Sh {sh:.2f})")

        results_summary[market] = {
            "assets": len(tmn),
            "days": len(dates),
            "train": len(train),
            "test": len(test),
            "combined": {"total": ct, "dd": cdd, "sharpe": csh, "switches": switches, "fee": total_fee},
            "bnh_btc": {"total": bht, "dd": bhdd, "sharpe": bhsh},
            "excess": ct - bht,
            "best_per_regime": best_per_regime,
            "top_singles": test_bests[:5],
        }

    # Final summary
    print("\n" + "="*100)
    print(" FINAL COMPARISON")
    print("="*100)
    for market, r in results_summary.items():
        print(f"\n{market} market:")
        print(f"  Combined: {r['combined']['total']:+.1f}% (DD {r['combined']['dd']:.1f}%, Sh {r['combined']['sharpe']:.2f})")
        print(f"  B&H BTC:  {r['bnh_btc']['total']:+.1f}% (Sh {r['bnh_btc']['sharpe']:.2f})")
        print(f"  Excess:   {r['excess']:+.1f}%")
        print(f"  Best per regime:")
        for reg, strat in r["best_per_regime"].items():
            print(f"    {reg:<14} -> {strat}")

    json.dump(results_summary, open("data/wallex_300_strategies.json", "w"), indent=2)
    print("\nSaved: data/wallex_300_strategies.json")


if __name__ == "__main__":
    main()
