"""Shared indicator helpers for strategy library."""
import math

def ema(values, period):
    out = [None] * len(values)
    if len(values) < period: return out
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    out[period - 1] = e
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out

def sma(values, period):
    out = [None] * len(values)
    if len(values) < period: return out
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i-period+1:i+1]) / period
    return out

def atr(candles, period=14):
    out = [None] * len(candles)
    if len(candles) < period + 1: return out
    trs = [0] * len(candles)
    for i in range(1, len(candles)):
        trs[i] = max(candles[i]["h"] - candles[i]["l"],
                     abs(candles[i]["h"] - candles[i-1]["c"]),
                     abs(candles[i]["l"] - candles[i-1]["c"]))
    out[period] = sum(trs[1:period+1]) / period
    for i in range(period + 1, len(candles)):
        out[i] = (out[i-1] * (period - 1) + trs[i]) / period
    return out

def rsi(values, period=14):
    out = [None] * len(values)
    if len(values) < period + 1: return out
    gains = losses = 0
    for i in range(1, period + 1):
        ch = values[i] - values[i-1]
        if ch > 0: gains += ch
        else: losses += abs(ch)
    ag, al = gains / period, losses / period
    out[period] = 100 - 100/(1 + ag/al) if al else 100
    for i in range(period + 1, len(values)):
        ch = values[i] - values[i-1]
        ag = (ag * (period-1) + max(ch, 0)) / period
        al = (al * (period-1) + max(-ch, 0)) / period
        out[i] = 100 - 100/(1 + ag/al) if al else 100
    return out

def bollinger(values, period=20, mult=2.0):
    mid = sma(values, period)
    upper = [None] * len(values)
    lower = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i-period+1:i+1]
        m = mid[i]
        var = sum((x - m) ** 2 for x in window) / period
        std = math.sqrt(var)
        upper[i] = m + mult * std
        lower[i] = m - mult * std
    return upper, mid, lower

def macd(values, fast=12, slow=26, signal=9):
    ema_f = ema(values, fast)
    ema_s = ema(values, slow)
    macd_line = [None] * len(values)
    for i in range(len(values)):
        if ema_f[i] is not None and ema_s[i] is not None:
            macd_line[i] = ema_f[i] - ema_s[i]
    valid = [m for m in macd_line if m is not None]
    sig = ema(valid, signal) if len(valid) >= signal else [None]*len(valid)
    # align
    aligned = [None] * len(values)
    offset = len(values) - len(valid)
    for i, s in enumerate(sig):
        if s is not None: aligned[offset + i] = s
    return macd_line, aligned

def adx(candles, period=14):
    if len(candles) < period * 2: return [None] * len(candles)
    trs, pdms, mdms = [], [], []
    for i in range(1, len(candles)):
        h, l = candles[i]["h"], candles[i]["l"]
        ph, pl, pc = candles[i-1]["h"], candles[i-1]["l"], candles[i-1]["c"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
        up, dn = h-ph, pl-l
        pdms.append(up if (up > dn and up > 0) else 0)
        mdms.append(dn if (dn > up and dn > 0) else 0)
    if len(trs) < period: return [None]*len(candles)
    atr_v = sum(trs[:period])/period
    ps, ms = sum(pdms[:period]), sum(mdms[:period])
    dxs = []
    for i in range(period, len(trs)):
        atr_v = (atr_v*(period-1)+trs[i])/period
        ps = ps - ps/period + pdms[i]
        ms = ms - ms/period + mdms[i]
        pdi = 100*ps/(atr_v*period) if atr_v else 0
        mdi = 100*ms/(atr_v*period) if atr_v else 0
        dx = 100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi) > 0 else 0
        dxs.append(dx)
    if len(dxs) < period: return [None]*len(candles)
    adx_v = sum(dxs[:period])/period
    adx_out = [None] * (period + 1)
    adx_out.append(adx_v)
    for i in range(period, len(dxs)):
        adx_v = (adx_v*(period-1)+dxs[i])/period
        adx_out.append(adx_v)
    return adx_out[:len(candles)]

