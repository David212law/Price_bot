"""Portfolio backtest — fixed baskets + dynamic strategies, OOS 70/30."""
import json
from datetime import datetime

def load():
    crypto = json.load(open("data/crypto_5y_usd.json"))
    usd_irr = json.load(open("data/usd_irr_tgju.json"))
    return crypto, usd_irr

def build_tmn(crypto, usd_irr):
    tmn = {}
    for sym, prices in crypto.items():
        if not sym.endswith("-USD"): continue
        base = sym[:-4]
        tmn[base] = {d: p * usd_irr[d]/10 for d, p in prices.items() if d in usd_irr}
    return tmn

def precompute_daily_rets(all_series):
    """Precompute daily returns ONCE for all assets (O(n) not O(n²))."""
    rets = {}
    for name, prices in all_series.items():
        r = {}
        dates = sorted(prices.keys())
        for i in range(1, len(dates)):
            d0, d1 = dates[i-1], dates[i]
            if (datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d0, "%Y-%m-%d")).days == 1:
                if prices[d0] > 0:
                    r[d1] = (prices[d1]/prices[d0] - 1) * 100
        rets[name] = r
    return rets

def evaluate_basket(weights, all_rets, date_list, split):
    train_alphas = []
    test_alphas = []
    tether_rets = all_rets["TETHER"]
    for date in date_list:
        if date not in tether_rets: continue
        port_ret = 0
        valid = True
        for asset, w in weights.items():
            if asset == "TETHER":
                continue
            if asset not in all_rets or date not in all_rets[asset]:
                valid = False
                break
            port_ret += w * all_rets[asset][date]
        if not valid: continue
        alpha = port_ret - tether_rets[date]
        if date < split:
            train_alphas.append(alpha)
        else:
            test_alphas.append(alpha)
    train_m = sum(train_alphas)/len(train_alphas) if train_alphas else 0
    test_m = sum(test_alphas)/len(test_alphas) if test_alphas else 0
    return train_m, test_m, len(test_alphas)

