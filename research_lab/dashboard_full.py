"""D-486: Full monitoring dashboard — text + HTML for mobile browser."""
import os, json
from datetime import datetime, timezone

BOTS = [
    ("HL Paper",          "exchanges/hyperliquid/state/m11_hl_portfolio.json",              10000.00),
    ("Aster Paper",       "exchanges/aster/state/m11_aster_paper_state.json",               10000.00),
    ("KuCoin Paper",      "exchanges/kucoin/state/m11_kucoin_paper_state.json",             10000.00),
    ("Aster COMBO",       "exchanges/aster/state/m11_aster_combo_paper_state.json",         10000.00),
    ("HL Shadow",         "exchanges/hyperliquid/state/m11_hl_shadow_portfolio.json",       10000.00),
    ("Aster Shadow TREND","exchanges/aster/state/m11_aster_shadow_trend_state.json",        10000.00),
    ("Aster Shadow RP",   "exchanges/aster/state/m11_aster_shadow_rp_state.json",           10000.00),
    ("Aster Shadow LV",   "exchanges/aster/state/m11_aster_shadow_lv_state.json",           10000.00),
    ("KuCoin Combo (S)",  "exchanges/kucoin/state/m11_kucoin_shadow_combo_state.json",      10000.00),
]

def load_json(path):
    if not os.path.exists(path): return None
    try: return json.load(open(path))
    except: return None

def get_equity(d):
    """D-486-fix: try all possible keys, fallback to last history entry."""
    if not d: return None
    for key in ["total_equity", "total_capital", "equity", "capital"]:
        if key in d and d[key] not in (None, 0):
            return float(d[key])
    # Tracker synthetic state: use last history snapshot
    hist = d.get("history", [])
    if isinstance(hist, list) and hist:
        last = hist[-1]
        if "combo_hypo_equity" in last:
            return float(last["combo_hypo_equity"])
        if "m31_real_equity" in last:
            return float(last["m31_real_equity"])
    return None

def fmt_age(iso_str):
    if not iso_str or iso_str == "MISSING": return "?"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z","+00:00"))
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        return f"{age:.1f}h"
    except: return "?"

def gather():
    now = datetime.now(timezone.utc)
    bots_data = []
    issues = []
    for name, path, baseline in BOTS:
        d = load_json(path)
        if not d:
            bots_data.append({"name": name, "status": "MISSING", "equity": None})
            issues.append(f"{name}: state missing")
            continue
        eq = get_equity(d)
        if eq is None:
            bots_data.append({"name": name, "status": "MISSING", "equity": None})
            issues.append(f"{name}: equity unreadable")
            continue
        hist = len(d.get("history", []))
        lr = d.get("last_run", d.get("created_at", "MISSING"))
        age = fmt_age(lr)
        delta = ((eq - baseline) / baseline) * 100 if baseline else 0
        is_stale = age != "?" and float(age.replace("h","")) > 24
        is_outlier = abs(delta) > 10
        status = "OK"
        if is_stale: status = "STALE"; issues.append(f"{name}: stale ({age})")
        elif is_outlier: status = "OUTLIER"; issues.append(f"{name}: outlier ({delta:+.1f}%)")
        bots_data.append({
            "name": name, "equity": eq, "baseline": baseline,
            "delta_pct": round(delta, 3), "last_run": lr, "age": age,
            "trades": hist, "status": status
        })
    
    # Pending approvals
    pend = load_json("exchanges/pending_approvals.json") or {}
    
    # Profiler stats
    prof = load_json("research_lab/logs/profiles/state.json") or {}
    prof_total = len(prof.get("done", {}))
    prof_stressed = sum(1 for v in prof.get("done", {}).values()
                        if isinstance(v, dict) and v.get("validation", {}).get("stress"))
    
    # Combo tracker
    tracker = load_json("exchanges/kucoin/state/m11_kucoin_shadow_combo_state.json") or {}
    tracker_hist = tracker.get("history", [])
    last_tracker = tracker_hist[-1] if tracker_hist else None
    
    return {
        "timestamp": now.isoformat(),
        "timestamp_display": now.strftime("%Y-%m-%d %H:%M UTC"),
        "bots": bots_data,
        "pending": pend,
        "profiler": {"total": prof_total, "stressed": prof_stressed},
        "tracker_last": last_tracker,
        "issues": issues,
    }

