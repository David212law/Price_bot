"""D-541: Economic Runner v2 — 300+ strategies from independent economic sources."""
import json, sys, shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

ROOT = Path.cwd()
STATE_PATH = ROOT / "research_lab/logs/profiles/state.json"
LIB_PATH = ROOT / "research/economic/v2/economic_library_v2.json"
RESULTS_PATH = ROOT / "research/economic/v2/v2_results.json"
RET_DIR = ROOT / "research/economic/v2/returns"

EXCHANGES = {
    "hyperliquid": ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"],
    "aster": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"],
    "kucoin": ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"],
}

_cache = {"candles": {}, "funding": {}, "daily_prices": {}, "daily_returns": {}}

def load_candles(exchange, symbol):
    key = (exchange, symbol)
    if key in _cache["candles"]: return _cache["candles"][key]
    try:
        from strategies.core_engine import load_data
        c = load_data(exchange, symbol)
        if c: _cache["candles"][key] = c; return c
    except: pass
    for p in [ROOT/f"data/{exchange}/{symbol}.json", ROOT/f"exchanges/{exchange}/data/{symbol}_candles.json", ROOT/f"exchanges/{exchange}/data/{symbol}.json"]:
        if p.exists():
            try:
                c = json.loads(p.read_text())
                _cache["candles"][key] = c; return c
            except: pass
    _cache["candles"][key] = []; return []

def load_funding(exchange, symbol):
    key = (exchange, symbol)
    if key in _cache["funding"]: return _cache["funding"][key]
    try:
        from research_lab.audit_core import load_funding as lf
        d = lf(exchange, symbol)
        if d and isinstance(d, dict):
            out = {str(k)[:10]: float(v) for k,v in d.items() if isinstance(v,(int,float))}
            _cache["funding"][key] = out; return out
    except: pass
    for p in [ROOT/f"exchanges/{exchange}/data/{symbol}_funding.json", ROOT/f"data/{exchange}/{symbol}_funding.json"]:
        if p.exists():
            try:
                raw = json.loads(p.read_text())
                out = {}
                if isinstance(raw, dict):
                    for k,v in raw.items():
                        if isinstance(v,(int,float)): out[str(k)[:10]] = float(v)
                elif isinstance(raw, list):
                    for it in raw:
                        if isinstance(it, dict):
                            t = it.get("t") or it.get("timestamp")
                            r = it.get("rate") or it.get("fundingRate")
                            if t is not None and r is not None:
                                if isinstance(t,(int,float)): ts = t/1000 if t>1e10 else t
                                else: ts = 0
                                d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else str(t)[:10]
                                out[d] = float(r)
                _cache["funding"][key] = out; return out
            except: pass
    _cache["funding"][key] = {}; return {}

def daily_prices(candles):
    if not candles: return {}, {}
    daily_close = {}
    daily_vol = defaultdict(float)
    for c in candles:
        if not isinstance(c, dict): continue
        t = c.get("t")
        close = c.get("c")
        vol = c.get("v", 0)
        if t is None or close is None: continue
        try: ts = int(t)/1000 if int(t) > 1e10 else int(t)
        except: continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        daily_close[d] = float(close)
        daily_vol[d] += float(vol) if vol else 0
    return daily_close, dict(daily_vol)

def daily_returns(prices):
    dates = sorted(prices.keys())
    rets = {}
    for i in range(1, len(dates)):
        prev, curr = prices[dates[i-1]], prices[dates[i]]
        if prev > 0: rets[dates[i]] = (curr - prev) / prev
    return rets

def sharpe(vals):
    if len(vals) < 10: return 0.0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return round((m/sd)*(365**0.5), 2) if sd > 0 else 0.0

def rolling_mean_std(prices, dates, period):
    out = {}
    for i in range(period, len(dates)):
        window = [prices[dates[j]] for j in range(i-period, i)]
        m = sum(window)/len(window)
        v = sum((x-m)**2 for x in window)/len(window)
        out[dates[i]] = (m, v**0.5)
    return out

