"""D-480: Unified dashboard for 8 Paper bots."""
import os, json
from datetime import datetime, timezone

BOTS = [
    ("HL Paper",      "exchanges/hyperliquid/state/m11_hl_portfolio.json",            9998.45),
    ("Aster Paper",   "exchanges/aster/state/m11_aster_paper_state.json",             10000.00),
    ("KuCoin Paper",  "exchanges/kucoin/state/m11_kucoin_paper_state.json",           9998.38),
    ("Aster COMBO",   "exchanges/aster/state/m11_aster_combo_paper_state.json",       10003.13),
    ("HL Shadow",     "exchanges/hyperliquid/state/m11_hl_shadow_portfolio.json",     10000.00),
    ("Aster Sh TREND","exchanges/aster/state/m11_aster_shadow_trend_state.json",      10002.35),
    ("Aster Sh RP",   "exchanges/aster/state/m11_aster_shadow_rp_state.json",         10002.12),
    ("Aster Sh LV",   "exchanges/aster/state/m11_aster_shadow_lv_state.json",         10002.10),
]

def main():
    now = datetime.now(timezone.utc)
    print("="*90)
    print(f"  PRICE_BOT DASHBOARD — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*90)
    print(f"\n{'Bot':<18} {'Equity':>12} {'vs Base':>10} {'Last Run':>12} {'Trades':>8} {'Status':>10}")
    print("-"*90)
    
    total_eq = 0
    total_trades = 0
    issues = 0
    
    for name, path, baseline in BOTS:
        if not os.path.exists(path):
            print(f"{name:<18} {'MISSING':>12}")
            issues += 1
            continue
        try:
            d = json.load(open(path))
            eq = d.get('total_equity', d.get('total_capital', 0))
            hist = len(d.get('history', []))
            lr = d.get('last_run', 'MISSING')
            
            total_eq += eq
            total_trades += hist
            
            if lr != 'MISSING':
                try:
                    age = (now - datetime.fromisoformat(lr.replace('Z','+00:00'))).total_seconds() / 3600
                    age_str = f"{age:.1f}h ago"
                except: age_str = "?"
            else:
                age_str = "MISSING"
                issues += 1
            
            delta = ((eq - baseline) / baseline) * 100
            status = "✅ OK"
            if age_str == "MISSING" or (age_str != "?" and float(age_str.split("h")[0]) > 24):
                status = "⚠️ STALE"
                issues += 1
            elif abs(delta) > 10:
                status = "⚠️ OUTLIER"
                issues += 1
            
            print(f"{name:<18} {eq:>10.2f} {delta:>+8.2f}% {age_str:>12} {hist:>8} {status:>10}")
        except Exception as e:
            print(f"{name:<18} ERROR: {e}")
            issues += 1
    
    print("-"*90)
    print(f"{'TOTAL':<18} {total_eq:>10.2f} {'':>10} {'':>12} {total_trades:>8}")
    print()
    if issues == 0:
        print(f"✅ ALL {len(BOTS)} BOTS HEALTHY")
    else:
        print(f"⚠️ {issues} issues detected")
    
    # Pending
    print()
    try:
        pend = json.load(open("exchanges/pending_approvals.json"))
        print(f"Pending approvals: {len(pend)} entries")
    except:
        print("Pending approvals: file missing")

if __name__ == "__main__":
    main()
