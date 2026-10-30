import sys, os, json, random, math, subprocess
from datetime import datetime, timezone
sys.path.append(os.getcwd())
from strategies.core_engine import (strategy_m35, strategy_a20, strategy_m40,
    strategy_a8, strategy_m50_regime_bh, strategy_m51_extreme_rev,
    strategy_m52_xsect_momentum, strategy_m53_vol_breakout,
    load_data, calculate_metrics)
from research_lab.bale_notifier import send_bale

MODE = "SEMI"  # SEMI (پیشنهاد + تایید دستی) یا ACTIVE (خودکار)
WEIGHT_CHANGE_THRESHOLD = 0.20
WEIGHTS_FILE = "exchanges/active_weights.json"

VARIANTS = {
    "M35_20_100": lambda c: strategy_m35(c, fast=20, slow=100),
    "M35_50_200": lambda c: strategy_m35(c, fast=50, slow=200),
    "A20": strategy_a20, "M40": strategy_m40, "A8": strategy_a8,
    "M50": strategy_m50_regime_bh, "M51": strategy_m51_extreme_rev,
    "M52": strategy_m52_xsect_momentum, "M53": strategy_m53_vol_breakout,
}
EXCHANGES = {
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
}

def embargo_wf(candles, n_windows=5, embargo=20, train_ratio=0.7):
    ws = len(candles) // n_windows
    for i in range(n_windows):
        s = i * ws
        tr_end = s + int(ws * train_ratio) - embargo
        te_start = s + int(ws * train_ratio) + embargo
        yield candles[s:tr_end], candles[te_start:s+ws]

def boot_p(rets, block_size=6, iterations=300, seed=42):
    n = len(rets)
    if n < 20: return 1.0
    actual = 1.0
    for r in rets: actual *= (1 + r * 0.01)
    rng = random.Random(seed)
    better = 0
    for _ in range(iterations):
        sim = 1.0; sm = 0
        while sm < n:
            st = rng.randint(0, n - 1)
            for i in range(block_size):
                if sm >= n: break
                sim *= (1 + rets[(st+i) % n] * 0.01); sm += 1
        if sim >= actual: better += 1
    return better / iterations

def holm(p_vals, alpha=0.05):
    n = len(p_vals)
    order = sorted(range(n), key=lambda i: p_vals[i])
    passed = [False] * n
    for k, idx in enumerate(order):
        if p_vals[idx] <= alpha / (n - k): passed[idx] = True
        else: break
    return passed

def analyze_exchange(ex, syms):
    results = []
    for name, func in VARIANTS.items():
        trades = []
        for sym in syms:
            cd = load_data(ex, sym)
            if not cd: continue
            for _, test in embargo_wf(cd):
                if len(test) > 20:
                    try: trades.extend(func(test))
                    except: pass
        if len(trades) < 15: continue
        m = calculate_metrics(trades)
        rets = [t["ret"] for t in trades]
        results.append({"name": name, "pf": m.get("pf", 0), "n": m.get("n", 0), "p": boot_p(rets)})
    
    if len(results) < 2: return {"status": "NO_WINNER", "reason": "too few variants"}
    
    passed = holm([r["p"] for r in results])
    survivors = [r for i, r in enumerate(results) if passed[i]]
    
    if len(survivors) < 2:
        survivors = [r for r in results if r["pf"] > 1.3 and r["p"] < 0.40]
    
    if len(survivors) < 2:
        return {"status": "NO_WINNER", "survivors": [s["name"] for s in survivors]}
    
    # HRP با Inverse Variance
    weights = {}
    for r in survivors:
        # واریانس معکوس بر اساس PF به عنوان proxy
        weights[r["name"]] = r["pf"] / max(r["n"] ** 0.5, 1)
    total = sum(weights.values())
    weights = {k: v/total for k, v in weights.items()}
    # سقف 50%
    for _ in range(20):
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        if all(0.10 <= w <= 0.50 for w in weights.values()): break
        for k in [k for k,v in weights.items() if v > 0.50]: weights[k] = 0.50
        for k in [k for k,v in weights.items() if v < 0.10]: weights[k] = 0.10
    total = sum(weights.values())
    weights = {k: round(v/total, 4) for k, v in weights.items()}
    
    return {"status": "OK", "weights": weights, "survivors_detail": survivors}

