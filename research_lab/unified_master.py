"""
Unified Research Master — یکپارچه‌سازی کامل چرخه تشخیص + ترکیب
اجرا: هفتگی. خروجی: پرتفوی بهینه به‌روزرسانی‌شده.
"""
import os, sys, json, math, random
from datetime import datetime, timezone
from collections import defaultdict
sys.path.append(os.getcwd())

from strategies.core_engine import (
    strategy_m35, strategy_a20, strategy_m40, strategy_a8,
    strategy_m60_liq_reversal, strategy_m62_funding_momentum,
    load_data, calc_atr
)
from research_lab.bale_notifier import send_bale
from research_lab.regime_core import calc_adx, detect_regime, bootstrap_p, holm_bonferroni

# ─── Config ───
ALPHA = 0.05
MIN_N_PER_REGIME = 30
MIN_PF = 1.2
M31_BASE = 0.50       # M31 همیشه 50%
CASH_BASE = 0.20      # Cash همیشه 20%
DIRECTIONAL_BUDGET = 0.30  # 30% برای استراتژی‌های جهت‌دار

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}
STRATEGIES = {
    "A20": strategy_a20,
    "M40": strategy_m40,
    "M35": lambda c: strategy_m35(c, fast=50, slow=200),
    "A8": strategy_a8,
    "M60": strategy_m60_liq_reversal,
    "M62": strategy_m62_funding_momentum,
}

# ─── Regime Detection (از regime_core) ───
# ─── Strategy Testing in Regime ───
def collect_regime_trades(exchange, symbols, strat_func, target_regime):
    rets = []
    for sym in symbols:
        candles = load_data(exchange, sym)
        if not candles or len(candles) < 200: continue
        try: trades = strat_func(candles)
        except: continue
        # Build ts->idx for speed
        ts_idx = {c["t"]: i for i, c in enumerate(candles)}
        for t in trades:
            entry_t = t.get("t", 0)
            idx = ts_idx.get(entry_t, -1)
            if idx < 0: continue
            if detect_regime(candles, idx) == target_regime:
                rets.append(t["ret"])
    return rets

# ─── Statistics ───
def bootstrap_p(rets, iters=800):
    n = len(rets)
    if n < 15: return 1.0
    mean = sum(rets)/n
    if mean <= 0: return 1.0
    std = math.sqrt(sum((r-mean)**2 for r in rets)/(n-1))
    if std == 0: return 0.0
    rng = random.Random(42)
    better = 0
    for _ in range(iters):
        sample = [rng.gauss(0, std) for _ in range(n)]
        if sum(sample)/n >= mean: better += 1
    return better/iters

def holm(p_vals, alpha=ALPHA):
    n = len(p_vals)
    order = sorted(range(n), key=lambda i: p_vals[i])
    passed = [False]*n
    for k, idx in enumerate(order):
        if p_vals[idx] <= alpha/(n-k): passed[idx] = True
        else: break
    return passed

# ─── Portfolio ───
def build_portfolio(valid_strategies):
    """valid_strategies: dict {name: {"pf":..., "regime":...}}"""
    weights = {"M31": M31_BASE, "Cash": CASH_BASE}
    if not valid_strategies:
        weights["Cash"] = 1.0 - M31_BASE
        return weights
    # Inverse-PF weighting
    total_inv = sum(1/v["pf"] for v in valid_strategies.values())
    for name, v in valid_strategies.items():
        w = (1/v["pf"]) / total_inv * DIRECTIONAL_BUDGET
        weights[name] = round(w, 4)
    # Normalize
    total = sum(weights.values())
    weights = {k: round(v/total, 4) for k,v in weights.items()}
    return weights

# ─── Main Pipeline ───
def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"=== 🤖 Unified Research Master ({now}) ===\n")
    
    all_results = []
    for exchange, symbols in EXCHANGES.items():
        print(f"═══ {exchange.upper()} ═══")
        for strat_name, strat_func in STRATEGIES.items():
            for regime in ["TREND", "RANGE", "NEUTRAL"]:
                rets = collect_regime_trades(exchange, symbols, strat_func, regime)
                if len(rets) < MIN_N_PER_REGIME: continue
                mean = sum(rets)/len(rets)
                wins = [r for r in rets if r>0]; losses = [r for r in rets if r<=0]
                pf = abs(sum(wins)/sum(losses)) if losses and sum(losses)!=0 else 99.99
                p = bootstrap_p(rets)
                all_results.append({"exchange":exchange,"strategy":strat_name,"regime":regime,
                    "n":len(rets),"pf":round(pf,2),"mean_pct":round(mean*100,3),"p":round(p,4)})
                status = "🟢" if (p<0.05 and pf>MIN_PF and mean>0) else "⚠️" if (p<0.10 and pf>MIN_PF and mean>0) else "❌"
                print(f"  {status} {strat_name:5} | {regime:8} | n={len(rets):4} | PF={pf:5.2f} | mean={mean*100:+.3f}% | p={p:.4f}")
    
    if not all_results:
        print("\n❌ No valid results.")
        send_bale("🤖 Unified Master: No valid (strategy, regime) pairs found.")
        return
    
    # Holm correction
    p_vals = [r["p"] for r in all_results]
    passed = holm(p_vals)
    
    # Filter: passed AND pf>MIN_PF AND mean>0
    survivors = [r for i,r in enumerate(all_results) if passed[i] and r["pf"]>MIN_PF and r["mean_pct"]>0]
    
    print(f"\n═══ After Holm (α=0.05) ═══")
    for r in all_results:
        is_surv = r in survivors
        mark = "✅" if is_surv else "❌"
        print(f"  {mark} {r['exchange']:12} | {r['strategy']:5} in {r['regime']:8} | PF={r['pf']:.2f} | P={r['p']:.4f}")
    
    # Build per-exchange portfolios
    new_weights = {}
    print(f"\n═══ Portfolio Allocation ═══")
    for exchange in EXCHANGES.keys():
        ex_survivors = {r["strategy"]: r for r in survivors if r["exchange"]==exchange}
        weights = build_portfolio(ex_survivors)
        new_weights[exchange] = weights
        print(f"\n  {exchange.upper()}:")
        for name, w in sorted(weights.items(), key=lambda x: -x[1]):
            print(f"    {name:8}: {w*100:5.1f}%")
    
    # Save
    with open("exchanges/active_weights.json", "w") as f:
        json.dump(new_weights, f, indent=2)
    print(f"\n✅ active_weights.json updated ({len(survivors)} valid pairs)")
    
    # Report to Bale
    msg = f"🤖 **Unified Master** ({now})\n\n"
    msg += f"Valid pairs after Holm: {len(survivors)}\n"
    for exchange, weights in new_weights.items():
        msg += f"\n**{exchange.upper()}**\n"
        for name, w in sorted(weights.items(), key=lambda x:-x[1]):
            msg += f"  • {name}: {w*100:.1f}%\n"
    send_bale(msg)
    print("\n✅ Report sent to Bale")

if __name__ == "__main__":
    main()
