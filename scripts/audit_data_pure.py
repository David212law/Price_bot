"""Data Quality Audit — Pure Python (no pandas needed)."""
import json
import math
from datetime import datetime

def load_market(name, path, suffix="TMN"):
    raw = json.load(open(path))
    if name == "GLOBAL":
        assets = {k[:-4]: v for k, v in raw.items() if k.endswith("-USD")}
    else:
        assets = {k[:-len(suffix)]: v for k, v in raw.items()
                  if k != f"USDT{suffix}" and k.endswith(suffix) and len(v) >= 100}
    return assets

def get_dates(assets, max_per_asset=None):
    """Get union of all dates, but capped to consistent range."""
    all_dates = set()
    for sym, prices in assets.items():
        all_dates.update(prices.keys())
    dates = sorted(all_dates)
    if max_per_asset:
        dates = dates[:max_per_asset]
    return dates

def get_price(asset_data, date):
    return asset_data.get(date)

def rolling_mean(prices_series, end_idx, window):
    """Mean of prices_series[end_idx-window+1 : end_idx+1]."""
    start = max(0, end_idx - window + 1)
    chunk = [p for p in prices_series[start:end_idx+1] if p is not None]
    return sum(chunk) / len(chunk) if chunk else None

def rolling_std(prices_series, end_idx, window):
    start = max(0, end_idx - window + 1)
    chunk = [p for p in prices_series[start:end_idx+1] if p is not None]
    if len(chunk) < 2: return None
    mean = sum(chunk) / len(chunk)
    var = sum((x - mean) ** 2 for x in chunk) / len(chunk)
    return math.sqrt(var) if var > 0 else None

def pct_change(prices_series):
    """Daily returns."""
    rets = []
    for i in range(1, len(prices_series)):
        p0, p1 = prices_series[i-1], prices_series[i]
        if p0 and p1 and p0 != 0:
            rets.append((p1 - p0) / p0)
        else:
            rets.append(None)
    rets = [None] + rets  # first is None
    return rets

def percentile(sorted_list, p):
    if not sorted_list: return 0
    idx = int(p * len(sorted_list))
    return sorted_list[min(idx, len(sorted_list)-1)]

def detect_regime_simple(price, ma50, ma200, vol_14):
    """5-regime detection (matches current researcher logic)."""
    if price is None or ma50 is None or ma200 is None or vol_14 is None:
        return "UNKNOWN"
    if price > ma50 and vol_14 < 0.4: return "BULL_STRONG"
    if price > ma50: return "BULL"
    if price <= ma50 and vol_14 < 0.4: return "FLAT"
    if price <= ma50 and 0.4 <= vol_14 < 0.7: return "BEAR"
    return "CRASH"

