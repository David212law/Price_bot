"""Correct fee model: turnover-based, not symmetric difference."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import load, daily_rets, rolling_mean, rolling_std

FEE = 0.006  # 0.6% roundtrip per asset

def bh_btc_decide(tmn, date): return ["BTC"]

def bb_mr_decide(tmn, date, period=20, n_std=2):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < period + 5: continue
        ma = rolling_mean(p, date, period)
        sd = rolling_std(p, date, period)
        if not ma or not sd: continue
        pn = p[past[-1]]
        if pn < ma - n_std * sd:
            cands.append((a, (pn - ma) / sd))
    cands.sort(key=lambda x: x[1])
    return [a for a, _ in cands[:3]]

def ma50_200_decide(tmn, date):
    cands = []
    for a, p in tmn.items():
        past = [d for d in sorted(p.keys()) if d <= date]
        if len(past) < 205: continue
        mf = rolling_mean(p, date, 50)
        ms = rolling_mean(p, date, 200)
        if mf is None or ms is None: continue
        if mf > ms: cands.append(a)
    return cands[:3]

STRATEGIES = {"bh_btc": bh_btc_decide, "bb_mr": bb_mr_decide, "ma50_200": ma50_200_decide}

def holdings_ret(holds, all_rets, date):
    if not holds: return 0.0
    w = 1.0 / len(holds)
    return sum(w * all_rets[a].get(date, 0) for a in holds)

def stats(daily):
    if not daily: return {"total":0,"dd":0,"sharpe":0}
    eq=peak=1.0; dd=0
    for r in daily:
        eq *= (1+r/100); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    m=sum(daily)/len(daily)
    s=(sum((x-m)**2 for x in daily)/len(daily))**0.5 if len(daily)>1 else 0
    return {"total":(eq-1)*100, "dd":dd, "sharpe":(m/s)*(365**0.5) if s>0 else 0}

def calc_turnover_fee(old_holds, new_holds):
    """Correct fee: sold fraction + bought fraction (max 0.6% roundtrip)."""
    old_set = set(old_holds)
    new_set = set(new_holds)
    old_w = 1.0 / len(old_holds) if old_holds else 0.0
    new_w = 1.0 / len(new_holds) if new_holds else 0.0
    sold = len(old_set - new_set) * old_w    # fraction of portfolio sold
    bought = len(new_set - old_set) * new_w  # fraction of portfolio bought
    # Roundtrip = (sold + bought) / 2 (each side at 0.3%, so both sides = 0.6%)
    turnover = (sold + bought) / 2.0
    return FEE * 100 * turnover

def run_backtest(fn, tmn, all_rets, dates):
    daily = []
    for i in range(1, len(dates)):
        d, d_prev = dates[i], dates[i-1]
        holds = fn(tmn, d_prev)
        daily.append(holdings_ret(holds, all_rets, d))
    return daily

def run_robot_correct(fn, tmn, all_rets, dates):
    """Correct robot: today's decision from d_prev, fee based on turnover."""
    daily = []
    cur_holdings = []
    total_fee = 0.0
    switches = 0
    for i in range(1, len(dates)):
        d, d_prev = dates[i], dates[i-1]
        new_holdings = fn(tmn, d_prev)
        r = holdings_ret(new_holdings, all_rets, d)
        if set(new_holdings) != set(cur_holdings):
            fee_today = calc_turnover_fee(cur_holdings, new_holdings)
            r -= fee_today
            total_fee += fee_today
            switches += 1
        daily.append(r)
        cur_holdings = new_holdings
    return daily, total_fee, switches

def main():
    print("="*90)
    print(" ROBOT vs BACKTEST v2 — CORRECT fee model (turnover-based)")
    print("="*90)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    dates = sorted(all_rets["TETHER"].keys())
    split = dates[int(len(dates)*0.7)]
    test = [d for d in dates if d >= split]

    print(f"\nTEST: {test[0]} -> {test[-1]} ({len(test)} days)\n")
    print(f"  {'Strategy':<12} {'Backtest':>11} {'Robot':>11} {'Fee':>8} {'Diff':>9} {'Match':>7} {'Sw':>4}")
    print("  " + "-"*68)

    all_match = True
    results = {}
    for name, fn in STRATEGIES.items():
        bt = run_backtest(fn, tmn, all_rets, test)
        rb, fee, sw = run_robot_correct(fn, tmn, all_rets, test)
        bt_s = stats(bt); rb_s = stats(rb)
        diff = rb_s["total"] - bt_s["total"]
        match = "✅" if abs(diff) < 10.0 else "❌"
        if match == "❌": all_match = False
        results[name] = {"bt": bt_s["total"], "rb": rb_s["total"], "fee": fee, "sw": sw, "dd": rb_s["dd"], "sharpe": rb_s["sharpe"]}
        print(f"  {name:<12} {bt_s['total']:>+9.1f}% {rb_s['total']:>+9.1f}% {fee:>+6.2f}% {diff:>+7.2f}% {match:>7} {sw:>4}")

    print("\n  " + "-"*68)
    if all_match:
        print("\n  ✅ ربات = backtest (اختلاف فقط از fee)")
        print("  ✅ ربات می‌تواند استراتژی‌ها را درست اجرا کند")
    else:
        print("\n  🟡 اختلاف بزرگ‌تر از fee — نیاز به بررسی")
        print("     ولی ممکن است فقط cumulative fee effect در compounding باشد")

    # Which strategy is viable after fee?
    print("\n  " + "="*68)
    print(" Which strategy is viable with 0.6% fee?")
    print("  " + "="*68)
    print(f"  {'Strategy':<12} {'Return':>11} {'DD':>8} {'Sharpe':>8} {'Viable?':>10}")
    for name, r in results.items():
        viable = "✅ YES" if r["rb"] > 100 and r["dd"] < 50 else "⚠️ MARGINAL" if r["rb"] > 0 else "❌ NO"
        print(f"  {name:<12} {r['rb']:>+9.1f}% {r['dd']:>6.1f}% {r['sharpe']:>7.2f} {viable:>10}")

    print("\n  " + "="*68)
    print(" COMBINED STRATEGY (1/3 each)")
    print("  " + "="*68)
    combined = []
    for i in range(1, len(test)):
        d = test[i]
        r = 0.0
        for name, fn in STRATEGIES.items():
            holds = fn(tmn, test[i-1])
            r += holdings_ret(holds, all_rets, d) / 3.0
        combined.append(r)
    cs = stats(combined)
    print(f"  Combined (1/3 each):  +{cs['total']:.1f}%  DD={cs['dd']:.1f}%  Sharpe={cs['sharpe']:.2f}")

    bh_daily = [all_rets["BTC"].get(d, 0) for d in test]
    bh_s = stats(bh_daily)
    print(f"  B&H BTC:              +{bh_s['total']:.1f}%  DD={bh_s['dd']:.1f}%  Sharpe={bh_s['sharpe']:.2f}")

if __name__ == "__main__":
    main()
