"""Analyze multi-asset regime performance over 5 years (TMN pairs)."""
import json
from collections import Counter

def main():
    crypto = json.load(open("data/crypto_5y_usd.json"))
    usd_irr = json.load(open("data/usd_irr_tgju.json"))

    # Reconstruct TMN pairs (USD price * USD/IRR / 10)
    tmn = {}
    for sym, prices in crypto.items():
        if not sym.endswith("-USD"): continue
        base = sym[:-4]
        tmn[base] = {}
        for date, price in prices.items():
            if date in usd_irr:
                tmn[base][date] = price * (usd_irr[date] / 10)

    # USDT (Tether) in TMN = USD/IRR / 10
    tether = {d: usd_irr[d] / 10 for d in usd_irr}

    # Regime classification based on BTC-USD 30-day return
    btc = crypto["BTC-USD"]
    btc_dates = sorted(btc.keys())

    def get_regime(date):
        try:
            idx = btc_dates.index(date)
        except ValueError:
            return None
        if idx < 30: return None
        ret = (btc[date] / btc[btc_dates[idx-30]] - 1) * 100
        if ret > 15: return "BULL_STRONG"
        elif ret > 5: return "BULL"
        elif ret > -5: return "FLAT"
        elif ret > -15: return "BEAR"
        else: return "CRASH"

    regimes = {d: get_regime(d) for d in btc_dates}
    regimes = {d: r for d, r in regimes.items() if r}
    counts = Counter(regimes.values())
    total = sum(counts.values())
    print(f"Regime distribution ({total} days):")
    for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        c = counts.get(r, 0)
        print(f"  {r:<14} {c:>5} days ({c/total*100:>5.1f}%)")

    # Daily alpha vs Tether, per asset per regime
    result = {}
    for asset in tmn:
        if asset == "USDT": continue
        prices = tmn[asset]
        result[asset] = {}
        for regime in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
            dates = sorted([d for d, r in regimes.items() if r == regime
                            and d in prices and d in tether])
            if len(dates) < 5: continue
            alphas = []
            asset_rets = []
            for i in range(1, len(dates)):
                d0, d1 = dates[i-1], dates[i]
                if d0 in prices and d1 in prices:
                    a = (prices[d1] / prices[d0] - 1) * 100
                    t = (tether[d1] / tether[d0] - 1) * 100
                    asset_rets.append(a)
                    alphas.append(a - t)
            if not asset_rets: continue
            avg_a = sum(asset_rets) / len(asset_rets)
            avg_alpha = sum(alphas) / len(alphas)
            std_a = (sum((r - avg_a)**2 for r in asset_rets) / len(asset_rets))**0.5
            result[asset][regime] = {
                "days": len(asset_rets),
                "avg_daily": avg_a,
                "alpha_daily": avg_alpha,
                "daily_std": std_a,
            }

    # Table
    regimes_list = ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]
    print(f"\n{'='*82}")
    print(f" Daily alpha vs Tether by regime (asset minus tether, %/day)")
    print(f"{'='*82}")
    header = f"  {'Asset':<8} "
    for r in regimes_list:
        header += f"{r:<14} "
    print(header)
    print("  " + "-" * 78)
    for asset in sorted(result.keys()):
        line = f"  {asset:<8} "
        for r in regimes_list:
            if r in result[asset]:
                v = result[asset][r]["alpha_daily"]
                line += f"{v:>+8.3f}%/d    "
            else:
                line += f"    N/A        "
        print(line)

    # Best per regime
    print(f"\n{'='*82}")
    print(f" Best asset per regime (highest daily alpha)")
    print(f"{'='*82}")
    best_per_regime = {}
    for r in regimes_list:
        cands = [(a, result[a][r]["alpha_daily"]) for a in result if r in result[a]]
        if not cands: continue
        cands.sort(key=lambda x: -x[1])
        best_asset, best_alpha = cands[0]
        if best_alpha > 0:
            print(f"  {r:<14} -> {best_asset:<8} (alpha {best_alpha:+.3f}%/d, {result[best_asset][r]['days']} days)")
            best_per_regime[r] = best_asset
        else:
            print(f"  {r:<14} -> TETHER (all assets negative alpha)")
            best_per_regime[r] = "TETHER"

    # Save
    output = {
        "regime_distribution": dict(counts),
        "regime_total_days": total,
        "best_per_regime": best_per_regime,
        "asset_regime_performance": result,
    }
    with open("data/regime_analysis_5y.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved data/regime_analysis_5y.json")

if __name__ == "__main__":
    main()
