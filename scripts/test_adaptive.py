"""Adaptive mode: choose Defensive/Balanced/Aggressive based on regime."""

import json

def detect_regime(btc, date, all_dates):
    try: idx = all_dates.index(date)
    except ValueError: return None
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
    price = btc[date]
    above = price > ma50
    if vol > 5.0: return "CRASH"
    if not above and vol > 3.0: return "BEAR"
    if not above: return "FLAT"
    if vol > 3.0: return "BULL"
    return "BULL_STRONG"

def run_adaptive(btc, dates):
    """Adaptive: choose mode per regime."""
    capital = 10000.0
    peak = 10000.0
    exposure = 0.0
    switches = 0
    daily_rets = []
    regime_counts = {}
    mode_counts = {}
    
    for i in range(50, len(dates)):
        d = dates[i]
        d_prev = dates[i-1]
        regime = detect_regime(btc, d, dates)
        if regime is None:
            daily_rets.append(0)
            continue
        
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        # 30-day momentum for FLAT regime decision
        mom_30 = 0
        if i >= 30:
            d_30ago = dates[i-30]
            if d_30ago in btc and btc[d_30ago] > 0:
                mom_30 = (btc[d] / btc[d_30ago] - 1) * 100
        
        # ADAPTIVE: choose exposure based on regime + momentum
        if regime == "BULL_STRONG":
            target = 1.0   # Aggressive: full BTC
            mode = "AGGRESSIVE"
        elif regime == "BULL":
            target = 0.8   # Mostly BTC
            mode = "BULL-MILD"
        elif regime == "FLAT":
            # SMART: if 30d momentum negative -> treat as BEAR
            if mom_30 < -5:
                target = 0.3
                mode = "FLAT->BEAR"
            elif mom_30 > 5:
                target = 0.8
                mode = "FLAT->BULL"
            else:
                target = 0.5
                mode = "BALANCED"
        elif regime == "BEAR":
            target = 0.3   # Mostly tether
            mode = "BEAR-DEF"
        else:  # CRASH
            target = 0.0   # Full tether (Defensive)
            mode = "DEFENSIVE"
        
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        if target != exposure:
            switches += 1
            exposure = target
        
        btc_ret = (btc[d] / btc[d_prev] - 1) * 100
        day_ret = exposure * btc_ret
        if target != exposure:
            day_ret -= 0.05
        
        capital *= (1 + day_ret/100)
        if capital > peak: peak = capital
        daily_rets.append(day_ret)
    
    total = (capital - 10000) / 100
    eq = 10000.0; peak2 = 10000.0; max_dd = 0
    for r in daily_rets:
        eq *= (1 + r/100)
        if eq > peak2: peak2 = eq
        max_dd = max(max_dd, (peak2 - eq) / peak2 * 100)
    m = sum(daily_rets) / len(daily_rets)
    var = sum((r - m)**2 for r in daily_rets) / len(daily_rets)
    std = var ** 0.5
    sharpe = (m / std) * (365 ** 0.5) if std > 0 else 0
    return {"total": total, "dd": max_dd, "sharpe": sharpe, "switches": switches,
            "regime_counts": regime_counts, "mode_counts": mode_counts}

def main():
    print("="*80)
    print(" ADAPTIVE MODE — Choose exposure per regime")
    print("="*80)
    
    # 2022
    raw_2022 = json.load(open("data/crypto_2022_bear.json"))
    btc_2022 = raw_2022["BTC-USD"]
    dates_2022 = sorted(btc_2022.keys())
    r2022 = run_adaptive(btc_2022, dates_2022)
    btc_2022_ret = (btc_2022[dates_2022[-1]] / btc_2022[dates_2022[0]] - 1) * 100
    
    # 2023
    raw_5y = json.load(open("data/crypto_5y_usd.json"))
    btc_5y = raw_5y["BTC-USD"]
    dates_2023 = [d for d in sorted(btc_5y.keys()) if d.startswith("2023")]
    btc_2023 = {d: btc_5y[d] for d in dates_2023}
    r2023 = run_adaptive(btc_2023, dates_2023)
    btc_2023_ret = (btc_2023[dates_2023[-1]] / btc_2023[dates_2023[0]] - 1) * 100
    
    print(f"\n📊 2022 (BEAR): B&H = {btc_2022_ret:+.1f}%")
    print(f"  Adaptive: {r2022['total']:+.1f}% (DD {r2022['dd']:.1f}%, Sharpe {r2022['sharpe']:.2f}, {r2022['switches']} switches)")
    print(f"  Regimes: {r2022['regime_counts']}")
    print(f"  Modes:   {r2022['mode_counts']}")
    
    print(f"\n📊 2023 (BULL): B&H = {btc_2023_ret:+.1f}%")
    print(f"  Adaptive: {r2023['total']:+.1f}% (DD {r2023['dd']:.1f}%, Sharpe {r2023['sharpe']:.2f}, {r2023['switches']} switches)")
    print(f"  Regimes: {r2023['regime_counts']}")
    print(f"  Modes:   {r2023['mode_counts']}")
    
    print(f"\n{'='*80}")
    print(" COMPARISON WITH PREVIOUS MODES")
    print("="*80)
    print(f"  2022: Defensive +27.7%, Balanced -25.5%, Aggressive -55.4%, ADAPTIVE {r2022['total']:+.1f}%")
    print(f"  2023: Defensive +61.7%, Balanced +67.7%, Aggressive +73.7%, ADAPTIVE {r2023['total']:+.1f}%")

if __name__ == "__main__":
    main()
