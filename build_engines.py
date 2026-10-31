"""Build auto_research_v2 pipeline: screening + validation + orchestrator + workflow."""
import os

# ═══════════════════════════════════════
# screening.py
# ═══════════════════════════════════════
open('research_lab/screening.py', 'w').write('''"""Screening Engine — fast filter of 38 strategies × params on train split."""
import sys, os, json, math
sys.path.append(os.getcwd())
from datetime import datetime, timezone
from strategies.library.registry import expand_param_grid, get_strategy, list_strategies
from strategies.core_engine import load_data, calculate_metrics
from research_lab.audit_core import load_funding

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

MIN_N = 30
MIN_PF = 1.3
TRAIN_SPLIT = 0.7

def _metrics_from_funding_returns(daily_dict):
    """Convert funding daily returns dict to (n, pf, wr) tuple."""
    rets = list(daily_dict.values())
    if len(rets) < 5: return None
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    if not losses:
        pf = 99.99 if wins else 0
    else:
        pf = sum(wins) / abs(sum(losses)) if losses else 99.99
    # n = number of daily periods (more meaningful than trades for funding)
    n = len(rets)
    wr = len(wins) / len(rets) * 100 if rets else 0
    return {"n": n, "pf": round(pf, 2), "wr": round(wr, 1), "mean_pct": round(sum(rets)/len(rets)*100, 4)}

def _run_candle_strategy(name, params, exchange, symbol):
    """Run candle-based strategy, return trade list metrics."""
    func, grid, kind = get_strategy(name)
    candles = load_data(exchange, symbol)
    if not candles or len(candles) < 200: return None
    # Train split only
    train_end = int(len(candles) * TRAIN_SPLIT)
    train_candles = candles[:train_end]
    try:
        trades = func(train_candles, **params)
    except Exception:
        return None
    if not trades or len(trades) < MIN_N: return None
    m = calculate_metrics(trades)
    if m.get("status") != "OK": return None
    return {"n": m["n"], "pf": m["pf"], "wr": m["win_rate"], "max_dd": m.get("max_dd", 0)}

def _run_funding_strategy(name, params, exchange, symbol):
    """Run funding-based strategy, return metrics."""
    func, grid, kind = get_strategy(name)
    records = load_funding(exchange, symbol)
    if not records or len(records) < 100: return None
    # Train split
    train_end = int(len(records) * TRAIN_SPLIT)
    train_records = records[:train_end]
    try:
        daily = func(train_records, **params)
    except Exception:
        return None
    if not daily: return None
    return _metrics_from_funding_returns(daily)

def screening_run(exchange, symbols):
    """Run all strategies × params on one exchange. Return top candidates."""
    print(f"═══ Screening {exchange.upper()} ═══")
    results = []
    strategies = list_strategies()
    total_combos = 0
    
    for name, kind in strategies:
        func, grid, _ = get_strategy(name)
        param_combos = expand_param_grid(grid)
        for params in param_combos:
            total_combos += 1
            # Pool metrics across all symbols
            all_metrics = []
            for sym in symbols:
                if kind == "candle":
                    m = _run_candle_strategy(name, params, exchange, sym)
                else:
                    m = _run_funding_strategy(name, params, exchange, sym)
                if m: all_metrics.append(m)
            
            if not all_metrics: continue
            # Aggregate
            total_n = sum(m["n"] for m in all_metrics)
            if total_n < MIN_N: continue
            avg_pf = sum(m["pf"] for m in all_metrics) / len(all_metrics)
            if avg_pf < MIN_PF: continue
            
            results.append({
                "strategy": name,
                "kind": kind,
                "params": params,
                "n": total_n,
                "pf": round(avg_pf, 2),
                "wr": round(sum(m["wr"] for m in all_metrics) / len(all_metrics), 1),
                "symbols": len(all_metrics),
            })
    
    # Sort by PF desc, then n desc
    results.sort(key=lambda x: (-x["pf"], -x["n"]))
    top = results[:20]
    print(f"  {total_combos} combos tested → {len(results)} passed filter → top {len(top)} kept")
    for r in top[:5]:
        print(f"    {r['strategy']:20s} PF={r['pf']:5.2f} n={r['n']:4} params={r['params']}")
    if len(top) > 5: print(f"    ... +{len(top)-5} more")
    return top

def main():
    all_results = {}
    for exchange, symbols in EXCHANGES.items():
        all_results[exchange] = screening_run(exchange, symbols)
        print()
    
    os.makedirs("research_lab/logs", exist_ok=True)
    with open("research_lab/logs/screening_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"📄 screening_results.json saved")
    total = sum(len(v) for v in all_results.values())
    print(f"Total candidates: {total}")

if __name__ == "__main__":
    main()
''')
print("[1/4] screening.py")

