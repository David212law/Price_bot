"""D-466: Check if M31 Sharpe is decaying over time (2024 vs 2025 vs 2026)."""
import sys; sys.path.insert(0, '.')
from research_lab.audit_core import portfolio_daily_returns, calc_sharpe
from collections import defaultdict

def check_decay(exchange, symbols):
    print(f"\n{'='*50}")
    print(f" Funding Decay Check: {exchange.upper()}")
    print(f"{'='*50}")
    
    # دریافت بازده‌های روزانه M31
    daily = portfolio_daily_returns(exchange, symbols)
    
    # گروه‌بندی بر اساس سال
    by_year = defaultdict(list)
    for date_str, ret in daily:
        year = date_str[:4]  # YYYY
        by_year[year].append(ret)
        
    for year in sorted(by_year.keys()):
        rets = by_year[year]
        if len(rets) < 30:
            print(f"  {year}: n={len(rets):3d} (insufficient data)")
            continue
        
        m = calc_sharpe(rets)
        if m:
            print(f"  {year}: n={m['n']:3d} | Sharpe: {m['sharpe']:>6.3f} | AnnRet: {m['ann_ret_pct']:>6.2f}% | AnnVol: {m['ann_vol_pct']:>5.2f}%")
        else:
            print(f"  {year}: n={len(rets)} (calc error)")

# تست روی هر ۳ صرافی
check_decay("hyperliquid", ["BTC","ETH","SOL","BNB","XRP","AVAX"])
check_decay("aster", ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"])
check_decay("kucoin", ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"])
