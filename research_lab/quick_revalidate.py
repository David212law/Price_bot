"""
Quick Revalidation — فقط 5 ترکیب کلیدی برای تایید regime_core
"""
import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import (
    strategy_m62_funding_momentum, strategy_m40, strategy_a20,
    load_data
)
from research_lab.regime_core import detect_regime, calc_adx, bootstrap_p

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

def collect(ex, syms, func, regime_filter):
    """جمع‌آوری تریدهای یک استراتژی در یک رژیم خاص"""
    rets = []
    n_total = 0
    for sym in syms:
        candles = load_data(ex, sym)
        if not candles or len(candles) < 250: continue
        try: trades = func(candles)
        except: continue
        n_total += len(trades)
        ts_idx = {c["t"]: i for i, c in enumerate(candles)}
        for t in trades:
            idx = ts_idx.get(t.get("t", 0), -1)
            if idx < 60: continue
            if detect_regime(candles, idx) == regime_filter:
                rets.append(t["ret"])
    return rets, n_total

def test_pair(label, ex, syms, func, regime):
    rets, n_total = collect(ex, syms, func, regime)
    if len(rets) < 15:
        print(f"  {label:35} | n={len(rets):3} (insufficient)")
        return None
    pf_wins = [r for r in rets if r > 0]
    pf_losses = [r for r in rets if r <= 0]
    pf = abs(sum(pf_wins)/sum(pf_losses)) if pf_losses and sum(pf_losses) != 0 else 99.99
    mean = sum(rets)/len(rets)*100
    p = bootstrap_p(rets, iterations=500)
    status = "✅" if (p < 0.05 and pf > 1.2 and mean > 0) else "⚠️" if (p < 0.10 and pf > 1.2) else "❌"
    print(f"  {label:35} | n={len(rets):4} | PF={pf:5.2f} | mean={mean:+6.3f}% | P={p:.4f} | {status}")
    return {"label": label, "n": len(rets), "pf": round(pf,2), "p": round(p,4), "mean": round(mean,3)}

def main():
    print("=== 🔍 Quick Revalidation (5 critical pairs) ===\n")
    print("Tool: regime_core.py (Single Source of Truth)\n")
    print(f"  {'Pair':35} | {'n':>4} | {'PF':>5} | {'Mean':>8} | {'P':>6} | Status")
    print("  " + "─" * 75)
    
    results = []
    # M62 در TREND (سه صرافی)
    results.append(test_pair("M62-TREND on Hyperliquid", "hyperliquid", 
                             EXCHANGES["hyperliquid"], strategy_m62_funding_momentum, "TREND"))
    results.append(test_pair("M62-TREND on Aster", "aster", 
                             EXCHANGES["aster"], strategy_m62_funding_momentum, "TREND"))
    results.append(test_pair("M62-TREND on KuCoin", "kucoin", 
                             EXCHANGES["kucoin"], strategy_m62_funding_momentum, "TREND"))
    
    # M40 در RANGE (فقط HL)
    results.append(test_pair("M40-RANGE on Hyperliquid", "hyperliquid", 
                             EXCHANGES["hyperliquid"], strategy_m40, "RANGE"))
    
    # A20 در RANGE (KuCoin)
    results.append(test_pair("A20-RANGE on KuCoin", "kucoin", 
                             EXCHANGES["kucoin"], strategy_a20, "RANGE"))
    
    print("\n" + "═" * 75)
    print("📊 مقایسه با نتایج قبلی:")
    print("  قبلی: M62-TREND (HL/Aster/KuCoin) P<0.0001، M40-RANGE-HL P<0.0001، A20-RANGE-KuCoin P=0.10")
    valid = [r for r in results if r]
    print(f"  جدید: {len(valid)} از 5 ترکیب تست شد")
    for r in valid:
        print(f"    {r['label']}: P={r['p']}")

if __name__ == "__main__":
    main()
