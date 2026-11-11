"""Simple 2022 test: Survival Mode + Kill Switch — pure Python."""
import json

def main():
    print("="*80)
    print(" 2022 BEAR TEST — SIMPLE & DIRECT")
    print("="*80)
    
    raw = json.load(open("data/crypto_2022_bear.json"))
    btc = raw.get("BTC-USD", {})
    dates = sorted(btc.keys())
    print(f"\nData: {len(dates)} days ({dates[0]} → {dates[-1]})")
    
    # BTC return in 2022
    btc_ret = (btc[dates[-1]] / btc[dates[0]] - 1) * 100
    print(f"BTC 2022 return: {btc_ret:+.1f}%")
    
    # Simple regime: 30-day momentum (positive = BULL, negative = BEAR)
    # If 30d return < -10% = BEAR/CRASH (survival)
    # Else = BULL (hold BTC)
    
    for kill_threshold in [10, 15, 20, 25]:
        capital = 10000.0
        peak = 10000.0
        kill_triggered = False
        kill_date = None
        switches = 0
        cur = "BTC"
        daily_rets = []
        
        for i in range(30, len(dates)):
            d = dates[i]
            d_30 = dates[i-30]
            d_prev = dates[i-1]
            
            # 30-day momentum
            mom_30 = (btc[d] / btc[d_30] - 1) * 100
            
            # Simple rule: if 30d mom < -10%, go to tether (survival)
            target = "TETHER" if mom_30 < -10 else "BTC"
            
            # Daily return
            if cur == "TETHER":
                day_ret = 0.0
            else:
                day_ret = (btc[d] / btc[d_prev] - 1) * 100
            
            # Fee on switch
            if target != cur:
                day_ret -= 0.05
                switches += 1
                cur = target
            
            capital *= (1 + day_ret/100)
            if capital > peak: peak = capital
            dd = (peak - capital) / peak * 100
            
            # Kill switch
            if dd > kill_threshold and not kill_triggered:
                kill_triggered = True
                kill_date = d
                cur = "TETHER"  # Move to tether permanently
            
            daily_rets.append(day_ret)
        
        # Final stats
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
        print(f"    DD:          {eq_peak_dd:.1f}%")
        print(f"    Sharpe:      {sharpe:.2f}")
        print(f"    Switches:    {switches}")
        print(f"    Kill:        {'TRIGGERED on ' + kill_date if kill_triggered else 'Not triggered'}")
        print(f"    Final:       ${capital:.2f}")
    
    print(f"\n{'='*80}")
    print(f" B&H BTC benchmark: {btc_ret:+.1f}% (DD 66.7%)")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