def supertrend(candles, period=10, mult=3.0):
    atr_v = atr(candles, period)
    st = [None]*len(candles)
    dirs = [1]*len(candles)
    for i in range(period, len(candles)):
        if atr_v[i] is None: continue
        hl2 = (candles[i]["h"]+candles[i]["l"])/2
        ub, lb = hl2+mult*atr_v[i], hl2-mult*atr_v[i]
        if i == period:
            st[i], dirs[i] = ub, 1
            continue
        if candles[i]["c"] > st[i-1]:
            dirs[i] = 1
            st[i] = max(lb, st[i-1]) if dirs[i-1]==1 else lb
        else:
            dirs[i] = -1
            st[i] = min(ub, st[i-1]) if dirs[i-1]==-1 else ub
    return st, dirs

def donchian(candles, period=20):
    upper = [None]*len(candles)
    lower = [None]*len(candles)
    for i in range(period-1, len(candles)):
        window = candles[i-period+1:i+1]
        upper[i] = max(c["h"] for c in window)
        lower[i] = min(c["l"] for c in window)
    return upper, lower

def kama(values, period=10, fast=2, slow=30):
    if len(values) < period + 1: return [None] * len(values)
    out = [None] * len(values); k = values[period-1]; out[period-1] = k
    fs = 2/(fast+1); ss = 2/(slow+1)
    for i in range(period, len(values)):
        ch = abs(values[i] - values[i-period])
        vol = sum(abs(values[j]-values[j-1]) for j in range(i-period+1, i+1))
        er = ch/vol if vol > 0 else 0
        sc = (er*(fs-ss)+ss)**2
        k = k + sc*(values[i]-k); out[i] = k
    return out

def wma(values, period=20):
    if len(values) < period: return [None]*len(values)
    out = [None]*len(values); wsum = period*(period+1)/2
    for i in range(period-1, len(values)):
        s = sum(values[i-period+1+j]*(j+1) for j in range(period))
        out[i] = s/wsum
    return out

def tema(values, period=20):
    e1 = ema(values, period)
    valid1 = [v for v in e1 if v is not None]
    if len(valid1) < period: return [None]*len(values)
    e2_padded = [None]*(len(values)-len(valid1)) + ema(valid1, period)
    e2 = e2_padded
    valid2 = [v for v in e2 if v is not None]
    if len(valid2) < period: return [None]*len(values)
    e3_padded = [None]*(len(values)-len(valid2)) + ema(valid2, period)
    e3 = e3_padded
    out = [None]*len(values)
    for i in range(len(values)):
        if e1[i] is not None and e2[i] is not None and e3[i] is not None:
            out[i] = 3*e1[i] - 3*e2[i] + e3[i]
    return out

def vwma(values, volumes, period=20):
    if len(values) < period: return [None]*len(values)
    out = [None]*len(values)
    for i in range(period-1, len(values)):
        num = sum(values[i-period+1+j]*volumes[i-period+1+j] for j in range(period))
        den = sum(volumes[i-period+1+j] for j in range(period))
        out[i] = num/den if den > 0 else None
    return out

def aroon(candles, period=25):
    if len(candles) < period+1: return [None]*len(candles), [None]*len(candles)
    up = [None]*len(candles); dn = [None]*len(candles)
    for i in range(period, len(candles)):
        window = candles[i-period+1:i+1]
        hi_idx = max(range(len(window)), key=lambda j: window[j]["h"])
        lo_idx = min(range(len(window)), key=lambda j: window[j]["l"])
        up[i] = 100*(hi_idx/period); dn[i] = 100*(lo_idx/period)
    return up, dn

def vortex(candles, period=14):
    if len(candles) < period+1: return [None]*len(candles), [None]*len(candles)
    vp = [None]*len(candles); vm = [None]*len(candles)
    for i in range(period, len(candles)):
        tr_sum = 0; vp_sum = 0; vm_sum = 0
        for j in range(i-period+1, i+1):
            tr = max(candles[j]["h"]-candles[j]["l"], abs(candles[j]["h"]-candles[j-1]["c"]), abs(candles[j]["l"]-candles[j-1]["c"]))
            vp_sum += abs(candles[j]["h"]-candles[j-1]["l"])
            vm_sum += abs(candles[j]["l"]-candles[j-1]["h"])
            tr_sum += tr
        if tr_sum > 0:
            vp[i] = vp_sum/tr_sum; vm[i] = vm_sum/tr_sum
    return vp, vm

