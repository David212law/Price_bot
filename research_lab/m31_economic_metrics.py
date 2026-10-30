import sys, os, json, math
sys.path.append(os.getcwd())

def extract_rates(records):
    rates = []
    if not records: return rates
    if isinstance(records, dict):
        for k in ["data", "results", "funding", "history"]:
            if k in records and isinstance(records[k], list):
                records = records[k]; break
    if not isinstance(records, list): return rates
    for r in records:
        if not isinstance(r, dict): continue
        rate = None
        for key in ["fundingRate", "rate", "funding_rate", "value", "funding"]:
            if key in r:
                try: rate = float(r[key]); break
                except: pass
        t = 0
        for key in ["time", "t", "fundingTime", "timestamp", "created_at"]:
            if key in r:
                try: t = int(r[key]); break
                except: pass
        if rate is not None and t > 0:
            rates.append({"t": t, "rate": rate})
    rates.sort(key=lambda x: x["t"])
    return rates

def analyze_m31(exchange, symbols, leverage=6, fee_per_trade=0.0004):
    """محاسبه Sharpe, بازدهی سالانه, MaxDD واقعی"""
    all_rates = []
    for sym in symbols:
        if exchange == "kucoin":
            path = f"exchanges/kucoin/data/{sym}_funding_full.json"
            if not os.path.exists(path):
                path = f"exchanges/kucoin/data/{sym}_funding.json"
        elif exchange == "aster":
            path = f"data/aster/{sym}_funding.json"
        else:
            path = f"data/hyperliquid/{sym}_funding.json"
        
        if not os.path.exists(path): continue
        try:
            with open(path) as f:
                data = json.load(f)
            all_rates.extend(extract_rates(data))
        except: pass
    
    if len(all_rates) < 100:
        return None
    
    # هر رکورد = یک پرداخت فاندینگ (نه هر کندل)
    all_rates.sort(key=lambda x: x["t"])
    
    # بازدهی هر پرداخت (با اهرم)
    returns = [r["rate"] * leverage for r in all_rates]
    
    n = len(returns)
    mean_ret = sum(returns) / n
    variance = sum((r - mean_ret)**2 for r in returns) / (n - 1)
    std_ret = math.sqrt(variance)
    
    # Sharpe (annualized): فرض 3 پرداخت/روز
    trades_per_year = 365 * 3
    annual_return = mean_ret * trades_per_year
    annual_vol = std_ret * math.sqrt(trades_per_year)
    sharpe = (annual_return - 0.05) / annual_vol if annual_vol > 0 else 0
    
    # MaxDD واقعی (روی equity curve)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= (1 + r)
        if equity > peak: peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd: max_dd = dd
    
    # Avg Win/Loss
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    avg_win = sum(wins)/len(wins) if wins else 0
    avg_loss = sum(losses)/len(losses) if losses else 0
    pf = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 99.99
    
    # دوره داده
    period_days = (all_rates[-1]["t"] - all_rates[0]["t"]) / (24*3600*1000)
    
    return {
        "exchange": exchange,
        "n_payments": n,
        "period_days": round(period_days, 1),
        "mean_rate_pct": round(mean_ret*100, 4),
        "annual_return_pct": round(annual_return*100, 2),
        "annual_vol_pct": round(annual_vol*100, 2),
        "sharpe": round(sharpe, 2),
        "max_dd_pct": round(max_dd*100, 2),
        "win_rate_pct": round(len(wins)/n*100, 1),
        "avg_win_pct": round(avg_win*100, 4),
        "avg_loss_pct": round(avg_loss*100, 4),
        "profit_factor": round(pf, 2),
        "final_equity_x": round(equity, 3),
    }

def main():
    print("=== 💰 M31 — Economic Significance (Sharpe, MaxDD, Return) ===\n")
    print("NOTE: هر رکورد = یک پرداخت فاندینگ (نه هر کندل)\n")
    
    SYMBOLS = {
        "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
        "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
        "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
    }
    
    print(f"{'Exchange':12} | {'n':>6} | {'Days':>6} | {'Ann.Ret%':>9} | {'Sharpe':>7} | {'MaxDD%':>7} | {'PF':>5} | {'WR%':>5}")
    print("-" * 85)
    
    for ex, syms in SYMBOLS.items():
        r = analyze_m31(ex, syms)
        if not r:
            print(f"{ex:12} | n/a (insufficient data)")
            continue
        print(f"{r['exchange']:12} | {r['n_payments']:6} | {r['period_days']:6} | {r['annual_return_pct']:9.2f} | {r['sharpe']:7.2f} | {r['max_dd_pct']:7.2f} | {r['profit_factor']:5.2f} | {r['win_rate_pct']:5.1f}")
    
    print("\n" + "="*85)
    print("\n📊 تفسیر:")
    print("  Sharpe > 2.0 = لبه قوی")
    print("  Sharpe 1.0-2.0 = لبه متوسط")
    print("  Sharpe < 1.0 = لبه ضعیف (حتی اگر P<0.0001)")
    print("  Ann.Ret% = بازدهی سالانه خالص (با اهرم 6x)")

if __name__ == "__main__":
    main()
