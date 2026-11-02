"""D-484: Verify the kucoin/NEUTRAL combo is genuine (3 quick tests)."""
import sys; sys.path.insert(0, '.')
import json, math, random
from research_lab.audit_core import portfolio_daily_returns, calc_sharpe, deflated_sharpe
from research_lab.pooled_returns import pooled_returns

STATE_FILE = 'research_lab/logs/profiles/state.json'

def sharpe_ann(rets):
    n = len(rets)
    if n < 20: return 0
    m = sum(rets)/n
    var = sum((r-m)**2 for r in rets)/(n-1) if n>1 else 0
    sd = math.sqrt(var) if var > 0 else 0
    return (m/sd)*math.sqrt(365) if sd > 0 else 0

def compute_combo_daily(m31_rets, keltner_rets, dual_rets, weights):
    """Compute daily returns of the combo."""
    common = sorted(set(m31_rets) & set(keltner_rets) & set(dual_rets))
    if len(common) < 30: return {}
    out = {}
    for d in common:
        out[d] = (weights[0]*m31_rets[d] + weights[1]*keltner_rets[d] + weights[2]*dual_rets[d])
    return out

def main():
    state = json.load(open(STATE_FILE))
    
    print("="*72)
    print(" VERIFY kucoin/NEUTRAL COMBO (D-484)")
    print("="*72)
    
    # Load combo from pending
    pend = json.load(open('exchanges/pending_approvals.json'))
    combo = pend.get('kucoin/NEUTRAL', {}).get('combo', {})
    if not combo:
        print("❌ combo not in pending"); return
    
    # weights
    comp_map = {c['name']: c.get('weight', 0) for c in combo['components']}
    w_m31 = comp_map.get('M31', 0)
    w_kelt = comp_map.get('KELTNER_REV_ETHUSDTM', 0)
    w_dual = comp_map.get('DUAL_MOMENTUM_XBTUSDTM', 0)
    print(f"\nWeights: M31={w_m31:.4f}, Keltner={w_kelt:.4f}, Dual={w_dual:.4f}")
    
    # Load data
    syms = ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]
    m31 = dict(portfolio_daily_returns("kucoin", syms))
    keltner = pooled_returns("kucoin", "KELTNER_REV", state)
    dual = pooled_returns("kucoin", "DUAL_MOMENTUM", state)
    
    if not all([m31, keltner, dual]):
        print("❌ missing data"); return
    
    # ═══ Test 1: Combo Sharpe on full data ═══
    print("\n[1] Full-data combo Sharpe")
    combo_daily = compute_combo_daily(m31, keltner, dual, [w_m31, w_kelt, w_dual])
    if not combo_daily:
        print("  insufficient overlap"); return
    
    sr_combo = sharpe_ann(list(combo_daily.values()))
    m31_common = [m31[d] for d in combo_daily]
    sr_m31 = sharpe_ann(m31_common)
    print(f"  SR_combo = {sr_combo:.3f}  (expected 10-12)")
    print(f"  SR_M31   = {sr_m31:.3f}")
    print(f"  Improvement: {(sr_combo/sr_m31 - 1)*100:+.1f}%")
    
    # ═══ Test 2: Walk-forward (70/30) ═══
    print("\n[2] Walk-forward (70% train, 30% test)")
    dates = sorted(combo_daily.keys())
    split = int(len(dates) * 0.7)
    train_dates = dates[:split]
    test_dates = dates[split:]
    
    sr_train = sharpe_ann([combo_daily[d] for d in train_dates])
    sr_test = sharpe_ann([combo_daily[d] for d in test_dates])
    
    print(f"  Train: n={len(train_dates)}, SR={sr_train:.2f}")
    print(f"  Test:  n={len(test_dates)}, SR={sr_test:.2f}")
    if sr_test > 0.5 * sr_train:
        print(f"  ✅ PASS — edge persists")
    else:
        print(f"  ❌ FAIL — edge collapsed in test")
    
    # ═══ Test 3: Bootstrap CI on combo Sharpe ═══
    print("\n[3] Bootstrap CI (95%) on combo Sharpe")
    rets_list = [combo_daily[d] for d in dates]
    rng = random.Random(42)
    n = len(rets_list)
    sharpes = []
    for _ in range(500):
        sample = [rets_list[rng.randint(0, n-1)] for _ in range(n)]
        sharpes.append(sharpe_ann(sample))
    sharpes.sort()
    lo = sharpes[int(500*0.025)]
    hi = sharpes[int(500*0.975)]
    print(f"  CI: [{lo:.2f}, {hi:.2f}]")
    print(f"  Point: {sr_combo:.2f}")
    print(f"  {'✅ PASS (>0)' if lo > 0 else '❌ FAIL (crosses 0)'}")
    
    # ═══ Test 4: DSR with N=large (whole composer run tested many combos) ═══
    print("\n[4] Deflated Sharpe (N=200+ combos tried in this session)")
    N = 200  # conservative: composer tried many candidates
    d = deflated_sharpe(sr_combo, n, N, annualized=True)
    if d:
        print(f"  DSR = {d['DSR']:.4f} (N={N})")
        print(f"  Verdict: {d['verdict']}")
        if d['DSR'] < 0.95:
            print(f"  ⚠️ DSR < 0.95 — likely lucky among N tests")
    
    # ═══ Verdict ═══
    print("\n" + "="*72)
    print(" VERDICT")
    print("="*72)
    verdicts = []
    verdicts.append(("Walk-forward", sr_test > 0.5 * sr_train))
    verdicts.append(("Bootstrap CI", lo > 0))
    if d:
        verdicts.append(("DSR >= 0.90", d['DSR'] >= 0.90))
    
    for name, ok in verdicts:
        print(f"  {name}: {'✅' if ok else '❌'}")
    
    all_pass = all(v for _, v in verdicts)
    print()
    if all_pass:
        print("✅ ALL PASS — combo is genuine, ready for Paper")
    else:
        print("❌ SOME FAIL — combo should be rejected or held for Paper data")

if __name__ == "__main__":
    main()