def current_weights(ex):
    if not os.path.exists(WEIGHTS_FILE): return None
    try:
        with open(WEIGHTS_FILE) as f:
            return json.load(f).get(ex, None)
    except: return None

def main():
    # پاک کردن پیشنهاد قبلی
    if os.path.exists("exchanges/proposed_weights.json"):
        os.remove("exchanges/proposed_weights.json")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== 🤖 Master Orchestrator ({now}) ===")
    print(f"Mode: {MODE}\n")
    
    proposals = {}
    report_lines = [f"🤖 **Master Orchestrator** ({now})\n"]
    
    # خواندن weights فعلی
    current_all = {}
    if os.path.exists(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE) as f:
                current_all = json.load(f)
        except: pass
    
    for ex, syms in EXCHANGES.items():
        print(f"\n─── {ex.upper()} ───")
        analysis = analyze_exchange(ex, syms)
        
        if analysis["status"] == "NO_WINNER":
            print(f"  ⚠️ NO_WINNER")
            report_lines.append(f"\n🌐 **{ex.upper()}**: ⚠️ NO_WINNER (بدون تغییر)")
            continue
        
        new_weights = analysis["weights"]
        # اضافه کردن M31 (فاندینگ) با تخصیص ثابت
        new_weights_final = {"M31": 0.50}
        for k, v in new_weights.items():
            new_weights_final[k] = round(v * 0.50, 4)
        
        # مقایسه با فعلی
        cur = current_all.get(ex, {})
        max_diff = 0
        for k in set(new_weights_final.keys()) | set(cur.keys()):
            diff = abs(new_weights_final.get(k, 0) - cur.get(k, 0))
            max_diff = max(max_diff, diff)
        
        print(f"  Proposed: {new_weights_final}")
        print(f"  Max change: {max_diff*100:.1f}%")
        
        if max_diff > WEIGHT_CHANGE_THRESHOLD:
            proposals[ex] = new_weights_final
            report_lines.append(f"\n🌐 **{ex.upper()}**: 🎯 پیشنهاد تغییر (Δ={max_diff*100:.0f}%)")
            for k, v in new_weights_final.items():
                old = cur.get(k, 0)
                report_lines.append(f"   • {k}: {old*100:.0f}% → {v*100:.0f}%")
        else:
            report_lines.append(f"\n🌐 **{ex.upper()}**: ✅ ترکیب فعلی تایید شد")
    
    # اعمال یا پیشنهاد
    if proposals:
        if MODE == "ACTIVE":
            with open(WEIGHTS_FILE, "w") as f:
                json.dump(proposals, f, indent=2)
            report_lines.append(f"\n✅ **اعمال شد** (MODE=ACTIVE)")
            print("✅ Weights applied (ACTIVE mode)")
        else:
            # ذخیره پیشنهاد برای تایید دستی
            with open("exchanges/proposed_weights.json", "w") as f:
                json.dump(proposals, f, indent=2)
            report_lines.append(f"\n⏸️ **SEMI mode**: فایل `proposed_weights.json` ساخته شد.")
            report_lines.append(f"برای اعمال، دستور زیر را اجرا کنید:")
            report_lines.append(f"`mv exchanges/proposed_weights.json exchanges/active_weights.json && git commit -am 'Apply weights' && git push`")
            print("⏸️ Proposal saved to proposed_weights.json")
    
    report_lines.append(f"\n⚙️ Mode: {MODE}")
    msg = "\n".join(report_lines)
    print("\n" + msg)
    send_bale(msg)

if __name__ == "__main__":
    main()
