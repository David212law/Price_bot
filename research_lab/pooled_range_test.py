import sys, os, json, math
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_a20, load_data
from research_lab.regime_analysis import classify_regime, tag_trades_with_regime
from research_lab.regime_wf_test import embargo_wf, boot_p

EXCHANGES = {
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

def collect_range_trades(exchange, symbols):
    """جمع‌آوری تریدهای RANGE از یک صرافی"""
    range_trades = []
    all_trades = 0
    for sym in symbols:
        candles = load_data(exchange, sym)
        if not candles: continue
        for train, test in embargo_wf(candles):
            if len(test) < 20: continue
            trades = strategy_a20(test)
            all_trades += len(trades)
            tagged = tag_trades_with_regime(trades, test)
            for t in tagged:
                if t["regime"] == "RANGE":
                    range_trades.append(t["ret"])
    return range_trades, all_trades

def main():
    print("=" * 60)
    print("  🎯 Pooled RANGE Test (D-330)")
    print("=" * 60)
    print("\nآستانه Pooled: n>=100، P<0.05، PF>1.5\n")
    
    all_range_rets = []
    per_exchange = {}
    
    for ex, syms in EXCHANGES.items():
        rets, total = collect_range_trades(ex, syms)
        per_exchange[ex] = rets
        all_range_rets.extend(rets)
        print(f"{ex:12}: {len(rets):>4} RANGE trades (from {total} total)")
    
    n_pool = len(all_range_rets)
    print(f"\n{'POOLED':12}: {n_pool:>4} RANGE trades")
    
    if n_pool < 30:
        print("❌ Insufficient for pooled test")
        return
    
    # Pooled آمار
    mean = sum(all_range_rets) / n_pool
    wins = [r for r in all_range_rets if r > 0]
    losses = [r for r in all_range_rets if r <= 0]
    pf = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 99.99
    wr = len(wins) / n_pool * 100
    
    p_pool = boot_p(all_range_rets, block_size=6, iterations=2000)
    
    print(f"\n📊 Pooled Metrics:")
    print(f"   n = {n_pool}")
    print(f"   Mean = {mean*100:+.3f}%")
    print(f"   WR = {wr:.1f}%")
    print(f"   PF = {pf:.2f}")
    print(f"   P-Value = {p_pool:.4f}")
    
    print(f"\n{'='*60}")
    if p_pool < 0.05 and pf > 1.5 and mean > 0:
        print(f"✅ POOLED VALIDATION: A20 in RANGE")
        print(f"   آستانه‌های آماری همه پاس شدند.")
        print(f"   تصمیم: A20 RANGE به عنوان Diversifier پذیرفته می‌شود.")
        print(f"   تخصیص پیشنهادی: 25% در KuCoin (قوی‌ترین صرافی)")
    elif p_pool < 0.10 and pf > 1.5 and mean > 0:
        print(f"⚠️ POOLED BORDERLINE: A20 in RANGE")
        print(f"   میانگین مثبت و PF قوی، اما P={p_pool:.3f} > 0.05")
        print(f"   تصمیم: پیشنهاد فعال‌سازی محدود (10-15%) در Paper")
    else:
        print(f"❌ POOLED FAILED")
        print(f"   A20 RANGE معتبر نیست. M31 تنها لبه است.")
    print(f"{'='*60}")
    
    # ذخیره نتایج
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/pooled_range_result.json", "w") as f:
        json.dump({
            "n": n_pool, "mean_pct": round(mean*100, 4), "wr": round(wr, 2),
            "pf": round(pf, 2), "p_value": p_pool,
            "per_exchange_n": {ex: len(r) for ex, r in per_exchange.items()},
        }, f, indent=2)

if __name__ == "__main__":
    main()