def print_text(data):
    print("=" * 90)
    print(f"  PRICE_BOT — FULL DASHBOARD  |  {data['timestamp_display']}")
    print("=" * 90)
    
    print(f"\n{'Bot':<22} {'Equity':>12} {'vs Base':>10} {'Age':>8} {'Trades':>8} {'Status':>10}")
    print("-" * 90)
    total_eq = 0
    for b in data["bots"]:
        if b.get("equity") is None:
            print(f"{b['name']:<22} {'MISSING':>12}")
            continue
        total_eq += b["equity"]
        status_marker = {"OK":"✅", "STALE":"⚠️", "OUTLIER":"🔴"}.get(b["status"], "?")
        print(f"{b['name']:<22} {b['equity']:>10.2f} {b['delta_pct']:>+8.2f}% {b['age']:>8} {b['trades']:>8} {status_marker} {b['status']}")
    print("-" * 90)
    print(f"{'TOTAL':<22} {total_eq:>10.2f}")
    
    # Pending
    print(f"\n📋 Pending approvals: {len(data['pending'])}")
    for k, v in data["pending"].items():
        status = v.get("status", "?")
        combo = v.get("combo", {})
        print(f"   {k}: {status} | SR={combo.get('combined_sharpe','?')} | n={combo.get('n_days','?')}")
    
    # Profiler
    p = data["profiler"]
    print(f"\n🔬 Profiler: {p['total']} entries ({p['stressed']} stressed)")
    
    # Tracker
    t = data["tracker_last"]
    if t:
        print(f"\n🎯 KuCoin Combo Tracker (last run):")
        print(f"   M31 real:     ${t['m31_real_equity']:.2f} ({t['m31_real_ret_pct']:+.3f}%)")
        print(f"   Combo hypo:   ${t['combo_hypo_equity']:.2f} ({t['combo_hypo_ret_pct']:+.3f}%)")
        print(f"   Diff:         {t['diff_pct']:+.4f}%")
    
    # Issues
    print()
    if data["issues"]:
        print(f"⚠️ {len(data['issues'])} issues:")
        for i in data["issues"]: print(f"   • {i}")
    else:
        print("✅ ALL SYSTEMS HEALTHY")
    print()

def print_html(data):
    rows = ""
    for b in data["bots"]:
        if b.get("equity") is None:
            rows += f"<tr><td>{b['name']}</td><td colspan='4' style='color:#999'>MISSING</td></tr>"
            continue
        color = {"OK":"#22c55e", "STALE":"#f59e0b", "OUTLIER":"#ef4444"}.get(b["status"], "#888")
        rows += (f"<tr>"
                 f"<td>{b['name']}</td>"
                 f"<td>${b['equity']:.2f}</td>"
                 f"<td>{b['delta_pct']:+.3f}%</td>"
                 f"<td>{b['age']}</td>"
                 f"<td style='color:{color};font-weight:bold'>{b['status']}</td>"
                 f"</tr>")
    
    pending_html = ""
    for k, v in data["pending"].items():
        combo = v.get("combo", {})
        pending_html += f"<li><b>{k}</b>: {v.get('status','?')} — SR={combo.get('combined_sharpe','?')}, n={combo.get('n_days','?')}</li>"
    if not pending_html:
        pending_html = "<li>None (صادقانه — هیچ کامبوی واقعی فعال نیست)</li>"
    
    tracker_html = ""
    t = data["tracker_last"]
    if t:
        tracker_html = f"""
        <div class="card">
            <h3>🎯 KuCoin Combo Tracker</h3>
            <p>M31 real: <b>${t['m31_real_equity']:.2f}</b> ({t['m31_real_ret_pct']:+.3f}%)</p>
            <p>Combo hypo: <b>${t['combo_hypo_equity']:.2f}</b> ({t['combo_hypo_ret_pct']:+.3f}%)</p>
            <p>Diff: <b>{t['diff_pct']:+.4f}%</b></p>
        </div>"""
    
    issues_html = "".join(f"<li>{i}</li>" for i in data["issues"]) or "<li>None ✅</li>"
    
    html = f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Price_bot Dashboard</title>
<style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
           margin: 0; padding: 16px; }}
    h1 {{ font-size: 1.4em; margin: 8px 0 16px; }}
    h3 {{ margin: 8px 0; font-size: 1em; color: #94a3b8; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b;
            border-radius: 8px; overflow: hidden; font-size: 0.85em; }}
    th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ background: #334155; color: #cbd5e1; font-weight: 600; }}
    tr:last-child td {{ border-bottom: none; }}
    .card {{ background: #1e293b; padding: 12px 16px; border-radius: 8px;
            margin: 12px 0; }}
    .card p {{ margin: 4px 0; }}
    .issues {{ background: #7f1d1d; padding: 12px 16px; border-radius: 8px; }}
    .issues ul {{ margin: 0; padding-left: 20px; }}
    .time {{ color: #64748b; font-size: 0.8em; margin-bottom: 8px; }}
</style>
</head>
<body>
<h1>📊 Price_bot Dashboard</h1>
<div class="time">{data['timestamp_display']}</div>

<h3>🤖 8 Paper Bots</h3>
<table>
<tr><th>Bot</th><th>Equity</th><th>Δ</th><th>Age</th><th>Status</th></tr>
{rows}
</table>

<div class="card">
    <h3>📋 Pending Approvals ({len(data['pending'])})</h3>
    <ul>{pending_html}</ul>
</div>

<div class="card">
    <h3>🔬 Profiler</h3>
    <p>Total: <b>{data['profiler']['total']}</b> entries</p>
    <p>Stressed: <b>{data['profiler']['stressed']}</b></p>
</div>

{tracker_html}

<div class="{'issues' if data['issues'] else 'card'}">
    <h3>⚠️ Issues ({len(data['issues'])})</h3>
    <ul>{issues_html}</ul>
</div>

<p style="text-align:center;color:#475569;font-size:0.75em;margin-top:24px">
    Generated by dashboard_full.py (D-486)
</p>
</body>
</html>"""
    
    out_path = "reports/dashboard.html"
    os.makedirs("reports", exist_ok=True)
    open(out_path, "w").write(html)
    print(f"✅ HTML saved: {out_path}")
    print(f"   Open: file://{os.path.abspath(out_path)}")

def main():
    data = gather()
    print_text(data)
    print_html(data)

if __name__ == "__main__":
    main()
