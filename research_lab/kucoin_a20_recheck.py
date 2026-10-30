import sys, os
sys.path.append(os.getcwd())
from strategies.core_engine import strategy_a20, load_data, calculate_metrics

SYMBOLS = ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]

def test_split(label, split_fn):
    trades = []
    for sym in SYMBOLS:
        cd = load_data("kucoin", sym)
        if cd: trades.extend(strategy_a20(split_fn(cd)))
    m = calculate_metrics(trades)
    print(f"  {label}: PF={m.get('pf')} | n={m.get('n')} | WR={m.get('win_rate')}%")
    return m

print("=== KuCoin A20 Recheck (D-231) ===")
print("1) Full data:")
test_split("Full", lambda c: c)
print("2) OOS (last 20%):")
test_split("OOS", lambda c: c[int(len(c)*0.8):])
print("3) Train (first 60%):")
test_split("Train", lambda c: c[:int(len(c)*0.6)])