def trix(values, period=15):
    e1 = ema(values, period)
    v1 = [x for x in e1 if x is not None]
    if len(v1) < period: return [None]*len(values)
    e2p = [None]*(len(values)-len(v1)) + ema(v1, period)
    e2 = e2p
    v2 = [x for x in e2 if x is not None]
    if len(v2) < period: return [None]*len(values)
    e3 = [None]*(len(values)-len(v2)) + ema(v2, period)
    out = [None]*len(values)
    for i in range(1, len(values)):
        if e3[i] is not None and e3[i-1] is not None and e3[i-1] != 0:
            out[i] = (e3[i]-e3[i-1])/e3[i-1]*100
    return out

def kst(values):
    def roc(vals, n):
        out = [None]*len(vals)
        for i in range(n, len(vals)):
            if vals[i-n] != 0: out[i] = (vals[i]-vals[i-n])/vals[i-n]*100
        return out
    rc1 = roc(values, 10); rc2 = roc(values, 15); rc3 = roc(values, 20); rc4 = roc(values, 30)
    s1 = sma([x if x is not None else 0 for x in rc1], 10)
    s2 = sma([x if x is not None else 0 for x in rc2], 10)
    s3 = sma([x if x is not None else 0 for x in rc3], 10)
    s4 = sma([x if x is not None else 0 for x in rc4], 15)
    out = [None]*len(values)
    for i in range(len(values)):
        if all(x[i] is not None for x in [s1,s2,s3,s4]):
            out[i] = s1[i]*1 + s2[i]*2 + s3[i]*3 + s4[i]*4
    return out

def psar(candles, af_start=0.02, af_step=0.02, af_max=0.2):
    n = len(candles)
    if n < 3: return [None]*n
    out = [None]*n; out[1] = candles[1]["l"]
    bull = True; af = af_start; ep = candles[1]["h"]
    for i in range(2, n):
        sar = out[i-1] + af*(ep-out[i-1])
        if bull:
            if candles[i]["l"] < sar:
                bull = False; sar = ep; ep = candles[i]["l"]; af = af_start
            else:
                if candles[i]["h"] > ep: ep = candles[i]["h"]; af = min(af+af_step, af_max)
        else:
            if candles[i]["h"] > sar:
                bull = True; sar = ep; ep = candles[i]["h"]; af = af_start
            else:
                if candles[i]["l"] < ep: ep = candles[i]["l"]; af = min(af+af_step, af_max)
        out[i] = sar
    return out

def tsi(values, long=25, short=13):
    diffs = [0] + [values[i]-values[i-1] for i in range(1, len(values))]
    absdiffs = [abs(d) for d in diffs]
    e1 = ema(diffs, long); e2 = ema([x if x is not None else 0 for x in e1], short)
    a1 = ema(absdiffs, long); a2 = ema([x if x is not None else 0 for x in a1], short)
    out = [None]*len(values)
    for i in range(len(values)):
        if e2[i] is not None and a2[i] is not None and a2[i] != 0:
            out[i] = 100*e2[i]/a2[i]
    return out

def ultimate_osc(candles):
    if len(candles) < 28: return [None]*len(candles)
    out = [None]*len(candles)
    def bp(i): return candles[i]["c"] - min(candles[i]["l"], candles[i-1]["c"])
    def tr(i): return max(candles[i]["h"], candles[i-1]["c"]) - min(candles[i]["l"], candles[i-1]["c"])
    for i in range(28, len(candles)):
        a1 = sum(bp(j) for j in range(i-6, i+1)) / max(sum(tr(j) for j in range(i-6, i+1)), 1e-9)
        a2 = sum(bp(j) for j in range(i-13, i+1)) / max(sum(tr(j) for j in range(i-13, i+1)), 1e-9)
        a3 = sum(bp(j) for j in range(i-27, i+1)) / max(sum(tr(j) for j in range(i-27, i+1)), 1e-9)
        out[i] = 100*(4*a1 + 2*a2 + a3) / 7
    return out

