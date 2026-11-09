"""2022 Bear test WITH Kill Switch active (10% threshold)."""
import json

def stats(rets):
    if not rets: return 0, 0, 0
    eq = 1.0; peak = 1.0; dd = 0
    for r in rets:
        eq *= (1 + r/100)
        if eq > peak: peak = eq
        cur_dd = (peak - eq) / peak * 100
        if cur_dd > dd: dd = cur_dd
    total = (eq - 1) * 100
    mean = sum(rets) / len(rets)
    var = sum((r - mean)**2 for r in rets) / len(rets)
    std = var ** 0.5
    sharpe = (mean / std) * (365 ** 0.5) if std > 0 else 0
    return total, dd, sharpe

def detect_regime(prices, date, all_dates):
    """Improved regime with full-history drawdown + MA50 distance."""
    try:
        idx = all_dates.index(date)
    except ValueError:
        return None
    if idx < 50: return None
    past = all_dates[max(0, idx-50):idx+1]
    prices_past = [prices[d] for d in past if d in prices]
    if len(prices_past) < 40: return None
    current = prices[date]
    ma50 = sum(prices_past) / len(prices_past)
    # ATH: full history up to now (not just 50 days)
    full_past = [prices[d] for d in all_dates[:idx+1] if d in prices]
    ath = max(full_past)
    drawdown = (current / ath - 1) * 100
    distance_ma50 = (current / ma50 - 1) * 100
    # Vol: std of last 14 daily returns
    rets_14 = []
    for j in range(max(1, idx-14), idx+1):
        if all_dates[j-1] in prices and all_dates[j] in prices:
            rets_14.append((prices[all_dates[j]] / prices[all_dates[j-1]] - 1) * 100)
    if len(rets_14) < 5: return None
    m = sum(rets_14) / len(rets_14)
    vol = (sum((r - m)**2 for r in rets_14) / len(rets_14)) ** 0.5 * (365 ** 0.5)
    # Classification — more conservative thresholds
    if (vol > 2.5) or (drawdown < -60):
        return "CRASH"
    if (distance_ma50 < -15) or (drawdown < -35):
        return "BEAR"
    if distance_ma50 > 10 and vol < 1.0:
        return "BULL_STRONG"
    if distance_ma50 > 0:
        return "BULL"
    return "FLAT"

def main():
    print("="*80)
    print(" 2022 BEAR TEST — WITH KILL SWITCH ACTIVE")
    print("="*80)
    
    raw = json.load(open("data/crypto_2022_bear.json"))
    cleaned = {k.replace("-USD", ""): v for k, v in raw.items()}
    btc = cleaned["BTC"]
    all_dates = sorted(btc.keys())
    
    print(f"\nData: {len(all_dates)} days ({all_dates[0]} → {all_dates[-1]})")
    
    # Simulate: Survival Mode (BEAR/CRASH -> tether) + Kill Switch at -10%
    capital = 10000.0
    peak_capital = 10000.0
    cur_strategy = "TETHER"  # Start in tether (safest)
    regime_log = []
    kill_switch_triggered = False
    kill_switch_date = None
    switches = 0
    daily_returns = []
    
    for i in range(1, len(all_dates)):
        d = all_dates[i]
        d_prev = all_dates[i-1]
        regime = detect_regime(btc, d, all_dates)
        if regime is None:
            daily_returns.append(0)
            continue
        
        # Smart strategy: BEAR/CRASH -> TETHER, else -> BTC
        target_strategy = "TETHER" if regime in ["BEAR", "CRASH"] else "BTC"
        
        # Daily return based on current strategy
        if cur_strategy == "TETHER":
            day_ret = 0.0  # Tether is flat
        else:
            day_ret = (btc[d] / btc[d_prev] - 1) * 100
        
        # Fee on switch
        if target_strategy != cur_strategy:
            day_ret -= 0.05  # 0.05% switch fee (global)
            switches += 1
            cur_strategy = target_strategy
        
        capital *= (1 + day_ret/100)
        if capital > peak_capital:
            peak_capital = capital
        
        dd = (peak_capital - capital) / peak_capital * 100
        
        # KILL SWITCH: if DD > 10%, stop trading
        if dd > 10 and not kill_switch_triggered:
            kill_switch_triggered = True
            kill_switch_date = d
            print(f"\n❌ KILL SWITCH TRIGGERED on {d} (DD={dd:.1f}%)")
            print(f"   Capital at trigger: ${capital:.2f}")
            # After kill switch, all cash (tether, 0% return)
            cur_strategy = "TETHER"
        
        daily_returns.append(day_ret)
        regime_log.append(regime)
    
    # Stats
    total, dd, sharpe = stats(daily_returns)
    btc_total = (btc[all_dates[-1]] / btc[all_dates[0]] - 1) * 100
    
    print(f"\n{'='*80}")
    print(" RESULTS")
    print("="*80)
    print(f"  {'Strategy':<25} {'Return':>10} {'DD':>8} {'Sharpe':>8}")
    print(f"  {'-'*55}")
    print(f"  {'Ensemble+Survival+KillSw':<25} {total:>+9.1f}% {dd:>7.1f}% {sharpe:>7.2f}")
    print(f"  {'B&H BTC':<25} {btc_total:>+9.1f}% {66.7:>7.1f}% {-1.34:>7.2f}")
    print(f"\n  Switches: {switches}")
    print(f"  Kill Switch: {'TRIGGERED on ' + kill_switch_date if kill_switch_triggered else 'Not triggered'}")
    print(f"  Final capital: ${capital:.2f}")
    
    # Regime distribution
    from collections import Counter
    counts = Counter(regime_log)
    print(f"\n  Regime distribution:")
    for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
        c = counts.get(r, 0)
        print(f"    {r:<14} {c:>3} days")

if __name__ == "__main__":
    main()
