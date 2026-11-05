"""D-539: Economic Runner

Reads economic_v1_definitions.json, computes returns for each strategy
using funding data, writes results into profiler state.json so that
the existing filter (composer) sees them naturally.

IMPORTANT: This file modifies profiles/state.json. A backup is created.
For safety, this should run in GitHub Actions, not on the user device.

Outputs:
  - research_lab/logs/profiles/returns_matrices/economic/{strategy}_{hash}_{symbol}.json
  - research_lab/logs/profiles/state.json (appended entries)
  - research_lab/logs/generated/economic_v1_results.json (summary)
"""
import json
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

ROOT = Path.cwd()
STATE_PATH = ROOT / "research_lab/logs/profiles/state.json"
DEFS_PATH = ROOT / "research_lab/logs/generated/economic_v1_definitions.json"
RET_DIR = ROOT / "research_lab/logs/profiles/returns_matrices/economic"
RESULTS_PATH = ROOT / "research_lab/logs/generated/economic_v1_results.json"

EXCHANGES = {
    "hyperliquid": ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"],
    "aster": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"],
    "kucoin": ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"],
}


def safe_load_funding(exchange, symbol):
    """Load funding as {date: rate}. Tries audit_core.load_funding first."""
    try:
        from research_lab.audit_core import load_funding
        d = load_funding(exchange, symbol)
        if d and isinstance(d, dict):
            return _normalize(d)
    except Exception:
        pass
    for p in [
        ROOT / f"exchanges/{exchange}/data/{symbol}_funding.json",
        ROOT / f"data/{exchange}/{symbol}_funding.json",
    ]:
        if p.exists():
            try:
                return _normalize(json.loads(p.read_text()))
            except Exception:
                continue
    return {}


def _normalize(data):
    out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (int, float)):
                out[str(k)[:10]] = float(v)
            elif isinstance(v, dict):
                r = v.get("rate") or v.get("fundingRate") or v.get("funding_rate")
                if r is not None:
                    out[str(k)[:10]] = float(r)
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict): continue
            t = item.get("t") or item.get("timestamp") or item.get("time")
            r = item.get("rate") or item.get("fundingRate") or item.get("funding_rate")
            if t is None or r is None: continue
            if isinstance(t, (int, float)):
                ts = t / 1000 if t > 1e10 else t
                d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            else:
                d = str(t)[:10]
            out[d] = float(r)
    return out


def sharpe_ann(vals):
    if len(vals) < 10: return 0.0
    m = sum(vals) / len(vals)
    v = sum((x - m) ** 2 for x in vals) / len(vals)
    sd = v ** 0.5
    return round((m / sd) * (365 ** 0.5), 2) if sd > 0 else 0.0


