"""Iran Currency Crisis Test — Pure Python (no pandas needed)."""
import json

def main():
    print("="*80)
    print(" IRAN CURRENCY CRISIS TEST (Pure Python)")
    print("="*80)

    # Load Wallex TMN
    raw = json.load(open("data/wallex_tmn_all.json"))
    btc_raw = raw.get("BTCTMN", {})
    usdt_raw = raw.get("USDTTMN", {})
    if not btc_raw or not usdt_raw:
        print("❌ Missing BTCTMN or USDTTMN data")
        return

    btc_dates = sorted(btc_raw.keys())
    print(f"\nData: {len(btc_dates)} days ({btc_dates[0]} → {btc_dates[-1]})")

    # Load USD/IRR (TGJU)
    usd_irr = json.load(open("data/usd_irr_tgju.json"))

    # For each date, compute 30-day IRR change
    crisis_dates = []
    for i in range(30, len(btc_dates)):
        d = btc_dates[i]
        d_prev = btc_dates[i - 30]
        if d in usd_irr and d_prev in usd_irr:
            irr_change = (usd_irr[d] / usd_irr[d_prev] - 1) * 100
            if irr_change > 5:  # IRR dropped > 5% in 30 days = crisis
                crisis_dates.append(d)

    print(f"\n📊 Currency Crisis Detection (IRR up > 5% in 30d):")
    print(f"   Crisis days: {len(crisis_dates)} / {len(btc_dates)} ({len(crisis_dates)/len(btc_dates)*100:.1f}%)")

    if len(crisis_dates) < 10:
        print("⚠️ Too few crisis days to test reliably")
        return

    # During crisis: BTC vs Tether returns
    btc_crisis_rets = []
    usdt_crisis_rets = []

    for i in range(1, len(crisis_dates)):
        d = crisis_dates[i]
        d_prev = crisis_dates[i - 1]
        if d in btc_raw and d_prev in btc_raw:
            btc_ret = (btc_raw[d] / btc_raw[d_prev] - 1) * 100
            btc_crisis_rets.append(btc_ret)
        if d in usdt_raw and d_prev in usdt_raw:
            usdt_ret = (usdt_raw[d] / usdt_raw[d_prev] - 1) * 100
            usdt_crisis_rets.append(usdt_ret)

    avg_btc = sum(btc_crisis_rets) / len(btc_crisis_rets) if btc_crisis_rets else 0
    avg_usdt = sum(usdt_crisis_rets) / len(usdt_crisis_rets) if usdt_crisis_rets else 0

    # Total return during crisis (compound)
    btc_total = 1.0
    for r in btc_crisis_rets: btc_total *= (1 + r/100)
    usdt_total = 1.0
    for r in usdt_crisis_rets: usdt_total *= (1 + r/100)

    print(f"\n🔴 During Iran Currency Crisis ({len(crisis_dates)} days):")
    print(f"   BTC/TMN:   avg {avg_btc:+.3f}%/day, total {(btc_total-1)*100:+.1f}%")
    print(f"   USDT/TMN:  avg {avg_usdt:+.3f}%/day, total {(usdt_total-1)*100:+.1f}%")

    # Correlation
    n = min(len(btc_crisis_rets), len(usdt_crisis_rets))
    if n > 5:
        b_vals = btc_crisis_rets[:n]
        u_vals = usdt_crisis_rets[:n]
        m_b = sum(b_vals) / n
        m_u = sum(u_vals) / n
        cov = sum((b_vals[i] - m_b) * (u_vals[i] - m_u) for i in range(n)) / n
        std_b = (sum((v - m_b)**2 for v in b_vals) / n) ** 0.5
        std_u = (sum((v - m_u)**2 for v in u_vals) / n) ** 0.5
        corr = cov / (std_b * std_u) if std_b > 0 and std_u > 0 else 0
        print(f"\n   Correlation BTC vs USDT during crisis: {corr:.2f}")

        if corr > 0.5:
            print(f"   ⚠️ HIGH correlation: BTC and Tether move together")
            print(f"   ⚠️ Survival Mode (Tether) provides LIMITED protection")
        elif corr > 0:
            print(f"   🟡 Moderate correlation: partial protection")
        else:
            print(f"   ✅ LOW correlation: Survival Mode provides protection")

    # Hypothetical: 1000$ during crisis
    print(f"\n📊 If you held $1000 during crisis period:")
    print(f"   100% BTC:    ${1000 * btc_total:,.2f}")
    print(f"   100% Tether: ${1000 * usdt_total:,.2f}")

    print(f"\n{'='*80}")
    print(" VERDICT")
    print(f"{'='*80}")
    if corr > 0.5:
        print(f"  ❌ CRITICAL: Survival Mode (Tether) does NOT protect during Iran crisis")
        print(f"  💡 Recommendation: In crisis, exit to USD (off-ramp) not Tether")
    elif corr > 0.2:
        print(f"  🟡 MODERATE: Survival Mode provides partial protection")
    else:
        print(f"  ✅ GOOD: Survival Mode protects during Iran crisis")

if __name__ == "__main__":
    main()
