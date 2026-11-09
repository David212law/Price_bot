"""2022 test with REAL regime detector (Vol+Trend) + Kill Switch."""
import json

def detect_regime(btc, date, all_dates):
    """Vol+Trend regime detector (same as production)."""
    try:
        idx = all_dates.index(date)
    except ValueError:
        return None
    if idx < 50: return None
    # Vol: 14-day std of returns
    rets_14 = []
    for j in range(max(1, idx-14), idx+1):
        if all_dates[j-1] in btc and all_dates[j] in btc:
            rets_14.append((btc[all_dates[j]] / btc[all_dates[j-1]] - 1) * 100)
    if len(rets_14) < 5: return None
    m = sum(rets_14) / len(rets_14)
    # Raw daily std (not annualized), in percent
    vol = (sum((r - m)**2 for r in rets_14) / len(rets_14)) ** 0.5
    # MA50
    ma50_vals = [btc[d] for d in all_dates[max(0, idx-49):idx+1] if d in btc]
    if len(ma50_vals) < 40: return None
    ma50 = sum(ma50_vals) / len(ma50_vals)
    current = btc[date]
    above_ma50 = current > ma50
    # Classification — based on daily std (typical range 2-6%)
    if vol > 5.0: return "CRASH"          # Extreme: daily std > 5%
    if not above_ma50 and vol > 3.0: return "BEAR"   # Below MA50 + high vol
    if not above_ma50: return "FLAT"      # Below MA50, calm
    if vol > 3.0: return "BULL"           # Above MA50, high vol
    return "BULL_STRONG"                  # Above MA50, calm

def main():
    print("="*80)
    print(" 2022 BEAR TEST — Vol+Trend Regime + Kill Switch")
    print("="*80)
    
    raw = json.load(open("data/crypto_2022_bear.json"))
    btc = raw.get("BTC-USD", {})
    dates = sorted(btc.keys())
    print(f"\nData: {len(dates)} days")
    
    btc_ret = (btc[dates[-1]] / btc[dates[0]] - 1) * 100
    print(f"BTC 2022 return: {btc_ret:+.1f}%")
    
    for kill_threshold in [15, 20, 25, 30]:
        capital = 10000.0
        peak = 10000.0
        kill_triggered = False
        kill_date = None
        switches = 0
        cur = "TETHER"  # Start conservative
        daily_rets = []
        regime_counts = {}
        last_target = "TETHER"
        
        for i in range(50, len(dates)):
            d = dates[i]
            d_prev = dates[i-1]
            regime = detect_regime(btc, d, dates)
            if regime is None:
                daily_rets.append(0)
                continue
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            # Survival Mode: BEAR/CRASH → tether
            target = "TETHER" if regime in ["BEAR", "CRASH"] else "BTC"
            
            # Daily return based on CURRENT holding
            if cur == "TETHER":
                day_ret = 0.0
            else:
                day_ret = (btc[d] / btc[d_prev] - 1) * 100
            
            # Switch (fee only if target changed)
            if target != cur:
                day_ret -= 0.05
                switches += 1
                cur = target
            
            capital *= (1 + day_ret/100)
            if capital > peak: peak = capital
            dd = (peak - capital) / peak * 100
            
            # Kill Switch
            if dd > kill_threshold and not kill_triggered:
                kill_triggered = True
                kill_date = d
                cur = "TETHER"
            
            daily_rets.append(day_ret)
            last_target = target
        
        total = (capital - 10000) / 100
        eq_peak_dd = 0
        eq = 10000.0
        peak2 = 10000.0
        for r in daily_rets:
            eq *= (1 + r/100)
            if eq > peak2: peak2 = eq
            eq_peak_dd = max(eq_peak_dd, (peak2 - eq) / peak2 * 100)
        
        mean = sum(daily_rets) / len(daily_rets)
        var = sum((r - mean)**2 for r in daily_rets) / len(daily_rets)
        std = var ** 0.5
        sharpe = (mean / std) * (365 ** 0.5) if std > 0 else 0
        
        print(f"\n  Kill Switch = {kill_threshold}%:")
        print(f"    Return:      {total:+.1f}%")
        print(f"    Max DD:      {eq_peak_dd:.1f}%")
        print(f"    Sharpe:      {sharpe:.2f}")
        print(f"    Switches:    {switches}")
        print(f"    Kill:        {'TRIGGERED on ' + kill_date if kill_triggered else 'Not triggered'}")
        print(f"    Regime counts: {regime_counts}")
    
    print(f"\n{'='*80}")
    print(f" B&H BTC benchmark: {btc_ret:+.1f}% (DD 66.7%)")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
