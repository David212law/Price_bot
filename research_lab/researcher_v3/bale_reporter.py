"""D-558: Bale Reporter — Auto notification."""
import os, json, urllib.request


def send_bale(msg):
    """Send message to Bale. Returns True/False."""
    token = os.environ.get("BALE_BOT_TOKEN", "")
    chat_id = os.environ.get("BALE_CHAT_ID", "")
    if not token or not chat_id:
        print(f"[BALE-SKIP] {msg[:100]}")
        return False
    try:
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": msg[:4000]}).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"[BALE-ERR] {e}")
        return False


def format_report(combos, pareto, live_data, per_exchange):
    """Format research report for Bale."""
    lines = ["📊 Researcher v3 Report"]
    lines.append("")
    
    # Live data status
    live_ok = sum(1 for d in live_data.values() if "error" not in d)
    lines.append(f"📡 Live: {live_ok}/4 exchanges OK")
    for exch, d in live_data.items():
        if "error" in d:
            lines.append(f"  ❌ {exch}: {d['error'][:40]}")
        else:
            lines.append(f"  ✅ {exch}: {len(d['prices'])} days")
    
    # Pareto front
    lines.append("")
    lines.append(f"🎯 Pareto: {len(pareto)} strategies")
    for p in pareto[:5]:
        lines.append(f"  • {p[:40]}")
    
    # Combos per regime
    lines.append("")
    lines.append(f"🔧 Combos: {len(combos)} regimes")
    for regime, combo in combos.items():
        if "components" in combo:
            comps = ", ".join(f"{c['strategy']}@{c['weight']:.0%}" for c in combo["components"])
            cov = combo.get("coverage", "?")
            lines.append(f"  {regime}: {comps[:60]} [{cov}/16]")
    
    # Per-exchange
    if per_exchange:
        lines.append("")
        lines.append(f"📈 Per-exchange:")
        for exch, info in per_exchange.items():
            n = info.get("n_strategies", 0)
            best = info.get("best", "?")
            lines.append(f"  {exch}: {n} strategies, best={best[:30]}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    ok = send_bale("🧪 Bale reporter test")
    print(f"Sent: {ok}")