# ═══════════════════════════════════════
# validation_v2.py
# ═══════════════════════════════════════
open('research_lab/validation_v2.py', 'w').write('''"""Validation Engine — SPA + DSR on screening survivors (on held-out 30%)."""
import sys, os, json, math, random
sys.path.append(os.getcwd())
from strategies.library.registry import get_strategy
from strategies.core_engine import load_data, calculate_metrics
from research_lab.audit_core import load_funding, deflated_sharpe

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

TEST_SPLIT = 0.7  # start of test = 70% (train was 0-70%)
MIN_N = 15
MIN_PF = 1.2
N_BOOTSTRAP = 500

def _test_returns_candle(name, params, exchange, symbol):
    """Get trade returns from test split."""
    func, _, _ = get_strategy(name)
    candles = load_data(exchange, symbol)
    if not candles: return []
    test_candles = candles[int(len(candles)*TEST_SPLIT):]
    try:
        trades = func(test_candles, **params)
    except Exception:
        return []
    return [t["ret"] for t in trades]

def _test_returns_funding(name, params, exchange, symbol):
    """Get daily returns from test split."""
    func, _, _ = get_strategy(name)
    records = load_funding(exchange, symbol)
    if not records: return []
    test_records = records[int(len(records)*TEST_SPLIT):]
    try:
        daily = func(test_records, **params)
    except Exception:
        return []
    return list(daily.values())

def spa_test(candidate_returns, n_bootstrap=N_BOOTSTRAP):
    """SPA vs zero (cash). Returns p-value."""
    if not candidate_returns or len(candidate_returns) < 10:
        return 1.0
    n = len(candidate_returns)
    mean = sum(candidate_returns) / n
    if mean <= 0: return 1.0
    
    t_obs = mean
    
    rng = random.Random(42)
    t_boots = []
    block_size = min(10, n // 5)
    for _ in range(n_bootstrap):
        indices = []
        while len(indices) < n:
            start = rng.randint(0, n - block_size)
            indices.extend(range(start, start + block_size))
        indices = indices[:n]
        boot_mean = sum(candidate_returns[i] for i in indices) / n
        t_boots.append(boot_mean)
    
    p = sum(1 for t in t_boots if t >= t_obs) / n_bootstrap
    return p

def validate_candidate(cand, exchange, symbols):
    """Validate one candidate on test split."""
    name = cand["strategy"]
    kind = cand["kind"]
    params = cand["params"]
    
    all_returns = []
    n_trades = 0
    for sym in symbols:
        if kind == "candle":
            rets = _test_returns_candle(name, params, exchange, sym)
        else:
            rets = _test_returns_funding(name, params, exchange, sym)
        all_returns.extend(rets)
        n_trades += len(rets)
    
    if n_trades < MIN_N:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"n={n_trades}<{MIN_N}"}
    
    mean = sum(all_returns) / len(all_returns)
    if mean <= 0:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": "mean<=0"}
    
    wins = [r for r in all_returns if r > 0]
    losses = [r for r in all_returns if r < 0]
    pf = sum(wins) / abs(sum(losses)) if losses else 99.99
    if pf < MIN_PF:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"PF={pf:.2f}<{MIN_PF}"}
    
    # SPA
    p = spa_test(all_returns)
    if p > 0.05:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"SPA p={p:.3f}", "pf": round(pf,2), "n": n_trades}
    
    # DSR
    std = math.sqrt(sum((r-mean)**2 for r in all_returns) / max(len(all_returns)-1, 1))
    if std > 0:
        sharpe = (mean / std) * math.sqrt(365)  # rough annualization
        d = deflated_sharpe(sharpe, len(all_returns), 54)
        dsr = d["DSR"] if d else 0
    else:
        dsr = 1.0
    
    if dsr < 0.90:
        return {"strategy": name, "params": params, "verdict": "REJECTED", "reason": f"DSR={dsr:.3f}<0.90", "pf": round(pf,2), "n": n_trades, "spa_p": round(p,4)}
    
    return {
        "strategy": name, "params": params, "verdict": "PASS",
        "pf": round(pf,2), "n": n_trades, "spa_p": round(p,4), "dsr": round(dsr,4),
        "mean_pct": round(mean*100, 4),
    }

def main():
    screening_file = "research_lab/logs/screening_results.json"
    if not os.path.exists(screening_file):
        print("❌ No screening results. Run screening.py first."); return
    
    with open(screening_file) as f:
        screening = json.load(f)
    
    print("═" * 60)
    print("  VALIDATION — SPA + DSR on test split")
    print("═" * 60 + "\\n")
    
    all_survivors = {}
    for exchange, candidates in screening.items():
        symbols = EXCHANGES[exchange]
        print(f"═══ {exchange.upper()} ({len(candidates)} candidates) ═══")
        survivors = []
        for cand in candidates:
            result = validate_candidate(cand, exchange, symbols)
            if result["verdict"] == "PASS":
                survivors.append(result)
                print(f"  ✅ {result['strategy']:20s} PF={result['pf']:5.2f} n={result['n']:3} SPA_p={result['spa_p']:.3f} DSR={result['dsr']:.3f}")
            else:
                print(f"  ❌ {result['strategy']:20s} {result['reason']}")
        all_survivors[exchange] = survivors
        print(f"  → {len(survivors)} survivors\\n")
    
    with open("research_lab/logs/validation_results.json", "w") as f:
        json.dump(all_survivors, f, indent=2, default=str)
    print(f"📄 validation_results.json saved")
    total = sum(len(v) for v in all_survivors.values())
    print(f"Total survivors: {total}")

if __name__ == "__main__":
    main()
''')
print("[2/4] validation_v2.py")

