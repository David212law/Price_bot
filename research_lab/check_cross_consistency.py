"""D-466: Check if M31 across exchanges is correlated."""
import sys; sys.path.insert(0, '.')
from research_lab.audit_core import portfolio_daily_returns
import math

def corr(d1, d2):
    common = sorted(set(d1.keys()) & set(d2.keys()))
    if len(common) < 30: return 0
    va = [d1[d] for d in common]
    vb = [d2[d] for d in common]
    ma, mb = sum(va)/len(va), sum(vb)/len(vb)
    cov = sum((va[i]-ma)*(vb[i]-mb) for i in range(len(va)))
    sa = math.sqrt(sum((x-ma)**2 for x in va))
    sb = math.sqrt(sum((x-mb)**2 for x in vb))
    return cov/(sa*sb) if sa>0 and sb>0 else 0

hl = dict(portfolio_daily_returns("hyperliquid", ["BTC","ETH","SOL","BNB","XRP","AVAX"]))
as_ = dict(portfolio_daily_returns("aster", ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"]))
kc = dict(portfolio_daily_returns("kucoin", ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]))

print(f"Correlation HL vs Aster:   {corr(hl, as_):.3f}")
print(f"Correlation HL vs KuCoin:  {corr(hl, kc):.3f}")
print(f"Correlation Aster vs KuCoin: {corr(as_, kc):.3f}")
print("\nIf correlation > 0.7: M31 is the SAME edge across exchanges (high concentration risk).")
print("If correlation < 0.3: M31 is genuinely diverse (three independent edges).")
