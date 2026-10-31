"""Corrected Fee Stress Test - models actual trading frequency"""
import sys, os, json, math
sys.path.append(os.getcwd())
from research_lab.audit_core import (
    load_funding, portfolio_daily_returns, calc_sharpe
)

SYMBOLS = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

# M31 logic parameters (from m11 allocator)
SMA_PERIOD = 12
ENTRY_THR = 0.00005
EXIT_THR = 0.00001
COOLDOWN_HOURS = 24

def simulate_m31_trades(rates):
    """Count actual round trips using real M31 logic"""
    hist = []
    in_pos = False
    last_exit = 0
    n_trades = 0
    
    for r in rates:
        hist.append(r["rate"])
        if len(hist) > SMA_PERIOD: hist.pop(0)
        if not hist: continue
        avg = sum(hist) / len(hist)
        
        if in_pos:
            if avg < EXIT_THR:
                in_pos = False
                last_exit = r["t"]
                n_trades += 1
        else:
            hours_since = (r["t"] - last_exit) / (3600 * 1000)
            if avg > ENTRY_THR and r["rate"] > 0 and hours_since >= COOLDOWN_HOURS:
                in_pos = True
    return n_trades

def count_trades(exchange, symbols):
    total = 0
    per_sym = {}
    for sym in symbols:
        rates = load_funding(exchange, sym)
        t = simulate_m31_trades(rates) if rates else 0
        total += t
        per_sym[sym] = t
    return total, per_sym

def run_fee_stress(exchange, symbols, stress_multipliers=[1.5, 2.0, 3.0]):
    """Corrected Fee Stress: proportional to actual trade frequency"""
    
    daily = portfolio_daily_returns(exchange, symbols)
    base_rets = [r for _, r in daily]
    n_days = len(base_rets)
    
    if n_days < 30:
        return {"error": "insufficient days", "n_days": n_days}
    
    # Count actual trades
    n_trades, per_sym = count_trades(exchange, symbols)
    
    # M31 position sizing: M31_ALLOC / n_symbols per trade
    # Default M31_ALLOC ~0.70, 6 symbols => ~11.67% per trade
    M31_ALLOC = 0.70
    per_symbol_pct = M31_ALLOC / len(symbols)
    
    # Fee per round trip (maker + taker, both sides)
    # HL: maker 0.015%, taker 0.045% (approx) → 0.12% per round trip
    # Aster/KuCoin: use 0.08% per round trip as base
    FEE_PER_RT_BASE = 0.0008  # 0.08% total (both sides)
    
    results = {
        "exchange": exchange,
        "n_days": n_days,
        "n_trades": n_trades,
        "per_sym_trades": per_sym,
        "per_symbol_pct": round(per_symbol_pct*100, 2),
        "base_sharpe": calc_sharpe(base_rets)["sharpe"],
        "stress_levels": []
    }
    
    for mult in stress_multipliers:
        stressed_fee_rt = FEE_PER_RT_BASE * mult
        additional_fee_rt = stressed_fee_rt - FEE_PER_RT_BASE
        
        # Total additional drag (as % of capital, over entire period)
        total_drag = n_trades * additional_fee_rt * per_symbol_pct
        daily_drag = total_drag / n_days if n_days > 0 else 0
        
        stressed = [r - daily_drag for r in base_rets]
        s_stats = calc_sharpe(stressed)
        
        results["stress_levels"].append({
            "multiplier": mult,
            "sharpe": s_stats["sharpe"] if s_stats else None,
            "ann_ret_pct": s_stats["ann_ret_pct"] if s_stats else None,
            "daily_drag_pct": round(daily_drag * 100, 4),
            "annual_drag_pct": round(daily_drag * 365 * 100, 2),
            "verdict": "PASS" if (s_stats and s_stats["sharpe"] > 0.5) else "FAIL"
        })
    
    return results

def main():
    print("═" * 72)
    print("  CORRECTED FEE STRESS TEST")
    print("  Method: proportional to actual trade frequency")
    print("═" * 72 + "\n")
    
    for ex, syms in SYMBOLS.items():
        print(f"═══ {ex.upper()} ═══")
        r = run_fee_stress(ex, syms)
        
        if "error" in r:
            print(f"  ⚠️ {r['error']} (n_days={r['n_days']})\n")
            continue
        
        print(f"  Trades (M31 logic): {r['n_trades']} over {r['n_days']} days")
        print(f"  Per-symbol trade count: {r['per_sym_trades']}")
        print(f"  Per-symbol allocation: {r['per_symbol_pct']}%")
        print(f"  Base Sharpe (no fee stress): {r['base_sharpe']}")
        print()
        print(f"  {'Fee×':>5} | {'Sharpe':>8} | {'AnnRet':>8} | {'DailyDrag':>10} | {'AnnDrag':>8} | {'Verdict':>7}")
        print("  " + "─" * 65)
        for s in r["stress_levels"]:
            print(f"  {s['multiplier']:>5} | {s['sharpe']:>8.3f} | {s['ann_ret_pct']:>7.2f}% | {s['daily_drag_pct']:>9.4f}% | {s['annual_drag_pct']:>7.2f}% | {s['verdict']:>7}")
        print()
    
    # Save
    all_results = {ex: run_fee_stress(ex, syms) for ex, syms in SYMBOLS.items()}
    with open("fee_stress_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("📄 fee_stress_results.json saved")

if __name__ == "__main__":
    main()
