"""Full Audit Runner"""
import sys, os, json
sys.path.append(os.getcwd())
from research_lab.audit_core import (trade_unit_stats, portfolio_daily_returns,
                                      calc_sharpe, deflated_sharpe)

SYMBOLS = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

def main():
    print("═" * 68)
    print("  FULL AUDIT — Trade Unit, Sharpe, Aster, DSR, Fee Stress")
    print("═" * 68 + "\n")

    print("## 1. Trade Unit Recalculation (P0-A2)")
    print(f"  {'Exchange':<12} | {'Raw n':>8} | {'Days':>5} | {'Syms':>4} | {'Inflation':>9}")
    print("  " + "─" * 60)
    tu = {}
    for ex, syms in SYMBOLS.items():
        s = trade_unit_stats(ex, syms)
        tu[ex] = s
        infl = s["raw"] // s["days"] if s["days"] > 0 else 0
        print(f"  {ex:<12} | {s['raw']:>8} | {s['days']:>5} | {s['symbols']:>4} | {infl:>9}x")
    print()

    print("## 2. Sharpe with Proper Annualization (P0-A3 base)")
    sr = {}
    for ex, syms in SYMBOLS.items():
        daily = portfolio_daily_returns(ex, syms, leverage=1.0)
        rets = [r for _, r in daily]
        s = calc_sharpe(rets)
        sr[ex] = s
        if s:
            print(f"  {ex:<12}: Sharpe={s['sharpe']:>6.3f} | AnnRet={s['ann_ret_pct']:>6.2f}% | Vol={s['ann_vol_pct']:>6.2f}% | N={s['n']}")
        else:
            print(f"  {ex:<12}: insufficient")
    print()

    print("## 3. Aster Sharpe Audit (Claimed=8.51)")
    if sr.get("aster"):
        recalc = sr["aster"]["sharpe"]
        ratio = recalc / 8.51
        verdict = "VALID" if ratio > 0.8 else "INFLATED" if ratio < 0.5 else "PARTIAL"
        print(f"  Claimed=8.51 | Reconstructed={recalc} | Ratio={ratio:.2f} | Verdict={verdict}")
    print()

    print("## 4. Deflated Sharpe (N_trials=54)")
    for ex, s in sr.items():
        if not s: continue
        d = deflated_sharpe(s["sharpe"], s["n"], 54)
        if d:
            print(f"  {ex:<12}: Raw={d['sharpe_raw']:>5.3f} | E_max={d['E_max_null']:>5.3f} | DSR={d['DSR']:>5.4f} → {d['verdict']}")
    print()

    print("## 5. Fee Stress (D-394b: proportional to trade frequency, NOT daily constant)")
    # D-394b: همان باگ fee_stress_fixed — اینجا هم اصلاح
    try:
        from research_lab.fee_stress_fixed import run_fee_stress, SYMBOLS as FS_SYMBOLS
        for ex, syms in FS_SYMBOLS.items():
            r = run_fee_stress(ex, syms)
            if "error" in r:
                print(f"  {ex:<12}: {r['error']} (n_days={r['n_days']})")
                continue
            base_sh = r['base_sharpe']
            for s in r['stress_levels']:
                if s['multiplier'] == 2.0:
                    delta = (s['sharpe'] - base_sh) / base_sh * 100 if base_sh else 0
                    print(f"  {ex:<12}: Base={base_sh:.3f} → 2xFee={s['sharpe']:.3f} (Δ={delta:+.1f}%) [{s['verdict']}]")
    except ImportError as e:
        print(f"  Fee stress unavailable: {e}")
    print()

    results = {"trade_units": tu, "sharpe": sr, "timestamp": "2026-10-31"}
    with open("audit_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("📄 audit_results.json saved")

if __name__ == "__main__":
    main()
