"""D-511: Live Analyzer — تحلیل داده‌های زنده و مقایسه با Historical.

READ-ONLY. هیچ weight یا state ای تغییر نمی‌کند. فقط گزارش می‌دهد.
"""
import json
import math
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LIVE_CACHE = ROOT / "research_lab" / "logs" / "live_data"
LIVE_REPORTS = ROOT / "research_lab" / "logs" / "live_reports"
STATE_FILE = ROOT / "research_lab" / "logs" / "profiles" / "state.json"

LIVE_CACHE.mkdir(parents=True, exist_ok=True)
LIVE_REPORTS.mkdir(parents=True, exist_ok=True)

BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")


# ═══════════════════════════════════════════════════════════════
# WATCHLIST: استراتژی‌های مهمی که باید پایش شوند
# ═══════════════════════════════════════════════════════════════
WATCHLIST = [
    # (exchange, strategy, symbol, kind, notes)
    ("hyperliquid", "M31", "BTC", "funding", "HL Main + Shadow"),
    ("aster", "M31", "BTCUSDT", "funding", "Aster Main + COMBO"),
    ("kucoin", "M31", "XBTUSDTM", "funding", "KuCoin Main + Combo"),
    ("hyperliquid", "KELTNER_REV", "BNB", "candle", "HL Shadow RP + NEUTRAL"),
    ("aster", "KELTNER_REV", "AVAXUSDT", "candle", "Aster COMBO"),
    ("kucoin", "KELTNER_REV", "ETHUSDTM", "candle", "KuCoin Combo"),
]


# ═══════════════════════════════════════════════════════════════
# Fetch functions (with cache)
# ═══════════════════════════════════════════════════════════════
def _cache_path(exchange, symbol, kind):
    return LIVE_CACHE / f"{exchange}_{symbol}_{kind}.json"


def _cache_age_hours(path):
    if not path.exists():
        return 999
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600


def _load_cached(exchange, symbol, kind):
    p = _cache_path(exchange, symbol, kind)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _save_cache(exchange, symbol, kind, data):
    p = _cache_path(exchange, symbol, kind)
    p.write_text(json.dumps(data, default=str))


