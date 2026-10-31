"""Core Audit: Trade Unit, Sharpe, DSR"""
import json, os, math
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

def deflated_sharpe(sharpe_obs, n_obs, n_trials):
    if n_trials < 2 or n_obs < 30: return None
    gamma = 0.5772156649
    E_max = (1-gamma)*Z_inv(1-1/n_trials) + gamma*Z_inv(1-1/(n_trials*math.e))
    se = math.sqrt(1/(n_obs-1))
    dsr = Z_cdf((sharpe_obs - E_max) / se)
    return {"sharpe_raw": round(sharpe_obs,3), "E_max_null": round(E_max,3),
            "DSR": round(dsr,4),
            "verdict": "PASS" if dsr > 0.95 else "FAIL" if dsr < 0.5 else "WEAK"}
