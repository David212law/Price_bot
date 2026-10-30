import sys, os, json, math
sys.path.append(os.getcwd())

def extract_rates(records):
    """Parser هوشمند برای هر فرمت JSON"""
    rates = []
    if not records: return rates
    
    # اگر dict است، کلیدهای رایج را جستجو کن
    if isinstance(records, dict):
        for k in ["data", "results", "funding", "history"]:
            if k in records and isinstance(records[k], list):
                records = records[k]
                break
    
    if not isinstance(records, list): return rates
    
    for r in records:
        if not isinstance(r, dict): continue
        # کلیدهای احتمالی نرخ
        rate = None
        for key in ["fundingRate", "rate", "funding_rate", "value", "funding"]:
            if key in r:
                try: rate = float(r[key]); break
                except: pass
        # کلیدهای احتمالی زمان
        t = 0
        for key in ["time", "t", "fundingTime", "timestamp", "created_at"]:
            if key in r:
                try: t = int(r[key]); break
                except: pass
        if rate is not None and t > 0:
            rates.append({"t": t, "rate": rate})
    return rates

def one_sample_t_test(rates):
    n = len(rates)
    if n < 30: return 1.0, 0, 0
    mean = sum(r["rate"] for r in rates) / n
    if mean <= 0: return 1.0, mean, 0
    variance = sum((r["rate"] - mean)**2 for r in rates) / (n - 1)
    std = math.sqrt(variance)
    if std == 0: return 0.0, mean, 0
    t_stat = mean / (std / math.sqrt(n))
    # P-Value تقریبی برای t-test یک‌طرفه با درجه آزادی بالا (تقریب نرمال)
    # t=20 → P≈0, t=2 → P≈0.023, t=1 → P≈0.16
    if t_stat > 6: p_val = 0.0
    elif t_stat > 4: p_val = 0.00003
    elif t_stat > 3: p_val = 0.001
    elif t_stat > 2.5: p_val = 0.006
    elif t_stat > 2: p_val = 0.023
    elif t_stat > 1.5: p_val = 0.067
    elif t_stat > 1: p_val = 0.16
    else: p_val = 0.5
    return p_val, mean, t_stat

def test_m31(exchange, symbols):
    print(f"\n═══ M31 {exchange.upper()} ═══")
    all_rates = []
    for sym in symbols:
        if exchange == "kucoin":
            path = f"exchanges/kucoin/data/{sym}_funding.json"
        elif exchange == "aster":
            path = f"data/aster/{sym}_funding.json"
        else:
            path = f"data/hyperliquid/{sym}_funding.json"
        
        if not os.path.exists(path):
            print(f"  {sym}: ❌ file not found")
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            rates = extract_rates(data)
            if not rates:
                print(f"  {sym}: ⚠️ 0 records parsed")
                continue
            all_rates.extend(rates)
            mean_sym = sum(r["rate"] for r in rates) / len(rates) * 100
            print(f"  {sym}: {len(rates)} records, mean = {mean_sym:.4f}%")
        except Exception as e:
            print(f"  {sym}: ❌ {e}")
    
    if len(all_rates) < 30:
        return None
    
    mean_rate = sum(r["rate"] for r in all_rates) / len(all_rates)
    wr = sum(1 for r in all_rates if r["rate"] > 0) / len(all_rates) * 100
    p_val, _, t_stat = one_sample_t_test(all_rates)
    
    print(f"\n  Total: {len(all_rates)} | Mean: {mean_rate*100:.4f}% | WR: {wr:.1f}% | t={t_stat:.2f} | P={p_val:.4f}")
    status = "✅ VALID" if p_val < 0.05 and mean_rate > 0 else ("⚠️ WEAK" if p_val < 0.10 and mean_rate > 0 else "❌ INVALID")
    print(f"  Status: {status}")
    return {"exchange": exchange, "n": len(all_rates), "mean": mean_rate, "wr": wr, "p": p_val, "t": t_stat, "status": status}

def main():
    print("=== 💰 M31 Funding — Proper Test (H1: mean > 0, α=0.05) ===")
    SYMBOLS = {
        "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
        "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
        "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"]
    }
    results = {}
    for ex, syms in SYMBOLS.items():
        r = test_m31(ex, syms)
        if r: results[ex] = r
    
    print("\n" + "="*50 + "\n  📊 FINAL VERDICT\n" + "="*50)
    for ex, r in results.items():
        print(f"  {ex:12}: {r['status']:10} (n={r['n']}, P={r['p']:.4f}, WR={r['wr']:.1f}%)")

if __name__ == "__main__":
    main()
