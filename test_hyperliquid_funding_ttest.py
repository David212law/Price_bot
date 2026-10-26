import json
import os
import math
import requests
import time
from datetime import datetime, timezone

# ─── Configuration (Same as V4) ───
INITIAL_CAPITAL = 10000.0
MAKER_FEE = 0.0002
LEVERAGE = 5
ENTRY_THRESHOLD = 0.0001
EXIT_THRESHOLD = 0.00001
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]
DAYS = 730

# ─── Data Fetching ───
def fetch_funding_history(symbol, days=DAYS):
    print(f"[{symbol}] Fetching funding history...")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    all_records = []
    current_end = end_ms
    
    while current_end > start_ms:
        current_start = max(start_ms, current_end - (30 * 24 * 3600 * 1000))
        payload = {"type": "fundingHistory", "coin": symbol, "startTime": current_start, "endTime": current_end}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if not data: break
                for rec in data:
                    all_records.append({"t": int(rec["time"]), "rate": float(rec["fundingRate"])})
                earliest = min(int(rec["time"]) for rec in data)
                current_end = earliest - 1
            elif r.status_code == 429:
                time.sleep(5)
                continue
        except:
            break
        time.sleep(1.5)
        
    unique = {r["t"]: r for r in all_records}
    return sorted(unique.values(), key=lambda x: x["t"])

# ─── Statistical Helpers ───
def norm_cdf(x):
    """Approximation of the Cumulative Distribution Function for Standard Normal"""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def one_sample_t_test(sample, mu=0):
    n = len(sample)
    if n < 30: 
        return 0.0, 1.0, 0.0, n # Not enough samples
    
    mean = sum(sample) / n
    variance = sum((x - mean) ** 2 for x in sample) / (n - 1)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0: 
        return 0.0, 1.0, mean, n
    
    # t-statistic
    t_stat = (mean - mu) / (std_dev / math.sqrt(n))
    
    # For n > 30, t-distribution approaches normal distribution
    # We want the right-tailed p-value (H1: mean > mu)
    p_value = 1.0 - norm_cdf(t_stat)
    
    return t_stat, p_value, mean, n

# ─── Backtest & Trade Extraction ───
def extract_trade_returns(data):
    capital_per_sym = INITIAL_CAPITAL / len(SYMBOLS)
    states = {sym: {"in_position": False, "funding": 0.0, "fees": 0.0} for sym in SYMBOLS}
    
    all_events = []
    for sym in SYMBOLS:
        for rec in data.get(sym, []):
            all_events.append({"t": rec["t"], "rate": rec["rate"], "symbol": sym})
    all_events.sort(key=lambda x: x["t"])
    
    trade_returns = [] # In USDT
    
    for event in all_events:
        sym = event["symbol"]
        rate = event["rate"]
        st = states[sym]
        
        if st["in_position"]:
            if rate > 0:
                st["funding"] += capital_per_sym * rate * LEVERAGE
            
            if rate < EXIT_THRESHOLD:
                st["fees"] += capital_per_sym * MAKER_FEE * 2 * LEVERAGE
                net_pnl = st["funding"] - st["fees"]
                trade_returns.append(net_pnl)
                st["in_position"] = False
                st["funding"] = 0.0
                st["fees"] = 0.0
        else:
            if rate > ENTRY_THRESHOLD:
                st["fees"] += capital_per_sym * MAKER_FEE * 2 * LEVERAGE
                st["in_position"] = True
                
    # Close remaining
    for sym in SYMBOLS:
        st = states[sym]
        if st["in_position"]:
            st["fees"] += capital_per_sym * MAKER_FEE * 2 * LEVERAGE
            net_pnl = st["funding"] - st["fees"]
            trade_returns.append(net_pnl)
            
    return trade_returns

def main():
    print(f"=== M31-V4 Statistical Validation (t-test) ===")
    print(f"Analyzing if Mean Trade Profit is > $0.00\n")
    
    data = {}
    for sym in SYMBOLS:
        records = fetch_funding_history(sym)
        if records: data[sym] = records
            
    print("\nExtracting Trade Returns...")
    trade_returns = extract_trade_returns(data)
    
    print(f"Total Trades Analyzed: {len(trade_returns)}")
    
    # Run t-test (H0: mean = 0, H1: mean > 0)
    t_stat, p_value, mean, n = one_sample_t_test(trade_returns, mu=0)
    
    print("\n=== STATISTICAL RESULTS ===")
    print(f"Mean Profit per Trade: {mean:.2f} USDT")
    print(f"t-statistic: {t_stat:.4f}")
    print(f"P-Value (One-Tailed): {p_value:.6f}")
    
    passed = (p_value < 0.05)
    print(f"\nFinal Status: {'✅ PASS' if passed else '❌ FAIL'}")
    if passed:
        print("Interpretation: We reject the null hypothesis. The mean profit per trade is statistically significantly greater than zero.")
    else:
        print("Interpretation: Fail to reject the null hypothesis. The profits might be due to chance.")

if __name__ == "__main__":
    main()
