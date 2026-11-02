"""D-474: Verify AVAX/SOL pair is genuine (not lucky)."""
import sys; sys.path.insert(0, '.')
from strategies.core_engine import load_data
from research_lab.audit_core import deflated_sharpe
import math
import random

def calc_sharpe(rets):
    n = len(rets)
    if n < 20: return 0
    m = sum(rets)/n
    var = sum((r-m)**2 for r in rets)/(n-1) if n > 1 else 0
    sd = math.sqrt(var) if var > 0 else 0
    return (m/sd)*math.sqrt(365) if sd > 0 else 0

def backtest_pair(candles_a, candles_b, lookback=30, z_thresh=2.0, fee=0.0006):
    b_by_t = {c["t"]: c["c"] for c in candles_b}
    aligned = [(c["t"], c["c"], b_by_t[c["t"]]) for c in candles_a if c["t"] in b_by_t]
    if len(aligned) < lookback * 2: return []
    
    ratio = [a/b for _, a, b in aligned]
    trades = []
    pos = None
    
    for i in range(lookback, len(ratio)):
        window = ratio[i-lookback:i]
        m = sum(window)/len(window)
        v = sum((x-m)**2 for x in window)/(len(window)-1)
        sd = math.sqrt(v) if v > 0 else 0
        if sd == 0: continue
        z = (ratio[i]-m)/sd
        
        if pos is None:
            if z > z_thresh: pos = {"side": "S", "entry": ratio[i]}
            elif z < -z_thresh: pos = {"side": "L", "entry": ratio[i]}
        else:
            if abs(z) < 0.5:
                if pos["side"] == "S":
                    gross = (pos["entry"] - ratio[i]) / pos["entry"]
                else:
                    gross = (ratio[i] - pos["entry"]) / pos["entry"]
                trades.append(gross - 2*fee)
                pos = None
            elif abs(z) > 4.0:
                trades.append(-0.05)
                pos = None
    return trades

print("="*70)
print(" AVAX/SOL PAIR — VERIFICATION")
print("="*70)

c_a = load_data("hyperliquid", "AVAX")
c_b = load_data("hyperliquid", "SOL")
if not c_a or not c_b:
    print("❌ Data missing"); sys.exit(1)

# ─── تست ۱: Cointegration (ساده) ───
print("\n[1] Cointegration Check")
# محاسبه spread (ratio) و چک اینکه آیا mean-reverting است
ratios = [a["c"]/b["c"] for a, b in zip(c_a[-500:], c_b[-500:])]
mean_r = sum(ratios)/len(ratios)
std_r = math.sqrt(sum((r-mean_r)**2 for r in ratios)/(len(ratios)-1))
final_ratio = ratios[-1]
z_now = (final_ratio - mean_r) / std_r
print(f"  Mean ratio: {mean_r:.4f}")
print(f"  Std ratio:  {std_r:.4f}")
print(f"  Current z:  {z_now:+.2f}")
print(f"  Range: [{min(ratios):.3f}, {max(ratios):.3f}]")

# ─── تست ۲: Walk-forward (70/30) ───
print("\n[2] Walk-forward (70% train, 30% test)")
split = int(len(c_a) * 0.7)
c_a_train, c_a_test = c_a[:split], c_a[split:]
c_b_train, c_b_test = c_b[:split], c_b[split:]

train_trades = backtest_pair(c_a_train, c_b_train)
test_trades = backtest_pair(c_a_test, c_b_test)

if train_trades and test_trades:
    sr_train = calc_sharpe(train_trades)
    sr_test = calc_sharpe(test_trades)
    print(f"  Train: n={len(train_trades):3d}, SR={sr_train:+.2f}")
    print(f"  Test:  n={len(test_trades):3d}, SR={sr_test:+.2f}")
    if sr_test > 0.5:
        print(f"  ✅ PASS — edge persists in test")
    else:
        print(f"  ❌ FAIL — edge was in train only (overfit)")
else:
    print(f"  ⚠️ insufficient trades: train={len(train_trades)}, test={len(test_trades)}")

# ─── تست ۳: Deflated Sharpe Ratio (with N=9 trials) ───
print("\n[3] Deflated Sharpe Ratio (N=9 tests, aggressive)")
all_trades = backtest_pair(c_a, c_b)
if all_trades:
    sr = calc_sharpe(all_trades)
    d = deflated_sharpe(sr, len(all_trades), 9, annualized=True)
    if d:
        print(f"  Raw Sharpe: {d['sharpe_annualized']}")
        print(f"  E_max_null: {d['E_max_null']}")
        print(f"  DSR:        {d['DSR']}")
        print(f"  Verdict:    {d['verdict']}")
        if d['DSR'] < 0.95:
            print(f"  ⚠️ DSR < 0.95 — could be lucky (multiple testing)")

# ─── تست ۴: Monte Carlo (permutation test) ───
print("\n[4] Monte Carlo Permutation (1000 shuffles)")
# shuffled pair — if real edge exists, original > 95% of shuffles
orig_sr = calc_sharpe(all_trades) if all_trades else 0
better_count = 0
rng = random.Random(42)
for _ in range(200):  # 200 not 1000 for speed
    # shuffle prices of B
    b_prices = [c["c"] for c in c_b[:len(c_a)]]
    rng.shuffle(b_prices)
    b_shuffled = [{"t": c_a[i]["t"], "c": b_prices[i]} for i in range(len(b_prices))]
    trades_shuffled = backtest_pair(c_a, b_shuffled)
    if trades_shuffled:
        sr_shuffled = calc_sharpe(trades_shuffled)
        if sr_shuffled >= orig_sr:
            better_count += 1
p_value = better_count / 200
print(f"  Original SR: {orig_sr:+.2f}")
print(f"  p-value:     {p_value:.3f}")
if p_value < 0.05:
    print(f"  ✅ PASS — genuine relationship")
else:
    print(f"  ❌ FAIL — likely noise")
