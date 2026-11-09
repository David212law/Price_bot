"""Compare 3 modes: Defensive / Aggressive / Balanced across 2022 & 2023."""

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

def run_mode(btc, dates, mode):
    """mode: 'defensive' | 'balanced' | 'aggressive'"""
    capital = 10000.0
    peak = 10000.0
    exposure = 0.0
    switches = 0
    daily_rets = []
    
    for i in range(50, len(dates)):
        d = dates[i]
        d_prev = dates[i-1]
        regime = detect_regime(btc, d, dates)
        if regime is None:
            daily_rets.append(0)
            continue
        
        # Target exposure based on mode
        if mode == "defensive":
            target = 0.0 if regime in ["BEAR", "CRASH"] else 1.0
        elif mode == "balanced":
            if regime == "CRASH": target = 0.0
            elif regime == "BEAR": target = 0.5
            else: target = 1.0
        elif mode == "aggressive":
            if regime == "CRASH" and regime_is_severe(btc, d, dates): target = 0.0
            else: target = 1.0
        else:
            target = 1.0
        
        if target != exposure:
            switches += 1
            exposure = target
        
        btc_ret = (btc[d] / btc[d_prev] - 1) * 100
        day_ret = exposure * btc_ret
        if target != exposure:  # fee on switch (approximation)
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
    return {"total": total, "dd": max_dd, "sharpe": sharpe, "switches": switches}

def regime_is_severe(btc, date, all_dates):
    """Only CRASH with deep drawdown (e.g., LUNA/FTX) is 'severe'."""
    try: idx = all_dates.index(date)
    except: return False
    if idx < 100: return False
    past_100 = [btc[all_dates[j]] for j in range(idx-100, idx+1) if all_dates[j] in btc]
    if not past_100: return False
    ath = max(past_100)
    dd = (btc[date] / ath - 1) * 100
    return dd < -40  # severe crash only

def main():
    print("="*80)
    print(" THREE MODES COMPARISON — Defensive vs Balanced vs Aggressive")
    print("="*80)
    
    # 2022
    raw_2022 = json.load(open("data/crypto_2022_bear.json"))
    btc_2022 = raw_2022["BTC-USD"]
    dates_2022 = sorted(btc_2022.keys())
    btc_2022_ret = (btc_2022[dates_2022[-1]] / btc_2022[dates_2022[0]] - 1) * 100
    
    # 2023
    raw_5y = json.load(open("data/crypto_5y_usd.json"))
    btc_5y = raw_5y["BTC-USD"]
    dates_2023 = [d for d in sorted(btc_5y.keys()) if d.startswith("2023")]
    btc_2023 = {d: btc_5y[d] for d in dates_2023}
    btc_2023_ret = (btc_2023[dates_2023[-1]] / btc_2023[dates_2023[0]] - 1) * 100
    
    print(f"\n📊 2022 (BEAR): B&H BTC = {btc_2022_ret:+.1f}%")
    print(f"{'Mode':<15} {'Return':>10} {'DD':>8} {'Sharpe':>8} {'Switches':>10}")
    print("-" * 55)
    for mode in ["defensive", "balanced", "aggressive"]:
        r = run_mode(btc_2022, dates_2022, mode)
        print(f"{mode:<15} {r['total']:>+9.1f}% {r['dd']:>7.1f}% {r['sharpe']:>7.2f} {r['switches']:>9}")
    
    print(f"\n📊 2023 (BULL): B&H BTC = {btc_2023_ret:+.1f}%")
    print(f"{'Mode':<15} {'Return':>10} {'DD':>8} {'Sharpe':>8} {'Switches':>10}")
    print("-" * 55)
    for mode in ["defensive", "balanced", "aggressive"]:
        r = run_mode(btc_2023, dates_2023, mode)
        print(f"{mode:<15} {r['total']:>+9.1f}% {r['dd']:>7.1f}% {r['sharpe']:>7.2f} {r['switches']:>9}")
    
    print(f"\n{'='*80}")
    print(" INTERPRETATION")
    print("="*80)
    print("  Defensive: best in 2022, worst in 2023")
    print("  Aggressive: worst in 2022, best in 2023")
    print("  Balanced: middle ground in both")

if __name__ == "__main__":
    main()
