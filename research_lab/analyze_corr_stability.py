"""D-482: Diagnose WHY correlations are unstable for Keltner, LOW_VOL, DUAL_MOMENTUM."""
import sys; sys.path.insert(0, '.')
import json, math
from research_lab.audit_core import portfolio_daily_returns
from research_lab.pooled_returns import pooled_returns
from research_lab.audit_core import correlation_stability

STATE_FILE = 'research_lab/logs/profiles/state.json'

def calc_corr(a, b, dates):
    if len(dates) < 20: return None
    va = [a[d] for d in dates]
    vb = [b[d] for d in dates]
    ma = sum(va)/len(va); mb = sum(vb)/len(vb)
    cov = sum((va[i]-ma)*(vb[i]-mb) for i in range(len(va)))
    sa = math.sqrt(sum((v-ma)**2 for v in va))
    sb = math.sqrt(sum((v-mb)**2 for v in vb))
    return cov/(sa*sb) if sa>0 and sb>0 else None

def analyze_candidate(exchange, strategy, symbol, m31_rets, state, n_windows=8):
    # پیدا کردن entry در state
    pooled = pooled_returns(exchange, strategy, state)
    if not pooled:
        print(f"  {strategy}/{symbol} @ {exchange}: no returns")
        return
    
    common = sorted(set(pooled.keys()) & set(m31_rets.keys()))
    if len(common) < 40:
        print(f"  {strategy}/{symbol}: overlap n={len(common)} too small")
        return
    
    print(f"\n  ── {strategy}/{symbol} @ {exchange} (n={len(common)}) ──")
    
    # بازه‌های زمانی
    w = len(common) // n_windows
    corrs = []
    for i in range(n_windows):
        chunk = common[i*w:(i+1)*w]
        if len(chunk) < 10: continue
        c = calc_corr(m31_rets, pooled, chunk)
        if c is not None:
            start = chunk[0]
            end = chunk[-1]
            corrs.append(c)
            print(f"    {start} → {end}: corr={c:+.3f}")
    
    if corrs:
        mean_c = sum(corrs)/len(corrs)
        var_c = sum((c-mean_c)**2 for c in corrs)/(len(corrs)-1)
        std_c = math.sqrt(var_c)
        print(f"    Mean corr: {mean_c:+.3f} | Std: {std_c:.3f} | Stability: {'STABLE' if std_c<0.25 else 'UNSTABLE'}")
        
        # آیا corr با regime تغییر می‌کند؟
        try:
            from research_lab.composer import regime_by_date
            reg_by_date = regime_by_date(exchange)
            by_regime = {"TREND": [], "RANGE": [], "NEUTRAL": [], "UNKNOWN": []}
            for d in common:
                r = reg_by_date.get(d, "UNKNOWN")
                by_regime.setdefault(r, []).append(d)
            
            print(f"    By regime:")
            for r, dates in by_regime.items():
                if len(dates) < 20: continue
                c = calc_corr(m31_rets, pooled, dates)
                if c is not None:
                    print(f"      {r:8s}: n={len(dates):3d}, corr={c:+.3f}")
        except Exception as e:
            pass

def main():
    state = json.load(open(STATE_FILE))
    print("="*72)
    print(" CORRELATION STABILITY DIAGNOSTIC")
    print("="*72)
    
    for exchange in ["kucoin", "hyperliquid", "aster"]:
        syms = {
            "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
            "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
            "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
        }[exchange]
        m31 = dict(portfolio_daily_returns(exchange, syms))
        if not m31: continue
        
        print(f"\n{'='*72}")
        print(f" Exchange: {exchange.upper()}")
        print(f"{'='*72}")
        
        # تست کاندیدهای مختلف
        candidates = [
            ("LOW_VOL_CARRY", "SOLUSDTM" if exchange=="kucoin" else "SOLUSDT" if exchange=="aster" else "SOL"),
            ("KELTNER_REV", "ETHUSDTM" if exchange=="kucoin" else "ETHUSDT" if exchange=="aster" else "ETH"),
            ("DUAL_MOMENTUM", "XBTUSDTM" if exchange=="kucoin" else "BTCUSDT" if exchange=="aster" else "BTC"),
        ]
        
        for strat, sym in candidates:
            analyze_candidate(exchange, strat, sym, m31, state)

if __name__ == "__main__":
    main()