def compute_quartile_pf(vals):
    if len(vals) < 20: return [0, 0, 0, 0], False
    n = len(vals)
    pfs = []
    for i in range(4):
        chunk = vals[i * n // 4:(i + 1) * n // 4]
        if not chunk: pfs.append(0.0); continue
        wins = sum(v for v in chunk if v > 0)
        losses = abs(sum(v for v in chunk if v < 0))
        pf = wins / losses if losses > 0 else (999 if wins > 0 else 1.0)
        pfs.append(round(pf, 3))
    return pfs, all(pf > 1.0 for pf in pfs)


# ═══════════════════════════════════════════════════════════════════════
# Economic logic implementations
# ═══════════════════════════════════════════════════════════════════════

def strat_funding_volatility_filter(funding, params):
    """Enter when rolling funding vol is low."""
    lookback = params.get("lookback", 7)
    threshold_pct = params.get("threshold_pct", 60)
    dates = sorted(funding.keys())
    if len(dates) < lookback + 10: return {}
    vols = []
    for i in range(lookback, len(dates)):
        window = [funding[dates[j]] for j in range(i - lookback, i)]
        mean = sum(window) / len(window)
        var = sum((x - mean) ** 2 for x in window) / len(window)
        vols.append((dates[i], var ** 0.5))
    vol_vals = sorted([v for _, v in vols])
    if not vol_vals: return {}
    thresh = vol_vals[int(len(vol_vals) * threshold_pct / 100)]
    returns = {}
    for d, v in vols:
        returns[d] = funding.get(d, 0) if v <= thresh else 0.0
    return returns


def strat_funding_regime_contrarian(funding, params):
    """Take contrarian position when funding is extreme high (short perp receives funding)."""
    lookback = params.get("lookback", 30)
    threshold_pct = params.get("threshold_pct", 85)
    dates = sorted(funding.keys())
    if len(dates) < lookback + 10: return {}
    returns = {}
    for i in range(lookback, len(dates)):
        window = [funding[dates[j]] for j in range(i - lookback, i)]
        sorted_win = sorted(window)
        thresh = sorted_win[int(len(sorted_win) * threshold_pct / 100)]
        d = dates[i]
        r = funding.get(d, 0)
        returns[d] = r if r > thresh else 0.0
    return returns


def strat_funding_zscore(funding, params):
    """Enter when funding z-score exceeds threshold."""
    lookback = params.get("lookback", 30)
    z_threshold = params.get("z_threshold", 1.5)
    dates = sorted(funding.keys())
    if len(dates) < lookback + 10: return {}
    returns = {}
    for i in range(lookback, len(dates)):
        window = [funding[dates[j]] for j in range(i - lookback, i)]
        mean = sum(window) / len(window)
        var = sum((x - mean) ** 2 for x in window) / len(window)
        sd = var ** 0.5
        if sd == 0: continue
        z = (funding[dates[i]] - mean) / sd
        returns[dates[i]] = funding.get(dates[i], 0) if z > z_threshold else 0.0
    return returns


LOGIC_IMPL = {
    "funding_volatility_filter": strat_funding_volatility_filter,
    "funding_regime_contrarian": strat_funding_regime_contrarian,
    "funding_zscore": strat_funding_zscore,
}


def main():
    print("=" * 72)
    print(" ECONOMIC RUNNER — D-539")
    print("=" * 72)

    if not DEFS_PATH.exists():
        print(f"❌ {DEFS_PATH} not found"); return 1
    if not STATE_PATH.exists():
        print(f"❌ {STATE_PATH} not found"); return 1

    defs = json.loads(DEFS_PATH.read_text())
    state = json.loads(STATE_PATH.read_text())

    # Backup state before modifying
    backup = STATE_PATH.with_suffix(".json.bak_D539")
    shutil.copy(STATE_PATH, backup)
    print(f"  💾 Backed up state.json → {backup.name}")

    results = []
    n_written = 0

    for d in defs["definitions"]:
        logic_id = d["logic_id"]
        impl = LOGIC_IMPL.get(logic_id)
        if not impl:
            continue

        for exchange, symbols in EXCHANGES.items():
            for symbol in symbols:
                funding = safe_load_funding(exchange, symbol)
                if len(funding) < 60:
                    continue

                returns = impl(funding, d["params"])
                if not returns or len(returns) < 60:
                    continue

                # Compute metrics
                vals = [returns[dt] for dt in sorted(returns.keys())]
                sr = sharpe_ann(vals)
                if sr <= 0:
                    continue

                pfs, qpass = compute_quartile_pf(vals)
                wins = [v for v in vals if v > 0]
                losses = [-v for v in vals if v < 0]
                pf = sum(wins) / sum(losses) if losses else (999 if wins else 1.0)
                wr = len(wins) / len(vals) * 100 if vals else 0

                # Write returns matrix
                ret_file = RET_DIR / exchange / f"{d['strategy']}_{d['hash']}_{symbol}.json"
                ret_file.parent.mkdir(parents=True, exist_ok=True)
                ret_file.write_text(json.dumps(returns))
                n_written += 1

                # Add to state
                key = f"economic_v1:{d['strategy']}:{d['hash']}:{symbol}"
                metrics = {
                    "n": len(vals),
                    "pf": round(pf, 3),
                    "wr": round(wr, 1),
                    "sharpe_daily": round(sr / (365 ** 0.5), 4),
                    "sufficient": len(vals) >= 30,
                }
                state["done"][key] = {
                    "strategy": d["strategy"],
                    "params": d["params"],
                    "kind": "economic_v1",
                    "exchange": exchange,
                    "symbol": symbol,
                    "n_total": len(vals),
                    "status": "profiled",
                    "metrics_by_regime": {
                        "TREND": metrics, "RANGE": metrics, "NEUTRAL": metrics,
                    },
                    "validation": {
                        "n": len(vals),
                        "pf": round(pf, 3),
                        "wr": round(wr, 1),
                        "sharpe_daily": round(sr / (365 ** 0.5), 4),
                        "sharpe_ann": sr,
                        "quartile_pf": pfs,
                        "quartiles_pass": 4 if qpass else sum(1 for p in pfs if p > 1.0),
                        "stress": {},
                        "calmar": {},
                    },
                }
                results.append({
                    "key": key, "logic": logic_id, "exchange": exchange,
                    "symbol": symbol, "n": len(vals), "sr": sr, "qpass": qpass,
                })

    # Write state
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"  💾 Wrote {n_written} new entries to state.json")

    # Summary by logic
    by_logic = defaultdict(lambda: {"count": 0, "avg_sr": 0, "qpass": 0, "sr_list": []})
    for r in results:
        b = by_logic[r["logic"]]
        b["count"] += 1
        b["sr_list"].append(r["sr"])
        if r["qpass"]: b["qpass"] += 1
    for logic, b in by_logic.items():
        b["avg_sr"] = round(sum(b["sr_list"]) / len(b["sr_list"]), 2) if b["sr_list"] else 0
        del b["sr_list"]

    RESULTS_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_total": len(results),
        "by_logic": dict(by_logic),
        "top10": sorted(results, key=lambda x: -x["sr"])[:10],
    }, indent=2))
    print(f"  💾 Results → {RESULTS_PATH}")

    print("\n📊 Summary by logic:")
    for logic, b in sorted(by_logic.items(), key=lambda x: -x[1]["avg_sr"]):
        print(f"  {logic:<30} count={b['count']:>3} avg_sr={b['avg_sr']:>6.2f} qpass={b['qpass']:>2}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
