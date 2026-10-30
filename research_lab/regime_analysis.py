import sys, os, json
sys.path.append(os.getcwd())
from strategies.core_engine import (strategy_a20, strategy_m40, strategy_m35,
                                     strategy_a8, strategy_m60_liq_reversal,
                                     strategy_m62_funding_momentum,
                                     load_data, calculate_metrics,
                                     calc_atr, calc_rsi)

def classify_regime(candles, i, adx_period=14):
    """طبقه‌بندی رژیم بازار در لحظه i"""
    if i < adx_period * 2:
        return "UNKNOWN"
    # محاسبه ADX با پنجره i
    window = candles[max(0, i - 50):i+1]
    if len(window) < 30: return "UNKNOWN"
    adx_val = calc_adx_simple(window, adx_period)
    if adx_val is None: return "UNKNOWN"
    if adx_val > 25: return "TREND"
    if adx_val < 20: return "RANGE"
    return "NEUTRAL"

def calc_adx_simple(candles, period=14):
    """محاسبه ساده ADX"""
    if len(candles) < period * 2: return None
    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, len(candles)):
        h, l, ph, pl, pc = candles[i]["h"], candles[i]["l"], candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        tr = max(h-l, abs(h-pc), abs(l-pc))
        up = h - ph
        down = pl - l
        trs.append(tr)
        plus_dm.append(up if (up > down and up > 0) else 0)
        minus_dm.append(down if (down > up and down > 0) else 0)
    if len(trs) < period: return None
    atr = sum(trs[:period]) / period
    plus_di_sum = sum(plus_dm[:period])
    minus_di_sum = sum(minus_dm[:period])
    dxs = []
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
        plus_di_sum = plus_di_sum - plus_di_sum/period + plus_dm[i]
        minus_di_sum = minus_di_sum - minus_di_sum/period + minus_dm[i]
        if atr == 0: dx = 0
        else:
            pdi = 100 * plus_di_sum / (atr * period)
            mdi = 100 * minus_di_sum / (atr * period)
            dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0
        dxs.append(dx)
    if len(dxs) < period: return None
    adx = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        adx = (adx * (period - 1) + dxs[i]) / period
    return adx

def tag_trades_with_regime(trades, candles):
    """برچسب‌گذاری هر معامله با رژیم زمان ورود"""
    if not trades: return []
    # نگاشت timestamp به index
    ts_to_idx = {c["t"]: i for i, c in enumerate(candles)}
    tagged = []
    for t in trades:
        entry_t = t.get("t", 0)
        # پیدا کردن نزدیک‌ترین کندل
        idx = ts_to_idx.get(entry_t, -1)
        if idx < 0:
            # جستجوی دودویی
            for i, c in enumerate(candles):
                if c["t"] >= entry_t:
                    idx = i; break
        if idx < 0: idx = len(candles) - 1
        regime = classify_regime(candles, idx)
        tagged.append({**t, "regime": regime})
    return tagged

def regime_metrics(trades):
    """محاسبه متریک‌ها به تفکیک رژیم"""
    by_regime = {}
    for t in trades:
        r = t.get("regime", "UNKNOWN")
        by_regime.setdefault(r, []).append(t)
    
    result = {}
    for regime, ts in by_regime.items():
        m = calculate_metrics(ts)
        result[regime] = m
    return result

def analyze_strategy(name, func, exchange, symbols):
    """تحلیل یک استراتژی به تفکیک رژیم"""
    print(f"\n─── {name} on {exchange.upper()} ───")
    all_tagged = []
    
    for sym in symbols:
        candles = load_data(exchange, sym)
        if not candles: continue
        trades = func(candles)
        tagged = tag_trades_with_regime(trades, candles)
        all_tagged.extend(tagged)
    
    if len(all_tagged) < 20:
        print(f"  ⚠️ Only {len(all_tagged)} trades")
        return None
    
    by_regime = regime_metrics(all_tagged)
    
    print(f"  Total: {len(all_tagged)} trades")
    print(f"  {'Regime':10} | {'n':>4} | {'PF':>5} | {'WR%':>5} | {'Avg Ret':>8}")
    print("  " + "-" * 45)
    for regime in ["TREND", "NEUTRAL", "RANGE", "UNKNOWN"]:
        if regime not in by_regime: continue
        m = by_regime[regime]
        if m.get("status") != "OK": 
            print(f"  {regime:10} | {m.get('n', 0):4} | n/a")
            continue
        pf = m.get("pf", 0)
        wr = m.get("win_rate", 0)
        # میانگین بازده
        rets = [t["ret"] for t in all_tagged if t["regime"] == regime]
        avg_ret = sum(rets)/len(rets)*100 if rets else 0
        print(f"  {regime:10} | {m['n']:4} | {pf:5.2f} | {wr:5.1f} | {avg_ret:+7.3f}%")
    
    return by_regime

def main():
    print("=" * 60)
    print("  🎯 Regime Detection — تحلیل رژیم‌محور استراتژی‌ها")
    print("=" * 60)
    print("\nتعریف رژیم:")
    print("  TREND:   ADX > 25")
    print("  NEUTRAL: 20 ≤ ADX ≤ 25")
    print("  RANGE:   ADX < 20")
    print("\nهدف: آیا استراتژی در رژیم خاصی لبه دارد؟")
    
    EXCHANGES = {
        "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
        "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    }
    STRATEGIES = {
        "A20": strategy_a20,
        "M40": strategy_m40,
        "M35": lambda c: strategy_m35(c, fast=50, slow=200),
        "M60": strategy_m60_liq_reversal,
    }
    
    for ex, syms in EXCHANGES.items():
        for name, func in STRATEGIES.items():
            analyze_strategy(name, func, ex, syms)

if __name__ == "__main__":
    main()