def awesome_osc(candles):
    closes = [c["c"] for c in candles]
    hl2 = [(c["h"]+c["l"])/2 for c in candles]
    s5 = sma(hl2, 5); s34 = sma(hl2, 34)
    return [(s5[i]-s34[i]) if (s5[i] is not None and s34[i] is not None) else None for i in range(len(candles))]

def coppock(values):
    def roc(vals, n):
        out = [None]*len(vals)
        for i in range(n, len(vals)):
            if vals[i-n] != 0: out[i] = (vals[i]-vals[i-n])/vals[i-n]*100
        return out
    r1 = roc(values, 14); r2 = roc(values, 11)
    combined = [(r1[i]+r2[i]) if (r1[i] is not None and r2[i] is not None) else None for i in range(len(values))]
    wma_in = [x if x is not None else 0 for x in combined]
    return wma(wma_in, 10)

def cci(candles, period=20):
    if len(candles) < period: return [None]*len(candles)
    tp = [(c["h"]+c["l"]+c["c"])/3 for c in candles]
    out = [None]*len(candles)
    for i in range(period-1, len(candles)):
        window = tp[i-period+1:i+1]
        m = sum(window)/period
        md = sum(abs(x-m) for x in window)/period
        out[i] = (tp[i]-m)/(0.015*md) if md > 0 else 0
    return out

def williams_r(candles, period=14):
    if len(candles) < period: return [None]*len(candles)
    out = [None]*len(candles)
    for i in range(period-1, len(candles)):
        h = max(candles[i-period+1+j]["h"] for j in range(period))
        l = min(candles[i-period+1+j]["l"] for j in range(period))
        out[i] = -100*(h-candles[i]["c"])/(h-l) if h > l else 0
    return out

def cmo(values, period=14):
    if len(values) < period+1: return [None]*len(values)
    gains = [0]*len(values); losses = [0]*len(values)
    for i in range(1, len(values)):
        ch = values[i]-values[i-1]
        gains[i] = max(ch, 0); losses[i] = max(-ch, 0)
    out = [None]*len(values)
    for i in range(period, len(values)):
        g = sum(gains[i-period+1:i+1]); l = sum(losses[i-period+1:i+1])
        out[i] = 100*(g-l)/(g+l) if (g+l) > 0 else 0
    return out

def keltner(candles, period=20, mult=2.0):
    closes = [c["c"] for c in candles]
    mid = ema(closes, period)
    at = atr(candles, period)
    up = [None]*len(candles); lo = [None]*len(candles)
    for i in range(len(candles)):
        if mid[i] is not None and at[i] is not None:
            up[i] = mid[i]+mult*at[i]; lo[i] = mid[i]-mult*at[i]
    return up, mid, lo

def chaikin_vol(candles, period=10):
    if len(candles) < period: return [None]*len(candles)
    hl = [c["h"]-c["l"] for c in candles]
    e = ema(hl, period)
    out = [None]*len(candles)
    for i in range(1, len(candles)):
        if e[i] is not None and e[i-1] is not None and e[i-1] != 0:
            out[i] = (e[i]-e[i-1])/e[i-1]*100
    return out

def hist_vol(values, period=20):
    import math
    if len(values) < period+1: return [None]*len(values)
    rets = [0]+[(values[i]-values[i-1])/values[i-1] if values[i-1] != 0 else 0 for i in range(1, len(values))]
    out = [None]*len(values)
    for i in range(period, len(values)):
        w = rets[i-period+1:i+1]
        m = sum(w)/period
        v = sum((x-m)**2 for x in w)/period
        out[i] = math.sqrt(v)*math.sqrt(365)*100
    return out

def atr_pct(candles, period=14):
    at = atr(candles, period)
    return [(at[i]/candles[i]["c"]*100) if (at[i] is not None and candles[i]["c"] != 0) else None for i in range(len(candles))]

def bb_width(values, period=20, mult=2.0):
    up, mid, lo = bollinger(values, period, mult)
    return [((up[i]-lo[i])/mid[i]*100) if (up[i] is not None and lo[i] is not None and mid[i] and mid[i] != 0) else None for i in range(len(values))]

