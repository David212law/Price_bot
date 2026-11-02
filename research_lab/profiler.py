"""profiler.py — Cascade strategy profiler with regime tagging.
D-399: profiles all strategies × exchanges × symbols with per-regime metrics.
"""
import sys, os, json, math, hashlib, time
from datetime import datetime, timezone
from collections import defaultdict
sys.path.append(os.getcwd())

from strategies.library.registry import list_strategies, get_strategy, expand_param_grid
from strategies.core_engine import load_data, calculate_metrics
from research_lab.audit_core import load_funding, sharpe_bootstrap_ci, calmar_maxdd
from research_lab.regime_core import calc_adx
from research_lab import stress_tests

EXCHANGES = {
    "hyperliquid": ["BTC","ETH","SOL","BNB","XRP","AVAX"],
    "aster": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT"],
    "kucoin": ["XBTUSDTM","ETHUSDTM","SOLUSDTM","BNBUSDTM","XRPUSDTM","AVAXUSDTM"],
}

CONFIG = {
    "l1_min_pf": 0.9, "l1_min_n": 10,
    "l2_min_n_per_regime": 10,
    "l3_strong_pf": 1.2, "l3_min_quartiles_pass": 3,
    "train_split": 0.7,
    "regime_window": 60, "regime_trend": 25, "regime_range": 20,
    "output_dir": "research_lab/logs/profiles",
}

STATE_FILE = os.path.join(CONFIG["output_dir"], "state.json")
RETURNS_DIR = os.path.join(CONFIG["output_dir"], "returns_matrices")
VAL_DIR = os.path.join(CONFIG["output_dir"], "validations")

def _h(name, params):
    return hashlib.md5(f"{name}_{json.dumps(params,sort_keys=True)}".encode()).hexdigest()[:8]

def _ensure(p):
    os.makedirs(p, exist_ok=True)

def compute_regime_series(candles):
    n = len(candles)
    regime = ["UNKNOWN"] * n
    w = CONFIG["regime_window"]
    for i in range(w, n):
        sub = candles[i-w+1:i+1]
        adx = calc_adx(sub, 14)
        if adx is None: regime[i] = "UNKNOWN"
        elif adx > CONFIG["regime_trend"]: regime[i] = "TREND"
        elif adx < CONFIG["regime_range"]: regime[i] = "RANGE"
        else: regime[i] = "NEUTRAL"
    return regime

def run_candle(func, params, candles):
    if not candles or len(candles) < 200: return []
    try: return func(candles, **params) or []
    except: return []

def run_funding(func, params, records):
    if not records or len(records) < 100: return {}
    try: return func(records, **params) or {}
    except: return {}

def tag_candle_trades(trades, candles, regime_series):
    ts_idx = {c["t"]: i for i, c in enumerate(candles)}
    out = []
    for t in trades:
        i = ts_idx.get(t["t"])
        if i is None: continue
        out.append({"t": t["t"], "ret": t["ret"], "regime": regime_series[i]})
    return out

def tag_funding_daily(daily, btc_candles, btc_regime):
    ts_reg = {c["t"]: btc_regime[i] for i, c in enumerate(btc_candles) if i < len(btc_regime)}
    sorted_ts = sorted(ts_reg.keys())
    if not sorted_ts: return []
    out = []
    for day_str, ret in daily.items():
        try:
            dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            ts = int(dt.timestamp() * 1000)
        except: continue
        nearest = None
        for t in sorted_ts:
            if t <= ts: nearest = t
            else: break
        reg = ts_reg.get(nearest, "UNKNOWN") if nearest else "UNKNOWN"
        out.append({"t": ts, "ret": ret, "regime": reg})
    return out