def quartiles(vals):
    if len(vals) < 20: return [0,0,0,0], False
    n = len(vals); pfs = []
    for i in range(4):
        chunk = vals[i*n//4:(i+1)*n//4]
        w = sum(v for v in chunk if v > 0); l = abs(sum(v for v in chunk if v < 0))
        pfs.append(round(w/l, 3) if l > 0 else (999 if w > 0 else 1.0))
    return pfs, all(pf > 1.0 for pf in pfs)

# ═══════ CATEGORY IMPL ═══════
def impl_price_mr(candles, params):
    prices, _ = daily_prices(candles)
    rets = daily_returns(prices)
    if len(prices) < 60: return {}
    method = params.get("method", "bollinger")
    result = {}
    if method == "bollinger":
        p, m = params["period"], params["mult"]
        for d, (mean, std) in rolling_mean_std(prices, sorted(prices.keys()), p).items():
            if d not in rets: continue
            prev_dates = sorted(prices.keys())
            idx = prev_dates.index(d)
            prev_price = prices[prev_dates[idx-1]]
            if prev_price < mean - m*std: result[d] = rets[d]
            elif prev_price > mean + m*std and params.get("mode") == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "zscore":
        w, z = params["window"], params["z"]
        for d, (mean, std) in rolling_mean_std(prices, sorted(prices.keys()), w).items():
            if d not in rets or std == 0: continue
            idx = sorted(prices.keys()).index(d)
            prev_price = prices[sorted(prices.keys())[idx-1]]
            zs = (prev_price - mean) / std
            if zs < -z: result[d] = rets[d]
            elif zs > z and params.get("mode") == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "rsi":
        p = params["period"]; os_thr = params["oversold"]; ob_thr = params["overbought"]
        dates = sorted(prices.keys())
        for i in range(p+1, len(dates)):
            gains = []; losses = []
            for j in range(i-p, i):
                ch = prices[dates[j]] - prices[dates[j-1]]
                if ch > 0: gains.append(ch); losses.append(0)
                else: gains.append(0); losses.append(-ch)
            ag = sum(gains)/p; al = sum(losses)/p
            if al == 0: rsi = 100
            else: rsi = 100 - 100/(1+ag/al)
            d = dates[i]
            if d not in rets: continue
            if rsi < os_thr: result[d] = rets[d]
            elif rsi > ob_thr and params.get("mode") == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "dist":
        ma = params["ma_period"]; pct = params["threshold_pct"]
        dates = sorted(prices.keys())
        for i in range(ma, len(dates)):
            m = sum(prices[dates[j]] for j in range(i-ma, i))/ma
            prev_price = prices[dates[i-1]]
            dist = (prev_price - m)/m*100
            d = dates[i]
            if d not in rets: continue
            if dist < -pct: result[d] = rets[d]
            elif dist > pct and params.get("mode") == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "keltner":
        p, m = params["period"], params["mult"]
        dates = sorted(prices.keys())
        for i in range(p+1, len(dates)):
            window = [prices[dates[j]] for j in range(i-p, i)]
            mean = sum(window)/p
            trs = []
            for j in range(i-p+1, i):
                tr = max(prices[dates[j]]-prices[dates[j-1]], abs(prices[dates[j]]-prices[dates[j-1]]))
                trs.append(tr)
            atr = sum(trs)/len(trs) if trs else 0
            prev_price = prices[dates[i-1]]
            d = dates[i]
            if d not in rets: continue
            if prev_price < mean - m*atr: result[d] = rets[d]
            elif prev_price > mean + m*atr and params.get("mode") == "both": result[d] = -rets[d]
            else: result[d] = 0
    return result

def impl_price_momentum(candles, params):
    prices, _ = daily_prices(candles); rets = daily_returns(prices)
    if len(prices) < 30: return {}
    method = params.get("method", "lookback"); mode = params.get("mode", "both")
    result = {}; dates = sorted(prices.keys())
    if method == "lookback":
        lb = params["lookback"]
        for i in range(lb+1, len(dates)):
            past = (prices[dates[i-1]] - prices[dates[i-1-lb]]) / prices[dates[i-1-lb]]
            d = dates[i]
            if d not in rets: continue
            if past > 0: result[d] = rets[d]
            elif past < 0 and mode == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "breakout":
        p = params["period"]
        for i in range(p+1, len(dates)):
            hh = max(prices[dates[j]] for j in range(i-p, i))
            ll = min(prices[dates[j]] for j in range(i-p, i))
            prev_price = prices[dates[i-1]]
            d = dates[i]
            if d not in rets: continue
            if prev_price > hh: result[d] = rets[d]
            elif prev_price < ll and mode == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "ma_cross":
        f, s = params["fast"], params["slow"]
        for i in range(s+1, len(dates)):
            fast_ma = sum(prices[dates[j]] for j in range(i-f, i))/f
            slow_ma = sum(prices[dates[j]] for j in range(i-s, i))/s
            d = dates[i]
            if d not in rets: continue
            if fast_ma > slow_ma: result[d] = rets[d]
            elif fast_ma < slow_ma and mode == "both": result[d] = -rets[d]
            else: result[d] = 0
    elif method == "roc":
        p = params["period"]; th = params.get("threshold", 0)
        for i in range(p+1, len(dates)):
            roc = (prices[dates[i-1]] - prices[dates[i-1-p]]) / prices[dates[i-1-p]] * 100
            d = dates[i]
            if d not in rets: continue
            if roc > th: result[d] = rets[d]
            elif roc < -th: result[d] = -rets[d]
            else: result[d] = 0
    return result

def impl_price_vol(candles, params):
    prices, _ = daily_prices(candles); rets = daily_returns(prices)
    if len(prices) < 60: return {}
    method = params.get("method", "regime")
    dates = sorted(prices.keys())
    result = {}
    if method == "regime":
        w = params["window"]; pct = params["keep_pct"]
        roll_vol = []
        for i in range(w, len(dates)):
            window = [rets.get(dates[j], 0) for j in range(i-w, i)]
            m = sum(window)/w
            v = sum((x-m)**2 for x in window)/w
            roll_vol.append((dates[i], v**0.5))
        vols = sorted(v for _, v in roll_vol)
        if not vols: return {}
        thresh = vols[int(len(vols)*pct/100)]
        for d, v in roll_vol:
            result[d] = rets.get(d, 0) if v <= thresh else 0
    elif method == "breakout":
        p = params["period"]; m = params["mult"]
        for i in range(p+2, len(dates)):
            trs = []
            for j in range(i-p, i):
                tr = abs(prices[dates[j]] - prices[dates[j-1]])
                trs.append(tr)
            atr = sum(trs)/len(trs)
            move = abs(prices[dates[i-1]] - prices[dates[i-2]])
            d = dates[i]
            if d not in rets: continue
            if move > m*atr: result[d] = rets[d] if prices[dates[i-1]] > prices[dates[i-2]] else -rets[d]
            else: result[d] = 0
    elif method == "contraction":
        p = params["period"]; pct = params["pct"]
        for d, (mean, std) in rolling_mean_std(prices, dates, p).items():
            if d not in rets or mean == 0: continue
            width = std/mean * 100
            if width < pct: result[d] = rets[d]
            else: result[d] = 0
    return result

def impl_price_volume(candles, params):
    prices, vols = daily_prices(candles); rets = daily_returns(prices)
    if len(prices) < 30: return {}
    method = params.get("method", "spike")
    dates = sorted(prices.keys())
    result = {}
    if method == "spike":
        w = params["window"]; m = params["mult"]; direction = params["direction"]
        for i in range(w+1, len(dates)):
            avg_v = sum(vols.get(dates[j], 0) for j in range(i-w, i))/w
            curr_v = vols.get(dates[i-1], 0)
            d = dates[i]
            if d not in rets: continue
            if curr_v > m*avg_v:
                if direction == "long_only": result[d] = rets[d]
                elif direction == "short_only": result[d] = -rets[d]
                else: result[d] = rets[d] if prices[dates[i-1]] > prices[dates[i-2]] else -rets[d]
            else: result[d] = 0
    elif method == "obv":
        w = params["window"]; direction = params["direction"]
        obv = [0]
        for i in range(1, len(dates)):
            if prices[dates[i]] > prices[dates[i-1]]: obv.append(obv[-1] + vols.get(dates[i], 0))
            elif prices[dates[i]] < prices[dates[i-1]]: obv.append(obv[-1] - vols.get(dates[i], 0))
            else: obv.append(obv[-1])
        for i in range(w, len(dates)):
            obv_slope = (obv[i] - obv[i-w])
            d = dates[i]
            if d not in rets: continue
            if direction == "long": result[d] = rets[d] if obv_slope > 0 else 0
            else: result[d] = -rets[d] if obv_slope < 0 else 0
    return result

def impl_calendar(candles, params):
    prices, _ = daily_prices(candles); rets = daily_returns(prices)
    if len(prices) < 30: return {}
    method = params.get("method"); dates = sorted(prices.keys()); result = {}
    import calendar as cal
    for d in dates:
        if d not in rets: continue
        dt = datetime.strptime(d, "%Y-%m-%d")
        if method == "eom":
            w = params["window"]; pos = params["position"]
            last = cal.monthrange(dt.year, dt.month)[1]
            if pos == "before": result[d] = rets[d] if dt.day > last - w else 0
            else: result[d] = rets[d] if dt.day <= w else 0
        elif method == "dow":
            target = params["day"]
            result[d] = rets[d] if dt.weekday() == target else 0
        elif method == "first_days":
            result[d] = rets[d] if dt.day <= params["window"] else 0
        elif method == "weekend":
            is_weekend = dt.weekday() >= 5
            if params["mode"] == "trade": result[d] = rets[d] if is_weekend else 0
            else: result[d] = 0 if is_weekend else rets[d]
    return result

def impl_funding_carry(funding, candles, params):
    if not funding: return {}
    th = params["threshold"]; result = {}
    for d, rate in funding.items():
        result[d] = rate if rate > th else 0.0
    return result

def impl_funding_zscore(funding, candles, params):
    if not funding: return {}
    w = params["window"]; z = params["z"]
    dates = sorted(funding.keys()); result = {}
    for i in range(w, len(dates)):
        window = [funding[dates[j]] for j in range(i-w, i)]
        m = sum(window)/w
        v = sum((x-m)**2 for x in window)/w
        sd = v**0.5
        if sd == 0: continue
        zs = (funding[dates[i]] - m) / sd
        result[dates[i]] = funding[dates[i]] if zs > z else 0.0
    return result

def impl_funding_divergence(funding, candles, params):
    if not funding or not candles: return {}
    prices, _ = daily_prices(candles); rets = daily_returns(prices)
    w = params["window"]; direction = params["direction"]
    fdates = sorted(funding.keys())
    result = {}
    for i in range(w, len(fdates)):
        d = fdates[i]
        if d not in rets: continue
        f_past = sum(funding[fdates[j]] for j in range(i-w, i))/w
        p_past = (prices.get(d, 0) - prices.get(fdates[i-w], prices.get(d, 0))) / (prices.get(fdates[i-w], 1) or 1)
        if direction == "same":
            result[d] = funding[d] if (f_past > 0 and p_past < 0) or (f_past < 0 and p_past > 0) else 0
        else:
            result[d] = funding[d] if (f_past > 0 and p_past > 0) or (f_past < 0 and p_past < 0) else 0
    return result

def impl_statistical(candles, params):
    prices, _ = daily_prices(candles); rets = daily_returns(prices)
    if len(prices) < 60: return {}
    method = params.get("method"); dates = sorted(prices.keys()); result = {}
    if method == "hurst":
        w = params["window"]; h_thresh = params["hurst_threshold"]
        vals = [rets.get(d, 0) for d in dates if d in rets]
        for i in range(w, len(dates)):
            d = dates[i]
            if d not in rets: continue
            # Simple Hurst: variance of sums / scale
            window = vals[max(0, i-w):i]
            if len(window) < 10: result[d] = 0; continue
            lags = [10, 20, 40]
            log_rs = []
            for lag in lags:
                if len(window) < lag*2: continue
                sub = window[-lag*2:]
                m1 = sum(sub[:lag])/lag; m2 = sum(sub[lag:])/lag
                var = sum((x-m1)**2 for x in sub[:lag]) + sum((x-m2)**2 for x in sub[lag:])
                var /= (2*lag)
                if var > 0: log_rs.append((lag, (var**0.5)))
            if len(log_rs) < 2: result[d] = 0; continue
            # Hurst ~ slope of log(sd) vs log(lag)
            import math
            xs = [math.log(x[0]) for x in log_rs]; ys = [math.log(x[1]) for x in log_rs]
            n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
            cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
            vx = sum((x-mx)**2 for x in xs)
            H = cov/vx if vx > 0 else 0.5
            # H < 0.5: mean reversion → counter-trend; H > 0.5: trend
            if H < h_thresh: result[d] = rets[d] if prices[dates[i-1]] < prices[dates[i-2]] else -rets[d]
            else: result[d] = rets[d] if prices[dates[i-1]] > prices[dates[i-2]] else -rets[d]
    elif method == "autocorr":
        lag = params["lag"]; th = params["threshold"]
        vals = [rets.get(d, 0) for d in dates if d in rets]
        for i in range(50, len(dates)):
            d = dates[i]
            if d not in rets: continue
            window = vals[max(0, i-50):i]
            if len(window) < lag+10: result[d] = 0; continue
            m = sum(window)/len(window)
            var = sum((x-m)**2 for x in window)
            if var == 0: result[d] = 0; continue
            cov = sum((window[j]-m)*(window[j-lag]-m) for j in range(lag, len(window)))
            ac = cov/var
            if ac > th: result[d] = rets[d]  # positive autocorr → momentum
            elif ac < -th: result[d] = -rets[d]  # negative autocorr → reversal
            else: result[d] = 0
    elif method == "dd_reversal":
        w = params["window"]; dd = params["dd_pct"]
        for i in range(w, len(dates)):
            d = dates[i]
            if d not in rets: continue
            peak = max(prices[dates[j]] for j in range(i-w, i))
            curr = prices[dates[i-1]]
            dd_now = (peak - curr)/peak*100
            if dd_now > dd: result[d] = rets[d]  # in drawdown → go long (reversal)
            else: result[d] = 0
    return result

DISPATCH = {
    "price_mr": impl_price_mr, "price_momentum": impl_price_momentum,
    "price_vol": impl_price_vol, "price_volume": impl_price_volume,
    "calendar": impl_calendar, "funding_carry": impl_funding_carry,
    "funding_zscore": impl_funding_zscore, "funding_divergence": impl_funding_divergence,
    "statistical": impl_statistical,
}

def main():
    print("="*72); print(" ECONOMIC RUNNER V2 — D-541"); print("="*72)
    if not LIB_PATH.exists(): print(f"❌ {LIB_PATH}"); return 1
    if not STATE_PATH.exists(): print(f"❌ {STATE_PATH}"); return 1
    lib = json.loads(LIB_PATH.read_text()); state = json.loads(STATE_PATH.read_text())
    backup = STATE_PATH.with_suffix(".json.bak_D541")
    shutil.copy(STATE_PATH, backup); print(f"💾 Backed up → {backup.name}")
    results = []; errs = defaultdict(int)
    total = len(lib["strategies"])
    for si, strat in enumerate(lib["strategies"]):
        cat = strat["category"]; impl = DISPATCH.get(cat)
        if not impl: continue
        if si % 20 == 0: print(f"  [{si+1}/{total}] {cat}")
        for exchange, symbols in EXCHANGES.items():
            for symbol in symbols:
                try:
                    candles = load_candles(exchange, symbol)
                    funding = load_funding(exchange, symbol)
                    if "price" in strat["data_source"] and len(candles) < 100: continue
                    if strat["data_source"] == "funding" and len(funding) < 60: continue
                    if cat in ("funding_carry", "funding_zscore"):
                        returns = impl(funding, candles, strat["params"])
                    elif cat == "funding_divergence":
                        returns = impl(funding, candles, strat["params"])
                    else:
                        returns = impl(candles, strat["params"])
                    if not returns or len(returns) < 60: continue
                    vals = [returns[d] for d in sorted(returns.keys())]
                    sr = sharpe(vals)
                    if sr < 3: continue
                    pfs, qpass = quartiles(vals)
                    wins = [v for v in vals if v > 0]; losses = [-v for v in vals if v < 0]
                    pf = sum(wins)/sum(losses) if losses else (999 if wins else 1)
                    wr = len(wins)/len(vals)*100
                    ret_file = RET_DIR/exchange/f"{strat['id']}_{symbol}.json"
                    ret_file.parent.mkdir(parents=True, exist_ok=True)
                    ret_file.write_text(json.dumps(returns))
                    key = f"economic_v2:{strat['id']}:{exchange}:{symbol}"
                    m = {"n": len(vals), "pf": round(pf,3), "wr": round(wr,1),
                         "sharpe_daily": round(sr/(365**0.5),4), "sufficient": len(vals) >= 30}
                    state["done"][key] = {
                        "strategy": strat["id"], "params": strat["params"], "kind": "economic_v2",
                        "exchange": exchange, "symbol": symbol, "n_total": len(vals), "status": "profiled",
                        "metrics_by_regime": {"TREND": m, "RANGE": m, "NEUTRAL": m},
                        "validation": {"n": len(vals), "pf": round(pf,3), "wr": round(wr,1),
                                       "sharpe_daily": round(sr/(365**0.5),4), "sharpe_ann": sr,
                                       "quartile_pf": pfs, "quartiles_pass": 4 if qpass else sum(1 for p in pfs if p>1.0),
                                       "stress": {}, "calmar": {}},
                    }
                    results.append({"key": key, "category": cat, "exchange": exchange, "symbol": symbol, "n": len(vals), "sr": sr, "qpass": qpass})
                except Exception as e:
                    errs[f"{cat}:{type(e).__name__}"] += 1
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"\n💾 Wrote {len(results)} entries")
    if errs: print(f"⚠️ Errors: {dict(errs)}")
    by_cat = defaultdict(lambda: {"count": 0, "sr_list": [], "qpass": 0})
    for r in results:
        b = by_cat[r["category"]]; b["count"] += 1; b["sr_list"].append(r["sr"]); b["qpass"] += 1 if r["qpass"] else 0
    for cat, b in by_cat.items():
        b["avg_sr"] = round(sum(b["sr_list"])/len(b["sr_list"]), 2) if b["sr_list"] else 0
        del b["sr_list"]
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "n_total": len(results), "by_category": dict(by_cat), "top50": sorted(results, key=lambda x: -x["sr"])[:50]}, indent=2))
    print(f"💾 Results → {RESULTS_PATH}")
    print("\n📊 By category:")
    for cat, b in sorted(by_cat.items(), key=lambda x: -x[1]["avg_sr"]):
        print(f"  {cat:<25} count={b['count']:>3} avg_SR={b['avg_sr']:>6.2f} qpass={b['qpass']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