def obv(candles):
    out = [0]*len(candles)
    for i in range(1, len(candles)):
        if candles[i]["c"] > candles[i-1]["c"]: out[i] = out[i-1] + candles[i]["v"]
        elif candles[i]["c"] < candles[i-1]["c"]: out[i] = out[i-1] - candles[i]["v"]
        else: out[i] = out[i-1]
    return out

def mfi(candles, period=14):
    if len(candles) < period+1: return [None]*len(candles)
    tp = [(c["h"]+c["l"]+c["c"])/3 for c in candles]
    pos = [0]*len(candles); neg = [0]*len(candles)
    for i in range(1, len(candles)):
        if tp[i] > tp[i-1]: pos[i] = tp[i]*candles[i]["v"]
        elif tp[i] < tp[i-1]: neg[i] = tp[i]*candles[i]["v"]
    out = [None]*len(candles)
    for i in range(period, len(candles)):
        p = sum(pos[i-period+1:i+1]); n = sum(neg[i-period+1:i+1])
        out[i] = 100 - 100/(1 + p/n) if n > 0 else 100
    return out

def vwap(candles, period=20):
    if len(candles) < period: return [None]*len(candles)
    out = [None]*len(candles)
    for i in range(period-1, len(candles)):
        tp_v = sum(((candles[j]["h"]+candles[j]["l"]+candles[j]["c"])/3)*candles[j]["v"] for j in range(i-period+1, i+1))
        v_sum = sum(candles[j]["v"] for j in range(i-period+1, i+1))
        out[i] = tp_v/v_sum if v_sum > 0 else None
    return out

def ad_line(candles):
    out = [0]*len(candles)
    for i in range(1, len(candles)):
        h_l = candles[i]["h"]-candles[i]["l"]
        if h_l > 0:
            clv = ((candles[i]["c"]-candles[i]["l"]) - (candles[i]["h"]-candles[i]["c"]))/h_l
            out[i] = out[i-1] + clv*candles[i]["v"]
        else: out[i] = out[i-1]
    return out

def cmf(candles, period=20):
    if len(candles) < period: return [None]*len(candles)
    out = [None]*len(candles)
    for i in range(period-1, len(candles)):
        num = 0; den = 0
        for j in range(i-period+1, i+1):
            h_l = candles[j]["h"]-candles[j]["l"]
            if h_l > 0:
                mfm = ((candles[j]["c"]-candles[j]["l"]) - (candles[j]["h"]-candles[j]["c"]))/h_l
                num += mfm*candles[j]["v"]
                den += candles[j]["v"]
        out[i] = num/den if den > 0 else 0
    return out

def force_index(candles, period=13):
    fi = [0]*len(candles)
    for i in range(1, len(candles)):
        fi[i] = (candles[i]["c"]-candles[i-1]["c"])*candles[i]["v"]
    return ema(fi, period)

def vpt(candles):
    out = [0]*len(candles)
    for i in range(1, len(candles)):
        if candles[i-1]["c"] != 0:
            out[i] = out[i-1] + candles[i]["v"]*(candles[i]["c"]-candles[i-1]["c"])/candles[i-1]["c"]
        else: out[i] = out[i-1]
    return out

def zscore(values, period=20):
    if len(values) < period: return [None]*len(values)
    out = [None]*len(values)
    for i in range(period-1, len(values)):
        w = values[i-period+1:i+1]
        m = sum(w)/period
        v = sum((x-m)**2 for x in w)/period
        sd = v**0.5
        out[i] = (values[i]-m)/sd if sd > 0 else 0
    return out

def half_life(values, period=60):
    import math
    if len(values) < period+1: return [None]*len(values)
    out = [None]*len(values)
    for i in range(period, len(values)):
        w = values[i-period:i+1]
        lag = w[:-1]; cur = w[1:]
        ml = sum(lag)/len(lag); mc = sum(cur)/len(cur)
        num = sum((lag[j]-ml)*(cur[j]-mc) for j in range(len(lag)))
        den = sum((lag[j]-ml)**2 for j in range(len(lag)))
        if den > 0:
            beta = num/den
            if 0 < beta < 1:
                out[i] = -math.log(2)/math.log(beta)
    return out