# ═══════════════════════════════════════
# unified_master_v2.py
# ═══════════════════════════════════════
open('research_lab/unified_master_v2.py', 'w').write('''"""Unified Master v2 — reads validation survivors, proposes weights (no auto-apply)."""
import sys, os, json
sys.path.append(os.getcwd())
from datetime import datetime, timezone
from research_lab.bale_notifier import send_bale

M31_BASE = 0.65
CASH_BASE = 0.20
DIVERSIFIER_BUDGET = 0.15

def build_portfolio(survivors):
    """M31 + Cash + up to 2 survivors (equal weight)."""
    weights = {"M31": M31_BASE, "Cash": CASH_BASE}
    if not survivors:
        weights["Cash"] = 1.0 - M31_BASE
        return weights
    # Pick top 2 survivors by PF
    top = sorted(survivors, key=lambda x: -x["pf"])[:2]
    per = DIVERSIFIER_BUDGET / len(top)
    for s in top:
        key = f"{s['strategy']}_{s['params'].get('period', s['params'].get('fast', 'x'))}"
        weights[key] = round(per, 4)
    # Normalize
    total = sum(weights.values())
    return {k: round(v/total, 4) for k, v in weights.items()}

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== 🤖 Unified Master v2 ({now}) ===\\n")
    
    val_file = "research_lab/logs/validation_results.json"
    if not os.path.exists(val_file):
        print(f"❌ No validation results. Run validation_v2.py first.")
        return
    
    with open(val_file) as f:
        validation = json.load(f)
    
    proposed = {}
    report = [f"🤖 **Unified Master v2** ({now})\\n"]
    
    for exchange, survivors in validation.items():
        weights = build_portfolio(survivors)
        proposed[exchange] = weights
        report.append(f"\\n**{exchange.upper()}** — {len(survivors)} survivors")
        for name, w in sorted(weights.items(), key=lambda x: -x[1]):
            report.append(f"  • {name}: {w*100:.1f}%")
    
    # Save proposal (NOT active_weights.json)
    with open("exchanges/proposed_weights.json", "w") as f:
        json.dump(proposed, f, indent=2)
    print("✅ proposed_weights.json saved (requires AI3 approval to apply)")
    
    msg = "\\n".join(report)
    msg += "\\n\\n⚠️ این پیشنهاد است، نه اعمال. برای اعمال، تأیید AI3 الزامی است."
    print(msg)
    send_bale(msg)

if __name__ == "__main__":
    main()
''')
print("[3/4] unified_master_v2.py")

# ═══════════════════════════════════════
# workflow — weekly auto_research_v2
# ═══════════════════════════════════════
open('.github/workflows/auto_research_v2.yml', 'w').write('''name: Auto Research v2 (Weekly)

on:
  schedule:
    - cron: '0 6 * * 0'  # Sunday 6 UTC (one hour before old unified_master)
  workflow_dispatch:

permissions:
  contents: write

jobs:
  research:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install
        run: pip install requests
      - name: Screening
        run: python -m research_lab.screening
      - name: Validation
        run: python -m research_lab.validation_v2
      - name: Orchestrator
        env:
          BALE_BOT_TOKEN: ${{ secrets.BALE_BOT_TOKEN }}
          BALE_CHAT_ID: ${{ secrets.BALE_CHAT_ID }}
        run: python -m research_lab.unified_master_v2
      - name: Commit results
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          git add research_lab/logs/screening_results.json research_lab/logs/validation_results.json exchanges/proposed_weights.json || echo "no artifacts"
          git diff --quiet && git diff --staged --quiet || git commit -m "auto: weekly research v2 [skip ci]" || echo "no changes"
          git pull --rebase origin main || true
          git push || echo "push failed"
''')
print("[4/4] workflow")

print("\\n✅ All 4 files built")
print("Files: screening.py, validation_v2.py, unified_master_v2.py, auto_research_v2.yml")