def per_regime_metrics(tagged):
    groups = defaultdict(list)
    for t in tagged: groups[t["regime"]].append(t["ret"])
    out = {}
    for reg, rets in groups.items():
        n = len(rets)
        if n == 0: continue
        wins = [r for r in rets if r > 0]; losses = [r for r in rets if r < 0]
        gp, gl = sum(wins), abs(sum(losses))
        pf = gp/gl if gl > 0 else (99.99 if gp > 0 else 0)
        wr = len(wins)/n*100
        m = sum(rets)/n
        s = math.sqrt(sum((r-m)**2 for r in rets)/(n-1)) if n > 1 else 0
        out[reg] = {
            "n": n, "pf": round(pf,3), "wr": round(wr,1),
            "mean_pct": round(m*100,4),
            "sharpe_daily": round(m/s,4) if s > 0 else 0,
            "sufficient": n >= CONFIG["l2_min_n_per_regime"],
        }
    return out

def to_daily_returns(tagged):
    by_day = defaultdict(list)
    for t in tagged:
        try:
            day = datetime.fromtimestamp(t["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            by_day[day].append(t["ret"])
        except: continue
    return {d: round(sum(v)/len(v), 6) for d, v in sorted(by_day.items())}

def validate_test(func, params, kind, candles_full, funding_full):
    if kind == "candle":
        split = int(len(candles_full) * CONFIG["train_split"])
        test_c = candles_full[split:]
        if len(test_c) < 100: return None
        trades = run_candle(func, params, test_c)
        if len(trades) < 10: return None
        rets = [t["ret"] for t in trades]
    else:
        if not funding_full or len(funding_full) < 100: return None
        test_f = funding_full[int(len(funding_full)*CONFIG["train_split"]):]
        daily = run_funding(func, params, test_f)
        if len(daily) < 10: return None
        rets = list(daily.values())
    n = len(rets)
    wins = [r for r in rets if r > 0]; losses = [r for r in rets if r < 0]
    pf = sum(wins)/abs(sum(losses)) if losses else 99.99
    wr = len(wins)/n*100
    m = sum(rets)/n
    s = math.sqrt(sum((r-m)**2 for r in rets)/(n-1)) if n > 1 else 0
    sd = m/s if s > 0 else 0
    q_size = max(1, n // 4)
    q_pfs = []
    for q in range(4):
        a = q * q_size
        b = (q+1) * q_size if q < 3 else n
        qr = rets[a:b]
        if not qr: continue
        qw = sum(r for r in qr if r > 0); ql = abs(sum(r for r in qr if r < 0))
        q_pfs.append(qw/ql if ql > 0 else (99.99 if qw > 0 else 0))
    q_pass = sum(1 for p in q_pfs if p >= 1.0)
    ci = sharpe_bootstrap_ci(rets, ppy=365)
    # D-406: Calmar / MaxDD
    calmar = calmar_maxdd(rets) or {}

    return {
        "n": n, "pf": round(pf,3), "wr": round(wr,1),
        "sharpe_daily": round(sd,4), "sharpe_ann": round(sd*math.sqrt(365),3),
        "bootstrap_ci": ci,
        "quartile_pf": [round(p,3) for p in q_pfs], "quartiles_pass": q_pass,
        "calmar": calmar,
    }

def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

def main():
    _ensure(CONFIG["output_dir"]); _ensure(RETURNS_DIR); _ensure(VAL_DIR)
    state = {"done": {}, "started": datetime.now(timezone.utc).isoformat()}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: state = json.load(f)
        print(f"[RESUME] {len(state.get('done',{}))} items already processed")
    strategies = list_strategies()
    print(f"[INFO] {len(strategies)} strategies × 3 exchanges × 6 symbols")
    
    print("\n[PREP] precomputing regime series...")
    t0 = time.time()
    regime_cache = defaultdict(dict)
    btc_cache = {}
    for ex, syms in EXCHANGES.items():
        for sym in syms:
            cd = load_data(ex, sym)
            if not cd or len(cd) < 200:
                print(f"  ⚠ {ex}/{sym}: insufficient")
                continue
            regime_cache[ex][sym] = compute_regime_series(cd)
        btc_sym = syms[0]
        btc_cache[ex] = {"candles": load_data(ex, btc_sym), "regime": regime_cache[ex].get(btc_sym, [])}
        print(f"  ✓ {ex}: {len(regime_cache[ex])} symbols")
    print(f"  ({time.time()-t0:.1f}s)")
    
    profiled = validated = rejects = 0
    total = 0
    try:
        for ex, syms in EXCHANGES.items():
            print(f"\n{'='*60}\n  {ex.upper()}\n{'='*60}")
            for name, kind in strategies:
                func, grid, _ = get_strategy(name)
                for params in expand_param_grid(grid):
                    ph = _h(name, params)
                    for sym in syms:
                        key = f"{ex}:{name}:{ph}:{sym}"
                        total += 1
                        if key in state["done"]: continue
                        
                        try:
                            candles = load_data(ex, sym)
                            if not candles or len(candles) < 200:
                                state["done"][key] = "reject:no_data"; rejects += 1; continue
                            train_c = candles[:int(len(candles)*CONFIG["train_split"])]
                            
                            if kind == "candle":
                                trades = run_candle(func, params, train_c)
                                if len(trades) < CONFIG["l1_min_n"]:
                                    state["done"][key] = f"reject:low_n({len(trades)})"; rejects += 1; continue
                                m = calculate_metrics(trades)
                                if m.get("pf",0) < CONFIG["l1_min_pf"]:
                                    state["done"][key] = f"reject:low_pf({m.get('pf',0):.2f})"; rejects += 1; continue
                            else:
                                fund_full = load_funding(ex, sym)
                                if len(fund_full) < 100:
                                    state["done"][key] = "reject:no_funding"; rejects += 1; continue
                                train_f = fund_full[:int(len(fund_full)*CONFIG["train_split"])]
                                daily = run_funding(func, params, train_f)
                                if not daily or len(daily) < CONFIG["l1_min_n"]:
                                    state["done"][key] = "reject:low_n"; rejects += 1; continue
                            
                            if kind == "candle":
                                tagged = tag_candle_trades(trades, candles, regime_cache[ex][sym])
                            else:
                                tagged = tag_funding_daily(daily, btc_cache[ex]["candles"], btc_cache[ex]["regime"])
                            if not tagged:
                                state["done"][key] = "reject:no_tagged"; rejects += 1; continue
                            
                            rm = per_regime_metrics(tagged)
                            dr = to_daily_returns(tagged)
                            rp = os.path.join(RETURNS_DIR, ex, f"{name}_{ph}_{sym}.json")
                            _ensure(os.path.dirname(rp))
                            with open(rp, "w") as f: json.dump(dr, f)
                            
                            entry = {
                                "strategy": name, "params": params, "kind": kind,
                                "exchange": ex, "symbol": sym,
                                "metrics_by_regime": rm, "n_total": len(tagged),
                                "status": "profiled",
                            }
                            
                            strong = [r for r,m in rm.items() if m["pf"] >= CONFIG["l3_strong_pf"] and m["sufficient"]]
                            if strong:
                                val = validate_test(func, params, kind, candles,
                                                    fund_full if kind=="funding" else None)
                                if val:
                                    # D-405: Stress tests
                                    try:
                                        stress = stress_tests.run_all(
                                            name, params, ex, [sym],
                                            val.get("sharpe_ann", 0)
                                        )
                                        val["stress"] = stress
                                    except Exception as _e:
                                        print(f"  [stress err] {name}: {_e}")
                                    entry["validation"] = val
                                    entry["status"] = "validated"
                                    validated += 1
                                    vp = os.path.join(VAL_DIR, ex, f"{name}_{ph}_{sym}.json")
                                    _ensure(os.path.dirname(vp))
                                    with open(vp, "w") as f:
                                        json.dump({"key": key, "validation": val}, f, indent=2)
                            
                            state["done"][key] = entry
                            profiled += 1
                            
                            if (profiled + rejects) % 20 == 0:
                                _save_state(state)
                                print(f"  [{total}] profiled={profiled} validated={validated} rejected={rejects}")
                        except Exception as e:
                            state["done"][key] = f"reject:exception({str(e)[:40]})"
                            rejects += 1
    except KeyboardInterrupt:
        print("\n[INTERRUPT] saving...")
    finally:
        _save_state(state)
        print(f"\n[SAVE] state.json ({len(state['done'])} entries)")
    
    print(f"\n{'='*60}\n  COMPLETE\n{'='*60}")
    print(f"  Profiled: {profiled} | Validated: {validated} | Rejected: {rejects}")
    
    print(f"\n{'='*60}\n  TOP per regime\n{'='*60}")
    print("\n" + "="*80)
    print("  RANKING BY SHARPE (not PF — PF is misleading for funding)")
    print("="*80)
    # D-469: Load blacklist to filter output
    try:
        from research_lab.composer import CONFIG
        blacklist = set(CONFIG.get("blacklist", []))
    except:
        blacklist = set()

    for reg in ["TREND","RANGE","NEUTRAL"]:
        print(f"\n{reg}:")
        cands = []
        for k,v in state["done"].items():
            if not isinstance(v, dict): continue
            st = v.get("strategy", "")
            if st in blacklist: continue # <-- این خط اضافه شد
            m = v["metrics_by_regime"].get(reg)
            if not m or not m["sufficient"]: continue
            sh = m.get("sharpe_daily", 0)
            if sh < 0.15: continue
            fam = FAMILY.get(st, "OTHER")
            cands.append((sh, st, v["exchange"], v["symbol"], m, v.get("validation"), fam))
        cands.sort(reverse=True, key=lambda x: x[0])
        seen_family = set()
        shown = 0
        for sh, st, ex, sy, m, val, fam in cands:
            if fam in seen_family: continue
            seen_family.add(fam)
            v_s = f" VAL:q={val['quartiles_pass']}/4 annSR={val.get('sharpe_ann',0):.1f}" if val else ""
            print(f"  SR={sh:+.3f} PF={m['pf']:6.2f} n={m['n']:3d} | {st:20s}[{fam:10s}] {ex[:4]}/{sy:8s}{v_s}")
            shown += 1
            if shown >= 8: break
        if not cands: print("  (none with sharpe>=0.15)")


FAMILY = {}
for _s in ["M31","M31_EMA","M31_QUANTILE","M31_MOMENTUM","M31_THRESHOLD","M31_SMA"]:
    FAMILY[_s] = "FUNDING_M31"
for _s in ["BOLLINGER","KELTNER_REV","ZSCORE","RSI_REVERSAL","MEAN_REV_SMA","RSI_DIVERGENCE","CONNORS_RSI","RSI_MEAN"]:
    FAMILY[_s] = "MR"
for _s in ["EMA_CROSS","MACD","ADX_TREND","SUPERTREND","DONCHIAN","TRIPLE_EMA","ICHIMOKU","PSAR"]:
    FAMILY[_s] = "TREND"
for _s in ["ROC","RSI_MOMENTUM","MOMENTUM_EMA","MOMENTUM_SMA","DUAL_MOMENTUM","PRICE_MOMENTUM","ELDER_IMPULSE"]:
    FAMILY[_s] = "MOMENTUM"
for _s in ["BB_SQUEEZE","KELTNER_SQUEEZE","ATR_BREAKOUT","NR_BREAKOUT","VOL_DONCHIAN"]:
    FAMILY[_s] = "VOL"
for _s in ["OBV","MFI","VWAP","VOLUME_BREAKOUT"]:
    FAMILY[_s] = "VOLUME"
for _s in ["PRICE_SMA"]:
    FAMILY[_s] = "PRICE"

if __name__ == "__main__":
    main()
