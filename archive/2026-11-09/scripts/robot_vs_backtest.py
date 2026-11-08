"""Test: does the robot correctly execute each strategy? Compare robot vs direct backtest."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime_bot_v2 import load, daily_rets, rolling_mean, rolling_std

FEE = 0.006

# ─── Strategy decision functions (pure logic) ───

def bh_btc_decide(tmn, date):
    return ["BTC"]

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

STRATEGIES = {
    "bh_btc":    bh_btc_decide,
    "bb_mr":     bb_mr_decide,
    "ma50_200":  ma50_200_decide,
}

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

def run_backtest(strategy_fn, tmn, all_rets, dates):
    """Direct backtest: honest returns (decision T, return T+1)."""
    daily = []
    for i in range(1, len(dates)):
        d, d_prev = dates[i], dates[i-1]
        holds = strategy_fn(tmn, d_prev)
        daily.append(holdings_ret(holds, all_rets, d))
    return daily

def run_robot(strategy_fn, tmn, all_rets, dates):
    """Robot simulation: state machine with fee on every position change."""
    daily = []
    cur_holdings = []
    for i in range(1, len(dates)):
        d, d_prev = dates[i], dates[i-1]
        # Robot makes decision based on d_prev
        new_holdings = strategy_fn(tmn, d_prev)
        # Apply today's return based on PREVIOUS holdings
        r = holdings_ret(cur_holdings, all_rets, d)
        # Fee on change
        if set(new_holdings) != set(cur_holdings):
            r -= FEE * 100
        daily.append(r)
        cur_holdings = new_holdings
    return daily

def main():
    print("="*88)
    print(" ROBOT vs BACKTEST — does robot execute correctly?")
    print("="*88)
    tmn, tether = load()
    all_rets = {a: daily_rets(p) for a, p in tmn.items()}
    all_rets["TETHER"] = daily_rets(tether)
    dates = sorted(all_rets["TETHER"].keys())
    split = dates[int(len(dates)*0.7)]
    test = [d for d in dates if d >= split]

    print(f"\nTEST: {test[0]} -> {test[-1]} ({len(test)} days)\n")

    print(f"  {'Strategy':<12} {'Backtest':>12} {'Robot':>12} {'Diff':>10} {'Match?':>10} {'Switches':>10}")
    print("  " + "-"*76)

    all_match = True
    for name, fn in STRATEGIES.items():
        bt = run_backtest(fn, tmn, all_rets, test)
        rb = run_robot(fn, tmn, all_rets, test)
        bt_s = stats(bt); rb_s = stats(rb)
        diff = rb_s["total"] - bt_s["total"]
        match = "✅" if abs(diff) < 1.0 else "❌"
        if match == "❌": all_match = False

        # Count switches
        switches = 0
        cur = []
        for i in range(1, len(test)):
            new = fn(tmn, test[i-1])
            if set(new) != set(cur):
                switches += 1
            cur = new

        print(f"  {name:<12} {bt_s['total']:>+10.1f}% {rb_s['total']:>+10.1f}% {diff:>+8.2f}% {match:>10} {switches:>9}")

    print("\n  " + "-"*76)
    if all_match:
        print("\n  ✅ همه سه استراتژی: ربات = backtest (اختلاف < ۱٪)")
        print("  ✅ ربات می‌تواند استراتژی‌ها را درست اجرا کند")
        print("  → آماده ترکیب سه استراتژی")
    else:
        print("\n  ❌ ربات ≠ backtest — باگ در ربات")
        print("  → قبل از ترکیب، باید باگ را پیدا کنیم")

    # Additional detail: show what fee did
    print("\n  " + "="*76)
    print(" Fee impact analysis")
    print("  " + "="*76)
    for name, fn in STRATEGIES.items():
        bt = run_backtest(fn, tmn, all_rets, test)
        rb = run_robot(fn, tmn, all_rets, test)
        bt_s = stats(bt); rb_s = stats(rb)
        # Backtest has no fee, robot has fee
        # So diff SHOULD equal -fee_total
        print(f"  {name:<12} backtest-no-fee: {bt_s['total']:+10.1f}%  robot-with-fee: {rb_s['total']:+10.1f}%  fee cost: {rb_s['total']-bt_s['total']:+.2f}%")

if __name__ == "__main__":
    main()
