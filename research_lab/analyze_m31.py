"""D-479: Deep analysis of M31 — day-of-week, trend, tail risk, funding."""
import sys; sys.path.insert(0, '.')
from research_lab.audit_core import portfolio_daily_returns, calc_sharpe
from datetime import datetime
from collections import defaultdict

def analyze(exchange, symbols):
    print(f"\n{'='*65}")
    print(f" M31 Deep Analysis: {exchange.upper()}")
    print(f"{'='*65}")
    
    daily = portfolio_daily_returns(exchange, symbols)
    if not daily:
        print("  No data"); return
    
    rets = [r for _, r in daily]
    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in daily]
    
    # ─── 1. Day of week ───
    print("\n[1] By day of week (avg return)")
    by_dow = defaultdict(list)
    for dt, r in zip(dates, rets):
        by_dow[dt.weekday()].append(r)
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for dow in range(7):
        if dow in by_dow:
            rets_dow = by_dow[dow]
            avg = sum(rets_dow) / len(rets_dow) * 100
            print(f"  {names[dow]}: n={len(rets_dow):3d}, avg={avg:+.3f}%/day")
    
    # ─── 2. Trend context (BTC direction) ───
    print("\n[2] By market trend (proxy: sign of recent 7-day avg)")
    up_rets, down_rets, flat_rets = [], [], []
    for i in range(7, len(rets)):
        recent = rets[i-7:i]
        avg7 = sum(recent) / 7
        if avg7 > 0.0001: up_rets.append(rets[i])
        elif avg7 < -0.0001: down_rets.append(rets[i])
        else: flat_rets.append(rets[i])
    
    for label, arr in [("UP trend (>0)", up_rets), ("DOWN trend (<0)", down_rets), ("FLAT", flat_rets)]:
        if arr:
            m = sum(arr)/len(arr)
            print(f"  {label:20s}: n={len(arr):3d}, avg={m*100:+.4f}%/day")
    
    # ─── 3. Tail risk (worst days) ───
    print("\n[3] Tail risk (worst 5 days)")
    sorted_days = sorted(zip(daily, rets), key=lambda x: x[1])[:5]
    for (d, _), r in sorted_days:
        print(f"  {d}: {r*100:+.3f}%")
    
    # ─── 4. Funding distribution ───
    neg_days = sum(1 for r in rets if r < 0)
    pos_days = sum(1 for r in rets if r > 0)
    print(f"\n[4] Return distribution")
    print(f"  Positive days: {pos_days:3d} ({pos_days/len(rets)*100:.1f}%)")
    print(f"  Negative days: {neg_days:3d} ({neg_days/len(rets)*100:.1f}%)")
    print(f"  Worst 5%:      {sorted(rets)[int(len(rets)*0.05)]*100:+.4f}%/day")
    print(f"  Best 5%:       {sorted(rets)[int(len(rets)*0.95)]*100:+.4f}%/day")
    
    # ─── 5. Half-year decay ───
    print("\n[5] Half-year Sharpe decay")
    by_period = defaultdict(list)
    for d, r in daily:
        # 2024-H1, 2024-H2, 2025-H1, ...
        year, month = d[:4], int(d[5:7])
        half = "H1" if month <= 6 else "H2"
        by_period[f"{year}-{half}"].append(r)
    for period in sorted(by_period.keys()):
        arr = by_period[period]
        if len(arr) < 30: continue
        m = calc_sharpe(arr)
        if m:
            print(f"  {period}: n={m['n']:3d}, SR={m['sharpe']:>6.2f}, Ret={m['ann_ret_pct']:>6.2f}%")

analyze("hyperliquid", ["BTC","ETH","SOL","BNB","XRP","AVAX"])
analyze("aster", ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"])
analyze("kucoin", ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"])
