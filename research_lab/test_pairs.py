"""D-473: Standalone test for Pairs Trading (same exchange, two correlated assets)."""
import sys; sys.path.insert(0, '.')
from strategies.core_engine import load_data
import math

def calc_metrics(rets):
    if not rets: return None
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    if not losses: pf = 99.99 if wins else 0
    else: pf = sum(wins) / abs(sum(losses))
    n = len(rets)
    m = sum(rets) / n
    var = sum((r - m)**2 for r in rets) / (n - 1) if n > 1 else 0
    sd = math.sqrt(var)
    sharpe = (m / sd) * math.sqrt(365) if sd > 0 else 0
    total_ret = sum(rets)
    return {"n": n, "pf": round(pf, 2), "wr": round(len(wins)/n*100, 1),
            "sharpe": round(sharpe, 2), "tot_ret": round(total_ret*100, 2)}

def test_pair(exchange, sym_a, sym_b, lookback=30, z_thresh=2.0, fee_mult=1.0):
    c_a = load_data(exchange, sym_a)
    c_b = load_data(exchange, sym_b)
    
    if not c_a or not c_b:
        print(f"  {sym_a}/{sym_b}: missing data")
        return
        
    b_by_t = {c["t"]: c["c"] for c in c_b}
    aligned = [(c["t"], c["c"], b_by_t[c["t"]]) for c in c_a if c["t"] in b_by_t]
    
    if len(aligned) < lookback * 2:
        print(f"  {sym_a}/{sym_b}: not enough overlap")
        return

    ratio = [a / b for _, a, b in aligned]
    trades = []
    pos = None
    fee = 0.0006 * fee_mult
    
    for i in range(lookback, len(ratio)):
        window = ratio[i-lookback:i]
        m = sum(window) / len(window)
        v = sum((x - m)**2 for x in window) / (len(window) - 1) if len(window) > 1 else 0
        sd = math.sqrt(v) if v > 0 else 0
        if sd == 0: continue
        
        z = (ratio[i] - m) / sd
        
        if pos is None:
            if z > z_thresh:
                pos = {"side": "SHORT_A", "entry": ratio[i]}
            elif z < -z_thresh:
                pos = {"side": "LONG_A", "entry": ratio[i]}
        else:
            # خروج: بازگشت به میانگین
            if abs(z) < 0.5:
                if pos["side"] == "SHORT_A":
                    gross = (pos["entry"] - ratio[i]) / pos["entry"]
                else:
                    gross = (ratio[i] - pos["entry"]) / pos["entry"]
                trades.append(gross - (fee * 2))
                pos = None
            # Stop Loss (اگر از 4 انحراف معیار گذشت)
            elif abs(z) > 4.0:
                trades.append(-0.05) # 5% ضرر فرضی برای SL
                pos = None
                
    if not trades:
        print(f"  {sym_a:4s}/{sym_b:4s} on {exchange[:4]}: 0 trades")
        return
        
    m = calc_metrics(trades)
    print(f"  {sym_a:4s}/{sym_b:4s} on {exchange[:4]:4s} | n={m['n']:3d} | PF={m['pf']:5.2f} | WR={m['wr']:5.1f}% | Sharpe={m['sharpe']:6.2f} | TotRet={m['tot_ret']:+6.2f}%")

print("="*90)
print(" PAIRS TRADING TEST (Same Exchange)")
print(" Lookback: 30 | Z-threshold: 2.0 | Fee: 0.12%")
print("="*90)

# تست جفت ارزهای منطقی در Hyperliquid
print("\n─── HYPERLIQUID ───")
test_pair("hyperliquid", "ETH", "SOL")
test_pair("hyperliquid", "ETH", "BTC")
test_pair("hyperliquid", "SOL", "BTC")
test_pair("hyperliquid", "AVAX", "SOL")

# تست در Aster
print("\n─── ASTER ───")
test_pair("aster", "ETHUSDT", "SOLUSDT")
test_pair("aster", "ETHUSDT", "BTCUSDT")
test_pair("aster", "SOLUSDT", "BTCUSDT")

# تست در KuCoin
print("\n─── KUCOIN ───")
test_pair("kucoin", "ETHUSDTM", "SOLUSDTM")
test_pair("kucoin", "XBTUSDTM", "ETHUSDTM")