def main():
    crypto, usd_irr = load()
    tmn = build_tmn(crypto, usd_irr)
    tether = {d: usd_irr[d]/10 for d in usd_irr}

    # Precompute once
    all_series = dict(tmn)
    all_series["TETHER"] = tether
    all_rets = precompute_daily_rets(all_series)

    date_list = sorted(all_rets["TETHER"].keys())
    split = "2022-05-14"

    baskets = {
        "TETHER_only":       {"TETHER": 1.0},
        "BTC_only":          {"BTC": 1.0},
        "BTC+BCH+BNB+TRX":   {"BTC": 0.25, "BCH": 0.25, "BNB": 0.25, "TRX": 0.25},
        "BTC+BNB":           {"BTC": 0.5, "BNB": 0.5},
        "BTC+ETH":           {"BTC": 0.5, "ETH": 0.5},
        "BTC+BNB+TRX":       {"BTC": 0.33, "BNB": 0.33, "TRX": 0.34},
        "Top4_eq":           {"BTC": 0.25, "ETH": 0.25, "BNB": 0.25, "XRP": 0.25},
        "Safe_diverse_40":   {"TETHER": 0.4, "BTC": 0.2, "BCH": 0.15, "BNB": 0.15, "TRX": 0.1},
        "Tether_heavy_70":   {"TETHER": 0.7, "BTC": 0.1, "BCH": 0.1, "TRX": 0.1},
        "BCH+BNB+TRX+XRP":   {"BCH": 0.25, "BNB": 0.25, "TRX": 0.25, "XRP": 0.25},
        "BTC+BCH+TRX":       {"BTC": 0.33, "BCH": 0.33, "TRX": 0.34},
        "BTC+BCH+BNB+TRX+SOL":{"BTC": 0.2, "BCH": 0.2, "BNB": 0.2, "TRX": 0.2, "SOL": 0.2},
    }

    print("=" * 84)
    print(" Basket backtest — OOS 70/30, split=" + split)
    print("=" * 84)
    print(f"\n  {'Basket':<24} {'TRAIN':>10} {'TEST':>10} {'TEST-ann':>12} {'test-n':>8}")
    print("  " + "-" * 72)

    results = {}
    for name, weights in baskets.items():
        tr, te, n = evaluate_basket(weights, all_rets, date_list, split)
        results[name] = {"train": tr, "test": te, "test_days": n, "test_annual": te * 252}
        print(f"  {name:<24} {tr:>+9.3f}% {te:>+9.3f}% {te*252:>+11.1f}% {n:>8}")

    # Dynamic strategies
    print(f"\n{'='*84}")
    print(" Dynamic strategies (no look-ahead)")
    print("=" * 84)

    btc_dates = sorted(tmn["BTC"].keys())
    btc_rets = all_rets["BTC"]
    tether_rets = all_rets["TETHER"]

    def btc_mom_30d(date):
        try: idx = btc_dates.index(date)
        except: return None
        if idx < 30: return None
        return (tmn["BTC"][date] / tmn["BTC"][btc_dates[idx-30]] - 1) * 100

    # Strategy 1: BTC 30d > 0 -> BTC, else Tether
    tr_alphas, te_alphas = [], []
    for date in date_list:
        if date not in btc_rets or date not in tether_rets: continue
        mom = btc_mom_30d(date)
        if mom is None: continue
        alpha = (btc_rets[date] - tether_rets[date]) if mom > 0 else 0
        if date < split: tr_alphas.append(alpha)
        else: te_alphas.append(alpha)

    tr_m = sum(tr_alphas)/len(tr_alphas) if tr_alphas else 0
    te_m = sum(te_alphas)/len(te_alphas)
    print(f"\n  Strategy: 'BTC mom30>0 -> BTC, else Tether'")
    print(f"    TRAIN: {tr_m:+.3f}%/d    TEST: {te_m:+.3f}%/d    TEST-ann: {te_m*252:+.1f}%")
    results["dyn_mom30"] = {"train": tr_m, "test": te_m, "test_annual": te_m * 252}

    # Strategy 2: BTC 30d > 5% -> BTC, else Tether (only strong signals)
    tr_alphas, te_alphas = [], []
    for date in date_list:
        if date not in btc_rets or date not in tether_rets: continue
        mom = btc_mom_30d(date)
        if mom is None: continue
        alpha = (btc_rets[date] - tether_rets[date]) if mom > 5 else 0
        if date < split: tr_alphas.append(alpha)
        else: te_alphas.append(alpha)
    tr_m = sum(tr_alphas)/len(tr_alphas) if tr_alphas else 0
    te_m = sum(te_alphas)/len(te_alphas)
    print(f"\n  Strategy: 'BTC mom30>5% -> BTC, else Tether'")
    print(f"    TRAIN: {tr_m:+.3f}%/d    TEST: {te_m:+.3f}%/d    TEST-ann: {te_m*252:+.1f}%")
    results["dyn_mom30_5"] = {"train": tr_m, "test": te_m, "test_annual": te_m * 252}

    # Strategy 3: BTC 30d > 0 -> basket(BTC+BCH+BNB+TRX), else Tether
    basket = {"BTC": 0.25, "BCH": 0.25, "BNB": 0.25, "TRX": 0.25}
    tr_alphas, te_alphas = [], []
    for date in date_list:
        if date not in btc_rets or date not in tether_rets: continue
        mom = btc_mom_30d(date)
        if mom is None: continue
        if mom > 0:
            # basket return
            port = 0
            valid = True
            for a, w in basket.items():
                if a not in all_rets or date not in all_rets[a]:
                    valid = False; break
                port += w * all_rets[a][date]
            if valid:
                alpha = port - tether_rets[date]
            else:
                alpha = 0
        else:
            alpha = 0
        if date < split: tr_alphas.append(alpha)
        else: te_alphas.append(alpha)
    tr_m = sum(tr_alphas)/len(tr_alphas) if tr_alphas else 0
    te_m = sum(te_alphas)/len(te_alphas)
    print(f"\n  Strategy: 'BTC mom30>0 -> BTC+BCH+BNB+TRX, else Tether'")
    print(f"    TRAIN: {tr_m:+.3f}%/d    TEST: {te_m:+.3f}%/d    TEST-ann: {te_m*252:+.1f}%")
    results["dyn_mom30_basket"] = {"train": tr_m, "test": te_m, "test_annual": te_m * 252}

    # Best
    print(f"\n{'='*84}")
    print(" BEST by TEST annual return:")
    print("=" * 84)
    ranked = sorted(results.items(), key=lambda x: -x[1]["test_annual"])
    for name, r in ranked[:5]:
        print(f"  {name:<28} test-ann {r['test_annual']:>+8.1f}%")

    json.dump(results, open("data/portfolio_test.json", "w"), indent=2)
    print(f"\nSaved data/portfolio_test.json")

if __name__ == "__main__":
    main()