# ═══════════════════════════════════════════════════════════════
# Fetch candles (live)
# ═══════════════════════════════════════════════════════════════
def fetch_candles_live(exchange, symbol, days=90):
    """Fetch recent candles from exchange. Cache 6 hours."""
    cached = _load_cached(exchange, symbol, "candles")
    if cached and _cache_age_hours(_cache_path(exchange, symbol, "candles")) < 6:
        return cached

    limit = days * 6  # 4h candles: 6 per day

    if exchange == "hyperliquid":
        # Use HL API
        url = "https://api.hyperliquid.xyz/info"
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = end_ms - (days * 86400 * 1000)
        payload = {"type": "candleSnapshot", "req": {"coin": symbol, "interval": "4h",
                                                       "startTime": start_ms, "endTime": end_ms}}
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                raw = r.json()
                out = [{"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]),
                        "l": float(c["l"]), "c": float(c["c"]), "v": float(c["v"])}
                       for c in raw]
                _save_cache(exchange, symbol, "candles", out)
                return out
        except Exception as e:
            print(f"[FETCH] {exchange}/{symbol}: {e}")
        return []

    if exchange == "aster":
        url = f"https://fapi.asterdex.com/fapi/v1/klines?symbol={symbol}&interval=4h&limit={limit}"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                out = [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                        "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                       for k in r.json()]
                _save_cache(exchange, symbol, "candles", out)
                return out
        except Exception as e:
            print(f"[FETCH] {exchange}/{symbol}: {e}")
        return []

    if exchange == "kucoin":
        url = f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=240&from={int((datetime.now(timezone.utc).timestamp() - days*86400) * 1000)}"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                data = r.json().get("data", [])
                out = [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                        "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
                       for k in data]
                _save_cache(exchange, symbol, "candles", out)
                return out
        except Exception as e:
            print(f"[FETCH] {exchange}/{symbol}: {e}")
        return []

    return []


def fetch_funding_live(exchange, symbol, days=90):
    """Fetch recent funding rates. Cache 6 hours."""
    cached = _load_cached(exchange, symbol, "funding")
    if cached and _cache_age_hours(_cache_path(exchange, symbol, "funding")) < 6:
        return cached

    if exchange == "hyperliquid":
        url = "https://api.hyperliquid.xyz/info"
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = end_ms - (days * 86400 * 1000)
        payload = {"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": end_ms}
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                out = [{"t": int(x["time"]), "rate": float(x["fundingRate"])} for x in r.json()]
                _save_cache(exchange, symbol, "funding", out)
                return out
        except Exception as e:
            print(f"[FETCH] {exchange}/{symbol} funding: {e}")
        return []

    if exchange == "aster":
        url = f"https://fapi.asterdex.com/fapi/v1/fundingRate?symbol={symbol}&limit=500"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                out = [{"t": int(x["fundingTime"]), "rate": float(x["fundingRate"])} for x in r.json()]
                _save_cache(exchange, symbol, "funding", out)
                return out
        except Exception as e:
            print(f"[FETCH] {exchange}/{symbol} funding: {e}")
        return []


    if exchange == "kucoin":
        # Try API first
        start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        url = f"https://api-futures.kucoin.com/api/v1/contract/funding-rate-history?symbol={symbol}&from={start_ms}&to={end_ms}"
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                data = r.json().get("data", {})
                items = data.get("dataList", [])
                out = [{"t": int(x["timepoint"]), "rate": float(x["fundingRate"])} for x in items]
                if out:
                    _save_cache(exchange, symbol, "funding", out)
                    return out
        except Exception as e:
            pass
        # Fallback: use local funding file
        local_path = ROOT / "exchanges" / "kucoin" / "data" / f"{symbol}_funding.json"
        if local_path.exists():
            try:
                raw = json.loads(local_path.read_text())
                if isinstance(raw, dict):
                    items_raw = raw.get("dataList") or raw.get("data") or raw.get("records") or []
                else:
                    items_raw = raw
                out = []
                for x in items_raw:
                    if not isinstance(x, dict):
                        continue
                    t = x.get("timepoint") or x.get("timePoint") or x.get("fundingTime") or x.get("t")
                    rate = x.get("fundingRate") or x.get("rate") or x.get("value")
                    if t is None or rate is None:
                        continue
                    try:
                        out.append({"t": int(t), "rate": float(rate)})
                    except (TypeError, ValueError):
                        continue
                if out:
                    print(f"[FALLBACK] {exchange}/{symbol}: loaded {len(out)} from local file")
                    _save_cache(exchange, symbol, "funding", out)
                    return out
            except Exception as e:
                print(f"[FALLBACK] {exchange}/{symbol}: {e}")
        return []

    return []


# ═══════════════════════════════════════════════════════════════
# Compute metrics
# ═══════════════════════════════════════════════════════════════
def compute_metrics(returns_list):
    """returns_list: list of daily returns (float)."""
    if len(returns_list) < 5:
        return {"n": len(returns_list), "sr": 0, "pf": 0, "wr": 0}
    mean = sum(returns_list) / len(returns_list)
    var = sum((x - mean) ** 2 for x in returns_list) / len(returns_list)
    sd = var ** 0.5
    sr = (mean / sd) * (365 ** 0.5) if sd > 0 else 0
    wins = sum(1 for x in returns_list if x > 0)
    gross_profit = sum(x for x in returns_list if x > 0)
    gross_loss = abs(sum(x for x in returns_list if x < 0))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 999
    wr = 100 * wins / len(returns_list)
    return {"n": len(returns_list), "sr": round(sr, 2), "pf": round(pf, 2),
            "wr": round(wr, 1), "mean": round(mean * 100, 4)}


def funding_to_daily_returns(funding_records):
    """Group funding by day, return list of (date, rate)."""
    by_day = {}
    for r in funding_records:
        day = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        by_day.setdefault(day, 0.0)
        by_day[day] += r["rate"]
    return sorted(by_day.items())


def run_strategy_candles(func, candles, min_bars=200):
    """Run a candle strategy function, return list of trade returns."""
    if len(candles) < min_bars:
        return []
    try:
        trades = func(candles)
        return [t.get("ret", 0.0) for t in trades if isinstance(t, dict)]
    except Exception as e:
        print(f"[RUN] strategy error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# Historical SR (from state.json)
# ═══════════════════════════════════════════════════════════════

def get_historical_sr(state, exchange, strategy, symbol):
    """Best historical SR."""
    if strategy == "M31":
        from research_lab.composer import portfolio_daily_returns, apply_m31_fees, sharpe
        if exchange == "hyperliquid":
            syms = ["BTC","ETH","SOL","BNB","XRP","AVAX"]
        elif exchange == "aster":
            syms = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"]
        elif exchange == "kucoin":
            syms = ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"]
        
        try:
            port = dict(portfolio_daily_returns(exchange, syms))
            fees = apply_m31_fees(port)
            return float(sharpe(list(fees.values())))
        except Exception as e:
            print(f"  [DEBUG] M31 historical error: {e}")
            return None
            
    best = None
    for key, entry in state.get("done", {}).items():
        if not isinstance(entry, dict): continue
        parts = key.split(":")
        if len(parts) < 4: continue
        if parts[0] != exchange or parts[1] != strategy: continue
        if symbol.replace("USDT", "").replace("USDTM", "").replace("M", "") not in parts[3]: continue
        val = entry.get("validation", {})
        sr = val.get("sharpe_ann")
        if sr is not None and (best is None or sr > best): best = float(sr)
    return best


# ═══════════════════════════════════════════════════════════════
# Decay classification
# ═══════════════════════════════════════════════════════════════
def classify_health(live_sr, hist_sr):
    if hist_sr is None or hist_sr <= 0:
        return "UNKNOWN", 0.0
    ratio = live_sr / hist_sr if hist_sr > 0 else 0
    if ratio >= 0.7:
        return "HEALTHY", ratio
    if ratio >= 0.3:
        return "DECAYING", ratio
    return "DEAD", ratio


# ═══════════════════════════════════════════════════════════════
# Main analysis
# ═══════════════════════════════════════════════════════════════
def analyze_one(exchange, strategy, symbol, kind, notes, state):
    """Analyze one watchlist item across 3 windows."""
    result = {"exchange": exchange, "strategy": strategy, "symbol": symbol,
              "kind": kind, "notes": notes, "windows": {}}

    hist_sr = get_historical_sr(state, exchange, strategy, symbol)
    result["historical_sr"] = hist_sr


    if kind == "funding":
        data = fetch_funding_live(exchange, symbol, days=90)
        if not data:
            result["error"] = "no_data"
            return result
        daily = funding_to_daily_returns(data)
        rets = [r for _, r in daily]

        if strategy == "M31":
            # Apply same friction: 0.0067% per day
            fee_per_day = 0.0067 / 100
            rets = [r - fee_per_day for r in rets]

        for window in [7, 30, 90]:
            sub = rets[-window:]
            m = compute_metrics(sub)
            health, ratio = classify_health(m["sr"], hist_sr)
            m["health"] = health
            m["ratio_vs_hist"] = round(ratio, 2)
            result["windows"][window] = m

    elif kind == "candle":
        from strategies.library.registry import get_strategy
        try:
            func, grid, _ = get_strategy(strategy)
        except KeyError:
            result["error"] = f"strategy {strategy} not found"
            return result

        candles = fetch_candles_live(exchange, symbol, days=90)
        if not candles:
            result["error"] = "no_data"
            return result

        # Run on full 90d, then chunk
        all_returns = run_strategy_candles(func, candles)
        for window in [7, 30, 90]:
            # Approx: assume returns are ordered
            sub = all_returns[-window:] if window < len(all_returns) else all_returns
            m = compute_metrics(sub)
            health, ratio = classify_health(m["sr"], hist_sr)
            m["health"] = health
            m["ratio_vs_hist"] = round(ratio, 2)
            result["windows"][window] = m

    return result


def main():
    print("=" * 70)
    print(" LIVE ANALYZER — D-511")
    print("=" * 70)

    if not STATE_FILE.exists():
        print("❌ state.json not found")
        return

    state = json.loads(STATE_FILE.read_text())
    print(f"[LOAD] state.json: {len(state.get('done', {}))} entries")
    print(f"[WATCHLIST] {len(WATCHLIST)} items")
    print()

    results = []
    alerts = []

    for exch, strat, sym, kind, notes in WATCHLIST:
        print(f"--- {exch}/{strat}/{sym} ({notes}) ---")
        r = analyze_one(exch, strat, sym, kind, notes, state)
        if "error" in r:
            print(f"  ⚠ {r['error']}")
            continue

        print(f"  Historical SR: {r['historical_sr']}")
        for w in [7, 30, 90]:
            if w in r["windows"]:
                m = r["windows"][w]
                print(f"  {w}d: SR={m['sr']:>6.2f} n={m['n']:>3} "
                      f"PF={m['pf']:>5.2f} Health={m['health']:>9} (ratio={m['ratio_vs_hist']})")
                if w == 30 and m["health"] in ("DECAYING", "DEAD"):
                    alerts.append(f"⚠️ {exch}/{strat}/{sym}: 30d SR={m['sr']} vs Hist={r['historical_sr']} ({m['health']})")
        results.append(r)
        print()

    # Save report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "watchlist": results,
        "alerts": alerts,
    }
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = LIVE_REPORTS / f"{today}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"[SAVE] {report_path}")

    if alerts:
        print()
        print("=" * 70)
        print(" ALERTS")
        print("=" * 70)
        for a in alerts:
            print(f"  {a}")
        if BALE_TOKEN and BALE_CHAT:
            try:
                msg = "🚨 Live Analyzer Alert:\n" + "\n".join(alerts)
                requests.post(f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage",
                              json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
            except Exception:
                pass

    print()
    print("=" * 70)
    print(" DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
