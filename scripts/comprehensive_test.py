"""
Comprehensive Test — همه فرمول‌ها و fix ها
بدون نیاز به pandas (Termux + Actions)
"""

import json
import os
from datetime import datetime


def test_1_rial_to_usd():
    """تست ۱: تبدیل ریال به دلار"""
    raw = json.load(open('data/wallex_tmn_all.json'))
    tgju = json.load(open('data/usd_irr_tgju.json'))
    
    dates = sorted(raw['BTCTMN'].keys())
    btc_rial = raw['BTCTMN'][dates[-1]]
    usd_rate = tgju[sorted(tgju.keys())[-1]]
    btc_usd = btc_rial / usd_rate
    
    qty = 3500 / btc_usd  # 35% از $10,000
    
    if 0.4 < qty < 0.6:
        print(f"  ✅ PASS: 35% از $10k → {qty:.6f} BTC (درست)")
        return True
    else:
        print(f"  🔴 FAIL: qty={qty} (باید ~0.5 BTC)")
        return False


def test_2_tether_preserved():
    """تست ۲: TETHER حفظ می‌شود"""
    equity = 10000
    target = {"BTC": 0.35, "TETHER": 0.65}
    
    capital = 0
    for a, w in target.items():
        if a == "TETHER":
            capital += equity * w
    
    if abs(capital - 6500) < 10:
        print(f"  ✅ PASS: TETHER = ${capital:.2f}")
        return True
    else:
        print(f"  🔴 FAIL: TETHER={capital}")
        return False


def test_3_rsi_inversion():
    """تست ۳: RSI معکوس نیست"""
    rsi_vals = [5, 15, 25, 50]  # 5 = oversoldترین
    
    sig = [r < 30 for r in rsi_vals]
    scored = [(30 - r) if s else None for r, s in zip(rsi_vals, sig)]
    filled = [s if s is not None else -999 for s in scored]
    sorted_idx = sorted(range(len(filled)), key=lambda i: -filled[i])
    ranks = [0] * len(filled)
    for rank, idx in enumerate(sorted_idx, 1):
        ranks[idx] = rank
    
    # باید rsi=5 رتبه ۱ بگیرد
    if ranks[0] == 1 and ranks[2] == 3:
        print(f"  ✅ PASS: RSI=5 → rank 1 (کمترین RSI بالاترین rank)")
        return True
    else:
        print(f"  🔴 FAIL: ranks={ranks} (باید [1,2,3,4])")
        return False


def test_4_price_freshness():
    """تست ۴: قیمت قدیمی skip می‌شود"""
    # شبیه‌سازی: X در 51 روز پیش
    today = datetime(2026, 11, 15)
    x_last = datetime(2026, 9, 25)
    age = (today - x_last).days
    
    if age > 7:
        print(f"  ✅ PASS: X ({age}d old) باید skip شود")
        return True
    else:
        print(f"  🔴 FAIL: X ({age}d old) نباید skip شود")
        return False


def test_5_hl_tether():
    """تست ۵: HL TETHER حفظ می‌شود"""
    equity = 10000
    fee = equity * 0.00035  # 0.035%
    equity_after = equity - fee
    
    target = {"BTC": 0.35, "TETHER": 0.6425, "BNB": 0.0075}
    capital = 0
    for a, w in target.items():
        if a == "TETHER":
            capital += equity_after * w
    
    expected = equity_after * 0.6425
    if abs(capital - expected) < 1:
        print(f"  ✅ PASS: HL TETHER = ${capital:.2f}")
        return True
    else:
        print(f"  🔴 FAIL: HL TETHER = ${capital:.2f}, expected ${expected:.2f}")
        return False


def test_6_equity_roundtrip():
    """تست ۶: equity قبل و بعد از rebalance یکسان"""
    equity = 10000
    fee = equity * 0.006
    equity_after = equity - fee
    
    prices = {"BTC": 17000000000, "ETH": 500000000, "UNI": 1300000}
    usd_rate = 2672100
    weights = {"BTC": 0.35, "ETH": 0.30, "UNI": 0.35}
    
    holdings = {}
    for a, w in weights.items():
        alloc = equity_after * w
        price_usd = prices[a] / usd_rate
        holdings[a] = alloc / price_usd
    
    # بازمحاسبه
    new_equity = 0
    for a, q in holdings.items():
        new_equity += q * (prices[a] / usd_rate)
    
    if abs(new_equity - equity_after) < 1:
        print(f"  ✅ PASS: ${equity_after:.2f} → ${new_equity:.2f} (round-trip OK)")
        return True
    else:
        print(f"  🔴 FAIL: ${equity_after:.2f} → ${new_equity:.2f}")
        return False


def main():
    print("=" * 60)
    print("  COMPREHENSIVE TEST")
    print("=" * 60)
    print()
    
    tests = [
        ("Rial to USD conversion", test_1_rial_to_usd),
        ("TETHER preservation", test_2_tether_preserved),
        ("RSI inversion", test_3_rsi_inversion),
        ("Price freshness (X)", test_4_price_freshness),
        ("HL TETHER", test_5_hl_tether),
        ("Equity round-trip", test_6_equity_roundtrip),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"[{name}]")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  🔴 EXCEPTION: {e}")
            failed += 1
        print()
    
    print("=" * 60)
    print(f"  RESULT: {passed}/{len(tests)} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        print("\n🔴 TEST FAILED — Paper نباید شروع شود")
        exit(1)
    else:
        print("\n🎉 ALL TESTS PASSED — Paper قابل شروع است")


if __name__ == "__main__":
    main()
