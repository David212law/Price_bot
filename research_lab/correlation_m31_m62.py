import sys, os, json, math
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_m62_funding_momentum, load_data
from research_lab.unified_master import detect_regime
from datetime import datetime, timezone

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

def monthly_returns_from_trades(trades):
    """تبدیل تریدها به بازدهی ماهانه"""
    monthly = {}
    for t in trades:
        ts = t.get("t", 0)
        if ts < 1e12: ts *= 1000
        month = datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime("%Y-%m")
        monthly[month] = monthly.get(month, 0) + t["ret"]
    return monthly

def calc_corr(x_list, y_list):
    n = min(len(x_list), len(y_list))
    if n < 3: return 0
    x, y = x_list[-n:], y_list[-n:]
    mx, my = sum(x)/n, sum(y)/n
    cov = sum((a-mx)*(b-my) for a,b in zip(x,y))
    sx = math.sqrt(sum((a-mx)**2 for a in x))
    sy = math.sqrt(sum((b-my)**2 for b in y))
    return cov/(sx*sy) if sx*sy > 0 else 0

def load_m31_monthly(exchange):
    """بازدهی ماهانه M31 از داده فاندینگ"""
    from research_lab.m31_economic_metrics import extract_rates
    monthly = {}
    symbols = {
        "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
        "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
        "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
    }
    for sym in symbols.get(exchange, []):
        path = {
            "kucoin": f"exchanges/kucoin/data/{sym}_funding_full.json",
            "aster": f"data/aster/{sym}_funding.json",
            "hyperliquid": f"data/hyperliquid/{sym}_funding.json",
        }.get(exchange, "")
        if not os.path.exists(path):
            # fallback
            path = f"exchanges/kucoin/data/{sym}_funding.json" if exchange=="kucoin" else ""
        if not path or not os.path.exists(path): continue
        try:
            with open(path) as f: data = json.load(f)
            for r in extract_rates(data):
                month = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m")
                monthly[month] = monthly.get(month, 0) + r["rate"]
        except: pass
    return monthly

def main():
    print("=== 🔍 Correlation M31 (Funding) vs M62 (Trend) ===\n")
    for exchange, symbols in EXCHANGES.items():
        print(f"═══ {exchange.upper()} ═══")
        m62_monthly = {}
        for sym in symbols:
            candles = load_data(exchange, sym)
            if not candles: continue
            trades = strategy_m62_funding_momentum(candles)
            # فیلتر TREND
            trend_trades = []
            for t in trades:
                if t.get("t", 0) <= 0: continue
                ts_idx = next((i for i, c in enumerate(candles) if c["t"] >= t["t"]), -1)
                if ts_idx > 50 and detect_regime(candles, ts_idx) == "TREND":
                    trend_trades.append(t)
            monthly = monthly_returns_from_trades(trend_trades)
            for m, v in monthly.items():
                m62_monthly[m] = m62_monthly.get(m, 0) + v
        
        m31_monthly = load_m31_monthly(exchange)
        common = sorted(set(m62_monthly.keys()) & set(m31_monthly.keys()))
        
        if len(common) < 6:
            print(f"  ⚠️ Only {len(common)} common months (insufficient for correlation)")
            continue
        
        m62_series = [m62_monthly[m] for m in common]
        m31_series = [m31_monthly[m] for m in common]
        corr = calc_corr(m62_series, m31_series)
        verdict = "✅ مستقل (Diversifier واقعی)" if abs(corr) < 0.3 else "⚠️ همبسته (Diversifier ضعیف)" if abs(corr) < 0.7 else "❌ بسیار همبسته (بدون تنوع)"
        print(f"  Months: {len(common)} | Correlation: {corr:+.3f} | {verdict}")

if __name__ == "__main__":
    main()
