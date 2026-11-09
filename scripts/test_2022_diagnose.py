"""Diagnose DD 40.7% vs Kill Switch 15% + dual Survival Mode test."""
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

def main():
    raw = json.load(open("data/crypto_2022_bear.json"))
    btc = raw["BTC-USD"]
    dates = sorted(btc.keys())
    
    print("="*80)
    print(" DIAGNOSE: DD 40.7% vs Kill Switch 15%")
    print("="*80)
    
    # Scenario A: Kill Switch 15% (current)
    # Scenario B: Kill Switch 15% + Survival Mode dual (crypto vs currency)
    # In 2022, no Iran currency data. So we test: partial de-risking (50% to tether at trigger)
    
    for label, kill_thresh, de_risk_mode in [
        ("A: Kill Switch 15% (full stop)", 15, "full"),
        ("B: Kill Switch 15% (50% to tether)", 15, "half"),
        ("C: Kill Switch 20% (50% to tether)", 20, "half"),
        ("D: No Kill Switch", 999, "full"),
    ]:
        capital = 10000.0
        peak = 10000.0
        kill_triggered = False
        kill_date = None
        switches = 0
        cur_exposure = 1.0  # 1.0 = full BTC, 0.5 = half tether, 0.0 = full tether
        daily_rets = []
        max_dd_date = None
        max_dd_val = 0
        
        for i in range(50, len(dates)):
            d = dates[i]
            d_prev = dates[i-1]
            regime = detect_regime(btc, d, dates)
            if regime is None:
                daily_rets.append(0)
                continue
            
            # Target exposure based on regime
            if regime in ["BEAR", "CRASH"]:
                target_exposure = 0.0
            else:
                target_exposure = 1.0
            
            if target_exposure != cur_exposure:
                switches += 1
                cur_exposure = target_exposure
            
            # Daily return = exposure × BTC return
            btc_ret = (btc[d] / btc[d_prev] - 1) * 100
            day_ret = cur_exposure * btc_ret
            if target_exposure != cur_exposure:  # fee
                day_ret -= 0.05
            
            capital *= (1 + day_ret/100)
            if capital > peak: peak = capital
            dd = (peak - capital) / peak * 100
            
            if dd > max_dd_val:
                max_dd_val = dd
                max_dd_date = d
            
            # Kill Switch
            if dd > kill_thresh and not kill_triggered:
                kill_triggered = True
                kill_date = d
                if de_risk_mode == "full":
                    cur_exposure = 0.0
                else:  # half
                    cur_exposure = 0.5
            
            daily_rets.append(day_ret)
        
        total = (capital - 10000) / 100
        print(f"\n{label}")
        print(f"  Return:      {total:+.1f}%")
        print(f"  Max DD:      {max_dd_val:.1f}% (on {max_dd_date})")
        print(f"  Switches:    {switches}")
        print(f"  Kill:        {'TRIGGERED on ' + kill_date if kill_triggered else 'Not triggered'}")
        if kill_triggered:
            print(f"  DD at kill:  {max_dd_val:.1f}%")

if __name__ == "__main__":
    main()