def audit_market(name, path, suffix="TMN"):
    print(f"\n{'='*70}")
    print(f" {name}")
    print(f"{'='*70}")
    
    assets = load_market(name, path, suffix)
    if not assets:
        print("  ❌ No assets loaded")
        return
    
    dates = get_dates(assets)
    print(f"[1] BASIC STATS")
    print(f"  Days: {len(dates)}")
    print(f"  Years: {len(dates)/365:.1f}")
    print(f"  Assets: {len(assets)}")
    print(f"  First date: {dates[0]}")
    print(f"  Last date:  {dates[-1]}")
    print(f"  {'⚠️ SHORT DATA' if len(dates) < 730 else '✅ ENOUGH'}")
    
    # ═══ BTC analysis (or first asset if no BTC) ═══
    btc_sym = "BTC" if "BTC" in assets else list(assets.keys())[0]
    print(f"\n[2] {btc_sym} PRICE ANALYSIS")
    btc_data = assets[btc_sym]
    btc_prices = [btc_data.get(d) for d in dates]
    valid_prices = [p for p in btc_prices if p]
    
    if not valid_prices:
        print(f"  ❌ No valid prices for {btc_sym}")
        return
    
    print(f"  Start: ${valid_prices[0]:,.0f}")
    print(f"  End:   ${valid_prices[-1]:,.0f}")
    print(f"  Min:   ${min(valid_prices):,.0f}")
    print(f"  Max:   ${max(valid_prices):,.0f}")
    print(f"  Range: {max(valid_prices)/min(valid_prices):.2f}x")
    print(f"  Total return: {(valid_prices[-1]/valid_prices[0] - 1)*100:+.1f}%")
    
    # ═══ Volatility analysis ═══
    rets = pct_change(btc_prices)
    vols = []
    for i in range(14, len(rets)):
        window_rets = [r for r in rets[i-13:i+1] if r is not None]
        if len(window_rets) < 2: continue
        mean = sum(window_rets) / len(window_rets)
        var = sum((r - mean) ** 2 for r in window_rets) / len(window_rets)
        vol_annual = math.sqrt(var) * math.sqrt(365)
        vols.append(vol_annual)
    
    if vols:
        vols_sorted = sorted(vols)
        print(f"\n[3] VOLATILITY RANGE (14d annualized)")
        print(f"  Min:  {min(vols):.2f}")
        print(f"  Max:  {max(vols):.2f}")
        print(f"  Mean: {sum(vols)/len(vols):.2f}")
        print(f"  P10:  {percentile(vols_sorted, 0.1):.2f}")
        print(f"  P90:  {percentile(vols_sorted, 0.9):.2f}")
        
        low = sum(1 for v in vols if v < 0.5)
        med = sum(1 for v in vols if 0.5 <= v < 1.5)
        high = sum(1 for v in vols if 1.5 <= v < 2.5)
        crash = sum(1 for v in vols if v >= 2.5)
        print(f"  Low vol (<0.5):    {low} days")
        print(f"  Med vol (0.5-1.5): {med} days")
        print(f"  High vol (1.5-2.5):{high} days")
        print(f"  Crash vol (≥2.5):  {crash} days")
        if crash < 10:
            print(f"  ⚠️ FEW CRASH DAYS — data may not represent bear markets")
        else:
            print(f"  ✅ Has crash days")
    
    # ═══ Trend range (MA50 vs MA200) ═══
    trends = []
    regimes = []
    for i in range(200, len(btc_prices)):
        if btc_prices[i] is None: continue
        ma50 = rolling_mean(btc_prices, i, 50)
        ma200 = rolling_mean(btc_prices, i, 200)
        if ma50 is None or ma200 is None or ma200 == 0: continue
        trend = (ma50 - ma200) / ma200
        trends.append(trend)
        
        # detect regime
        vol_here = None
        if i < len(vols):
            vol_here = vols[i - 14] if i >= 14 else None
        regime = detect_regime_simple(btc_prices[i], ma50, ma200, vol_here)
        regimes.append(regime)
    
    if trends:
        trends_sorted = sorted(trends)
        print(f"\n[4] TREND RANGE (MA50 vs MA200)")
        print(f"  Min: {min(trends)*100:.1f}%")
        print(f"  Max: {max(trends)*100:.1f}%")
        print(f"  Strong bear (<-15%):   {sum(1 for t in trends if t < -0.15)} days")
        print(f"  Mild bear (-15 to -5%):{sum(1 for t in trends if -0.15 <= t < -0.05)} days")
        print(f"  Range (-5 to +5%):     {sum(1 for t in trends if -0.05 <= t < 0.05)} days")
        print(f"  Mild bull (+5 to +15%):{sum(1 for t in trends if 0.05 <= t < 0.15)} days")
        print(f"  Strong bull (≥+15%):   {sum(1 for t in trends if t >= 0.15)} days")
    
    # ═══ Regime distribution ═══
    if regimes:
        from collections import Counter
        counts = Counter(regimes)
        total = sum(counts.values())
        print(f"\n[5] REGIME DISTRIBUTION ({total} days classified)")
        for r in ["BULL_STRONG", "BULL", "FLAT", "BEAR", "CRASH"]:
            c = counts.get(r, 0)
            pct = c / total * 100 if total > 0 else 0
            flag = "⚠️" if pct < 5 else "✅"
            print(f"  {flag} {r}: {c} days ({pct:.1f}%)")
        
        # ═══ Persistence ═══
        changes = sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i-1])
        avg_dur = total / max(1, changes)
        print(f"\n[6] REGIME PERSISTENCE")
        print(f"  Total changes: {changes}")
        print(f"  Avg duration: {avg_dur:.0f} days per regime")
        if changes > 100:
            print(f"  ✅ GOOD DIVERSITY")
        elif changes < 50:
            print(f"  ⚠️ TOO STICKY (few regime changes)")
        else:
            print(f"  ✅ OK")

# Run for all 3 markets
audit_market("TMN", "data/wallex_tmn_all.json", "TMN")
audit_market("USDT", "data/wallex_usdt_all.json", "USDT")
audit_market("GLOBAL", "data/crypto_5y_usd.json")
