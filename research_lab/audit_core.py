"""Core Audit: Trade Unit, Sharpe, DSR"""
import json, os, math, random
from datetime import datetime, timezone
from collections import defaultdict

def normalize_ms(t):
    try: t = int(float(t))
    except: return 0
    if t > 10**14: return t // 1000
    if t > 10**11: return t
    if t > 10**9: return t * 1000
    return t

def extract_rates(data):
    rates = []
    if isinstance(data, dict):
        for k in ["data","results","funding","history"]:
            if k in data and isinstance(data[k], list):
                data = data[k]; break
    if not isinstance(data, list): return rates
    for r in data:
        if not isinstance(r, dict): continue
        rate = None
        for key in ["fundingRate","rate","funding_rate","value","funding"]:
            if key in r:
                try: rate = float(r[key]); break
                except: pass
        t = 0
        for key in ["time","t","fundingTime","timestamp","created_at","timepoint"]:
            if key in r:
                t = normalize_ms(r[key])
                if t > 0: break
        if rate is not None and t > 0:
            rates.append({"t": t, "rate": rate})
    rates.sort(key=lambda x: x["t"])
    return rates

def load_funding(exchange, symbol):
    paths = {
        "aster": [f"data/aster/{symbol}_funding.json", f"data/aster/{symbol}_funding_full.json"],
        "hyperliquid": [f"data/hyperliquid/{symbol.replace('USDT','').replace('XBT','BTC')}_funding.json"],
        "kucoin": [f"exchanges/kucoin/data/{symbol}_funding_full.json", f"exchanges/kucoin/data/{symbol}_funding.json"],
    }
    for p in paths.get(exchange, []):
        if os.path.exists(p):
            try:
                with open(p) as f: return extract_rates(json.load(f))
            except: continue
    return []

def trade_unit_stats(exchange, symbols):
    total_raw = 0
    all_days = set()
    for sym in symbols:
        rates = load_funding(exchange, sym)
        total_raw += len(rates)
        for r in rates:
            day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            all_days.add(day)
    return {"raw": total_raw, "days": len(all_days), "symbols": len(symbols)}

def portfolio_daily_returns(exchange, symbols, leverage=1.0):
    all_days = defaultdict(list)
    for sym in symbols:
        rates = load_funding(exchange, sym)
        sym_daily = defaultdict(float)
        for r in rates:
            day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            sym_daily[day] += r["rate"]
        for day, ret in sym_daily.items():
            all_days[day].append(ret)
    return [(d, sum(all_days[d])/len(all_days[d])*leverage) for d in sorted(all_days.keys())]

def calc_sharpe(daily_rets, ppy=365):
    if len(daily_rets) < 30: return None
    n = len(daily_rets)
    mean = sum(daily_rets) / n
    var = sum((r-mean)**2 for r in daily_rets) / (n-1)
    std = math.sqrt(var)
    if std == 0: return None
    ann_ret = mean * ppy
    ann_vol = std * math.sqrt(ppy)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    return {"n": n, "mean_d_pct": round(mean*100,4), "std_d_pct": round(std*100,4),
            "ann_ret_pct": round(ann_ret*100,2), "ann_vol_pct": round(ann_vol*100,2),
            "sharpe": round(sharpe,3)}

def Z_cdf(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))

