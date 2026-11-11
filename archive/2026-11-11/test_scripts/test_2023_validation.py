"""Validate 2022 result by testing on 2023 data (bull market)."""
import json

def detect_regime(btc, date, all_dates):
    try:
        idx = all_dates.index(date)
    except ValueError:
        return None
    if idx < 50: return None
    rets_14 = []
    for j in range(max(1, idx-14), idx+1):
        if all_dates[j-1] in btc and all_dates[j] in btc:
            rets_14.append((btc[all_dates[j]] / btc[all_dates[j-1]] - 1) * 100)
    if len(rets_14) < 5: return None
    m = sum(rets_14) / len(rets_14)
    vol = (sum((r - m)**2 for r in rets_14) / len(rets_14)) ** 0.5
    ma50_vals = [btc[d] for d in all_dates[max(0, idx-49):idx+1] if d in btc]
    if len(ma50_vals) < 40: return None
    ma50 = sum(ma50_vals) / len(ma50_vals)
    current = btc[date]
    above_ma50 = current > ma50
    if vol > 5.0: return "CRASH"
    if not above_ma50 and vol > 3.0: return "BEAR"
    if not above_ma50: return "FLAT"
    if vol > 3.0: return "BULL"
    return "BULL_STRONG"

def run_test(btc, dates, label):
    capital = 10000.0
    peak = 10000.0
    cur_exposure = 0.0
    switches = 0
    daily_rets = []
    
    for i in range(50, len(dates)):
        d = dates[i]
        d_prev = dates[i-1]
        regime = detect_regime(btc, d, dates)
        if regime is None:
            daily_rets.append(0)
            continue
        target = 0.0 if regime in ["BEAR", "CRASH"] else 1.0
        if target != cur_exposure:
            switches += 1
            cur_exposure = target
        btc_ret = (btc[d] / btc[d_prev] - 1) * 100
        day_ret = cur_exposure * btc_ret
        if target != cur_exposure:  # fee (approximate)
            day_ret -= 0.05
        capital *= (1 + day_ret/100)
        if capital > peak: peak = capital
        daily_rets.append(day_ret)
    
    total = (capital - 10000) / 100
    eq_peak_dd = 0
    eq = 10000.0
    peak2 = 10000.0
    for r in daily_rets:
        eq *= (1 + r/100)
        if eq > peak2: peak2 = eq
        eq_peak_dd = max(eq_peak_dd, (peak2 - eq) / peak2 * 100)
    
    btc_total = (btc[dates[-1]] / btc[dates[0]] - 1) * 100
    print(f"\n{label}:")
    print(f"  Strategy: {total:+.1f}% (DD {eq_peak_dd:.1f}%)")
    print(f"  B&H BTC:  {btc_total:+.1f}%")
    print(f"  Switches: {switches}")
    print(f"  Difference: {total - btc_total:+.1f}%")

def main():
    print("="*80)
    print(" VALIDATION: Is +27.7% in 2022 real or lucky?")
    print("="*80)
    
    # 2022 data
    raw_2022 = json.load(open("data/crypto_2022_bear.json"))
    btc_2022 = raw_2022["BTC-USD"]
    dates_2022 = sorted(btc_2022.keys())
    run_test(btc_2022, dates_2022, "2022 (BEAR)")
    
    # Check if 2023 data exists
    import os
    if os.path.exists("data/crypto_5y_usd.json"):
        raw_5y = json.load(open("data/crypto_5y_usd.json"))
        btc_5y = raw_5y["BTC-USD"]
        # Filter to 2023
        dates_2023 = [d for d in sorted(btc_5y.keys()) if d.startswith("2023")]
        if len(dates_2023) > 100:
            btc_2023 = {d: btc_5y[d] for d in dates_2023}
            run_test(btc_2023, dates_2023, "2023 (BULL)")
        else:
            print("\n⚠️ 2023 data not available in 5y dataset")
    else:
        print("\n⚠️ crypto_5y_usd.json not found")

if __name__ == "__main__":
    main()