def Z_inv(p):
    if p <= 0: return -10
    if p >= 1: return 10
    a = [-39.69683028665376, 220.9460984245205, -275.9285104469687,
         138.3577518672690, -30.66479806614716, 2.506628277459239]
    b = [-54.47609879822406, 161.5858368580409, -155.6989798598866,
         66.80131188771972, -13.28068155288572]
    c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838,
         -2.549732539343734, 4.374664141464968, 2.938163982698783]
    d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416]
    p_low, p_high = 0.02425, 0.97575
    if p < p_low:
        q = math.sqrt(-2*math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= p_high:
        q = p - 0.5; r = q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2*math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

def deflated_sharpe(sharpe_input, n_obs, n_trials, annualized=True,
                       skew=None, kurt=None):
    """
    Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio.
    
    Args:
        sharpe_input: observed Sharpe. If annualized=True (default), this is
                      Sharpe*sqrt(365). If False, per-period.
        n_obs: number of observations
        n_trials: number of independent trials
        annualized: if True, convert to per-period internally
        skew, kurt: optional moments for higher-order correction
    
    Returns:
        {"sharpe_per_period", "sharpe_annualized", "E_max_null",
         "n_obs", "n_trials", "DSR", "verdict"}
    """
    import sys
    if n_trials < 2 or n_obs < 30:
        return None
    if not annualized and abs(sharpe_input) > 5:
        print(f"[WARN] deflated_sharpe: per-period Sharpe={sharpe_input:.2f} "
              f"seems very high — did you pass annualized by mistake?",
              file=sys.stderr)
    
    sr = sharpe_input / math.sqrt(365) if annualized else sharpe_input
    gamma = 0.5772156649
    E_max = (1-gamma)*Z_inv(1-1/n_trials) + gamma*Z_inv(1-1/(n_trials*math.e))
    
    if skew is not None and kurt is not None:
        var_term = max(1 - skew*sr + (kurt-1)/4 * sr**2, 0.01)
        se = math.sqrt(var_term / (n_obs-1))
    else:
        se = math.sqrt(1 / (n_obs-1))
    
    z = (sr - E_max) / se
    dsr = Z_cdf(z)
    return {
        "sharpe_per_period": round(sr, 4),
        "sharpe_annualized": round(sr * math.sqrt(365), 3),
        "E_max_null": round(E_max, 4),
        "n_obs": n_obs,
        "n_trials": n_trials,
        "DSR": round(dsr, 4),
        "verdict": "PASS" if dsr >= 0.95 else "WEAK" if dsr >= 0.80 else "FAIL"
    }


# ═══════════════ D-398: Bootstrap Sharpe CI ═══════════════
def sharpe_bootstrap_ci(daily_rets, ppy=365, n_boot=1000, alpha=0.05, seed=42):
    """Bootstrap 95% CI for Sharpe (per-period and annualized)."""
    n = len(daily_rets)
    if n < 30:
        return None
    def _sharpe(rs):
        m = sum(rs)/len(rs)
        v = sum((r-m)**2 for r in rs)/(len(rs)-1) if len(rs) > 1 else 0
        s = math.sqrt(v)
        return m/s if s > 0 else 0
    sr_obs = _sharpe(daily_rets)
    rng = random.Random(seed)
    sharpes = [_sharpe([daily_rets[rng.randint(0, n-1)] for _ in range(n)])
               for _ in range(n_boot)]
    sharpes.sort()
    lo = sharpes[int(n_boot * alpha/2)]
    hi = sharpes[int(n_boot * (1 - alpha/2))]
    sq = math.sqrt(ppy)
    return {
        "sharpe_per_period": round(sr_obs, 4),
        "sharpe_annualized": round(sr_obs * sq, 3),
        "ci_low_annualized": round(lo * sq, 3),
        "ci_high_annualized": round(hi * sq, 3),
        "significant": lo > 0,
        "n_obs": n,
        "n_boot": n_boot,
    }


# ═══════════════ D-398: Multi-candidate SPA ═══════════════
def spa_multi(candidate_returns_dict, benchmark_returns=None,
              n_boot=1000, block_size=10, seed=42):
    """
    Multi-candidate SPA (Hansen 2005) / Reality Check (White 2000).
    H0: max_k E[mu_k] <= 0. H1: at least one candidate beats benchmark.
    """
    if not candidate_returns_dict:
        return {"error": "no candidates"}
    names = list(candidate_returns_dict.keys())
    min_len = min(len(v) for v in candidate_returns_dict.values())
    if min_len < 30:
        return {"error": f"n={min_len} < 30", "n_obs": min_len}
    
    cands = {k: v[:min_len] for k, v in candidate_returns_dict.items()}
    bench = [0.0]*min_len if benchmark_returns is None else benchmark_returns[:min_len]
    diffs = {k: [cands[k][i] - bench[i] for i in range(min_len)] for k in names}
    
    means, stds = {}, {}
    for k in names:
        d = diffs[k]
        m = sum(d)/len(d)
        v = sum((x-m)**2 for x in d)/(len(d)-1) if len(d) > 1 else 0
        means[k] = m
        stds[k] = math.sqrt(v)
    
    t_stats = {k: (means[k]/stds[k] if stds[k] > 0 else 0) for k in names}
    T_obs = max(0, max(t_stats.values()))
    if T_obs == 0:
        return {"T_SPA": 0.0, "p_value": 1.0, "verdict": "FAIL",
                "n_obs": min_len, "n_candidates": len(names),
                "best_candidate": max(means, key=means.get)}
    
    rng = random.Random(seed)
    centered = {k: [diffs[k][i] - means[k] for i in range(min_len)] for k in names}
    block_size = min(block_size, max(2, min_len // 10))
    
    t_boots = []
    for _ in range(n_boot):
        idx = []
        while len(idx) < min_len:
            start = rng.randint(0, min_len - block_size)
            idx.extend(range(start, start + block_size))
        idx = idx[:min_len]
        boot_t = {k: (sum(centered[k][i] for i in idx)/min_len)/stds[k]
                  if stds[k] > 0 else 0 for k in names}
        t_boots.append(max(0, max(boot_t.values())))
    
    p_value = sum(1 for t in t_boots if t >= T_obs) / n_boot
    verdict = "STRONG_PASS" if p_value < 0.01 else \
              "PASS" if p_value < 0.05 else \
              "WEAK" if p_value < 0.10 else "FAIL"
    best = max(t_stats, key=t_stats.get)
    return {
        "T_SPA": round(T_obs, 4),
        "p_value": round(p_value, 4),
        "verdict": verdict,
        "n_obs": min_len,
        "n_candidates": len(names),
        "best_candidate": best,
        "best_mean_pct": round(means[best]*100, 4),
        "best_t_stat": round(t_stats[best], 4),
        "all_means_pct": {k: round(means[k]*100, 4) for k in names},
    }


# ═══════════════ D-398: Walk-forward folds ═══════════════
def walk_forward_folds(n_obs, n_folds=4):
    """Generate (train_start, train_end, test_start, test_end) — expanding window."""
    if n_obs < n_folds * 20:
        return []
    fold_size = n_obs // n_folds
    folds = []
    for i in range(1, n_folds):
        train_end = i * fold_size
        test_start = train_end
        test_end = min((i+1) * fold_size, n_obs)
        if test_end - test_start >= 10:
            folds.append((0, train_end, test_start, test_end))
    return folds


# ═══════════════ Self-test ═══════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  audit_core.py self-test (D-398)")
    print("=" * 60)
    
    rng = random.Random(42)
    rets = [rng.gauss(0.0005, 0.01) for _ in range(500)]
    m = sum(rets)/len(rets)
    s = math.sqrt(sum((r-m)**2 for r in rets)/(len(rets)-1))
    sr_per = m/s
    
    print(f"\n[Test 1] DSR consistency")
    d1 = deflated_sharpe(sr_per*math.sqrt(365), 500, 54, annualized=True)
    d2 = deflated_sharpe(sr_per, 500, 54, annualized=False)
    print(f"  annualized-input DSR: {d1['DSR']}")
    print(f"  per-period-input DSR: {d2['DSR']}")
    print(f"  Match: {abs(d1['DSR']-d2['DSR']) < 0.001} ← must be True")
    
    print(f"\n[Test 2] Bootstrap CI")
    ci = sharpe_bootstrap_ci(rets, n_boot=500)
    print(f"  annualized Sharpe: {ci['sharpe_annualized']}")
    print(f"  95% CI: [{ci['ci_low_annualized']}, {ci['ci_high_annualized']}]")
    print(f"  significant: {ci['significant']}")
    
    print(f"\n[Test 3] SPA multi")
    strong = [rng.gauss(0.001, 0.01) for _ in range(500)]
    weak = [rng.gauss(0.0001, 0.01) for _ in range(500)]
    sp = spa_multi({"strong": strong, "weak": weak}, n_boot=500)
    print(f"  best: {sp['best_candidate']}, p={sp['p_value']}, verdict={sp['verdict']}")
    
    print(f"\n[Test 4] Walk-forward")
    for f in walk_forward_folds(500, 4):
        print(f"  train=[0,{f[1]}), test=[{f[2]},{f[3]})")
    
    print("\n" + "=" * 60)
    print("  ✅ Self-test complete")
    print("=" * 60)
