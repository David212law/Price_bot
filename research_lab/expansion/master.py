"""
Expansion Master — همه چیز در یک اجرا.
Usage: python3 -m research_lab.expansion.master --stage [infra|strategies|verify|all]
"""
import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent.parent

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

# ═══════════════════════════════════════════════════════════════════
# PHASE 1: 34 NEW INDICATORS
# ═══════════════════════════════════════════════════════════════════

NEW_INDICATORS = {}

NEW_INDICATORS["kama"] = '''
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
'''

NEW_INDICATORS["wma"] = '''
def wma(values, period=20):
    if len(values) < period: return [None]*len(values)
    out = [None]*len(values); wsum = period*(period+1)/2
    for i in range(period-1, len(values)):
        s = sum(values[i-period+1+j]*(j+1) for j in range(period))
        out[i] = s/wsum
    return out
'''

NEW_INDICATORS["tema"] = '''
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
'''

NEW_INDICATORS["vwma"] = '''
def vwma(values, volumes, period=20):
    if len(values) < period: return [None]*len(values)
    out = [None]*len(values)
    for i in range(period-1, len(values)):
        num = sum(values[i-period+1+j]*volumes[i-period+1+j] for j in range(period))
        den = sum(volumes[i-period+1+j] for j in range(period))
        out[i] = num/den if den > 0 else None
    return out
'''

NEW_INDICATORS["aroon"] = '''
def aroon(candles, period=25):
    if len(candles) < period+1: return [None]*len(candles), [None]*len(candles)
    up = [None]*len(candles); dn = [None]*len(candles)
    for i in range(period, len(candles)):
        window = candles[i-period+1:i+1]
        hi_idx = max(range(len(window)), key=lambda j: window[j]["h"])
        lo_idx = min(range(len(window)), key=lambda j: window[j]["l"])
        up[i] = 100*(hi_idx/period); dn[i] = 100*(lo_idx/period)
    return up, dn
'''

NEW_INDICATORS["vortex"] = '''
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
'''

NEW_INDICATORS["trix"] = '''
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
'''

NEW_INDICATORS["kst"] = '''
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
'''

NEW_INDICATORS["psar"] = '''
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
'''

NEW_INDICATORS["tsi"] = '''
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
'''

NEW_INDICATORS["ultimate_osc"] = '''
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
'''

NEW_INDICATORS["awesome_osc"] = '''
def awesome_osc(candles):
    closes = [c["c"] for c in candles]
    hl2 = [(c["h"]+c["l"])/2 for c in candles]
    s5 = sma(hl2, 5); s34 = sma(hl2, 34)
    return [(s5[i]-s34[i]) if (s5[i] is not None and s34[i] is not None) else None for i in range(len(candles))]
'''

NEW_INDICATORS["coppock"] = '''
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
'''

NEW_INDICATORS["cci"] = '''
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
'''

NEW_INDICATORS["williams_r"] = '''
def williams_r(candles, period=14):
    if len(candles) < period: return [None]*len(candles)
    out = [None]*len(candles)
    for i in range(period-1, len(candles)):
        h = max(candles[i-period+1+j]["h"] for j in range(period))
        l = min(candles[i-period+1+j]["l"] for j in range(period))
        out[i] = -100*(h-candles[i]["c"])/(h-l) if h > l else 0
    return out
'''

NEW_INDICATORS["cmo"] = '''
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
'''

NEW_INDICATORS["keltner"] = '''
def keltner(candles, period=20, mult=2.0):
    closes = [c["c"] for c in candles]
    mid = ema(closes, period)
    at = atr(candles, period)
    up = [None]*len(candles); lo = [None]*len(candles)
    for i in range(len(candles)):
        if mid[i] is not None and at[i] is not None:
            up[i] = mid[i]+mult*at[i]; lo[i] = mid[i]-mult*at[i]
    return up, mid, lo
'''

NEW_INDICATORS["chaikin_vol"] = '''
def chaikin_vol(candles, period=10):
    if len(candles) < period: return [None]*len(candles)
    hl = [c["h"]-c["l"] for c in candles]
    e = ema(hl, period)
    out = [None]*len(candles)
    for i in range(1, len(candles)):
        if e[i] is not None and e[i-1] is not None and e[i-1] != 0:
            out[i] = (e[i]-e[i-1])/e[i-1]*100
    return out
'''

NEW_INDICATORS["hist_vol"] = '''
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
'''

NEW_INDICATORS["atr_pct"] = '''
def atr_pct(candles, period=14):
    at = atr(candles, period)
    return [(at[i]/candles[i]["c"]*100) if (at[i] is not None and candles[i]["c"] != 0) else None for i in range(len(candles))]
'''

NEW_INDICATORS["bb_width"] = '''
def bb_width(values, period=20, mult=2.0):
    up, mid, lo = bollinger(values, period, mult)
    return [((up[i]-lo[i])/mid[i]*100) if (up[i] is not None and lo[i] is not None and mid[i] and mid[i] != 0) else None for i in range(len(values))]
'''

NEW_INDICATORS["obv"] = '''
def obv(candles):
    out = [0]*len(candles)
    for i in range(1, len(candles)):
        if candles[i]["c"] > candles[i-1]["c"]: out[i] = out[i-1] + candles[i]["v"]
        elif candles[i]["c"] < candles[i-1]["c"]: out[i] = out[i-1] - candles[i]["v"]
        else: out[i] = out[i-1]
    return out
'''

NEW_INDICATORS["mfi"] = '''
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
'''

NEW_INDICATORS["vwap"] = '''
def vwap(candles, period=20):
    if len(candles) < period: return [None]*len(candles)
    out = [None]*len(candles)
    for i in range(period-1, len(candles)):
        tp_v = sum(((candles[j]["h"]+candles[j]["l"]+candles[j]["c"])/3)*candles[j]["v"] for j in range(i-period+1, i+1))
        v_sum = sum(candles[j]["v"] for j in range(i-period+1, i+1))
        out[i] = tp_v/v_sum if v_sum > 0 else None
    return out
'''

NEW_INDICATORS["ad_line"] = '''
def ad_line(candles):
    out = [0]*len(candles)
    for i in range(1, len(candles)):
        h_l = candles[i]["h"]-candles[i]["l"]
        if h_l > 0:
            clv = ((candles[i]["c"]-candles[i]["l"]) - (candles[i]["h"]-candles[i]["c"]))/h_l
            out[i] = out[i-1] + clv*candles[i]["v"]
        else: out[i] = out[i-1]
    return out
'''

NEW_INDICATORS["cmf"] = '''
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
'''

NEW_INDICATORS["force_index"] = '''
def force_index(candles, period=13):
    fi = [0]*len(candles)
    for i in range(1, len(candles)):
        fi[i] = (candles[i]["c"]-candles[i-1]["c"])*candles[i]["v"]
    return ema(fi, period)
'''

NEW_INDICATORS["vpt"] = '''
def vpt(candles):
    out = [0]*len(candles)
    for i in range(1, len(candles)):
        if candles[i-1]["c"] != 0:
            out[i] = out[i-1] + candles[i]["v"]*(candles[i]["c"]-candles[i-1]["c"])/candles[i-1]["c"]
        else: out[i] = out[i-1]
    return out
'''

NEW_INDICATORS["zscore"] = '''
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
'''

NEW_INDICATORS["half_life"] = '''
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
'''

def add_indicators():
    log("PHASE 1: Adding 30 new indicators...")
    path = ROOT / "strategies/library/indicators.py"
    content = path.read_text()
    added, skipped = [], []
    for name, code in NEW_INDICATORS.items():
        if f"def {name}(" in content:
            skipped.append(name); continue
        content += "\n" + code.strip() + "\n"
        added.append(name)
    try:
        ast.parse(content)
    except SyntaxError as e:
        log(f"  ✗ SYNTAX ERROR: {e}"); sys.exit(1)
    path.write_text(content)
    log(f"  ✓ Added {len(added)} indicators, skipped {len(skipped)} existing")
    return added

# ═══════════════════════════════════════════════════════════════════
# PHASE 2: Family registry
# ═══════════════════════════════════════════════════════════════════

FAMILIES_MAP = {
    # Trend
    "EMA_CROSS":"trend","MACD":"trend","ADX_TREND":"trend","SUPERTREND":"trend",
    "DONCHIAN":"trend","TRIPLE_EMA":"trend","ICHIMOKU":"trend","PSAR":"trend",
    "PRICE_SMA":"trend",
    # MR
    "BOLLINGER":"mr","KELTNER_REV":"mr","ZSCORE":"mr","RSI_REVERSAL":"mr",
    "MEAN_REV_SMA":"mr","RSI_DIVERGENCE":"mr","CONNORS_RSI":"mr","RSI_MEAN":"mr",
    # Momentum
    "ROC":"momentum","RSI_MOMENTUM":"momentum","MOMENTUM_EMA":"momentum",
    "MOMENTUM_SMA":"momentum","DUAL_MOMENTUM":"momentum","PRICE_MOMENTUM":"momentum",
    "ELDER_IMPULSE":"momentum",
    # Vol
    "BB_SQUEEZE":"vol","KELTNER_SQUEEZE":"vol","ATR_BREAKOUT":"vol",
    "NR_BREAKOUT":"vol","VOL_DONCHIAN":"vol",
    # Volume
    "OBV":"volume","MFI":"volume","VWAP":"volume","VOLUME_BREAKOUT":"volume",
    # Funding
    "M31":"funding","M31_EMA":"funding","M31_QUANTILE":"funding",
    "M31_MOMENTUM":"funding","M31_THRESHOLD":"funding","M31_SMA":"funding",
    "FUNDING_MEAN_REV":"funding",
    # Exotic
    "PAIRS_RELATIVE":"mr","PAIRS_TRADING":"mr","LOW_VOL_CARRY":"vol",
    "MTF_CONFIRMATION":"trend","WEEKLY_PIVOT":"vol",
}

def add_family_registry():
    log("PHASE 2: Adding family registry...")
    path = ROOT / "strategies/library/families.py"
    lines = ['"""Strategy → family mapping (D-507)."""', "STRATEGY_FAMILY = {"]
    for name, fam in sorted(FAMILIES_MAP.items()):
        lines.append(f'    "{name}": "{fam}",')
    lines.append("}")
    lines.append("")
    lines.append("FAMILY_STRATEGIES = {}")
    lines.append("for _s, _f in STRATEGY_FAMILY.items():")
    lines.append("    FAMILY_STRATEGIES.setdefault(_f, []).append(_s)")
    content = "\n".join(lines) + "\n"
    ast.parse(content)
    path.write_text(content)
    log(f"  ✓ families.py with {len(FAMILIES_MAP)} strategies")

# ═══════════════════════════════════════════════════════════════════
# PHASE 3: Family-based DSR
# ═══════════════════════════════════════════════════════════════════

FAMILY_DSR_CODE = '''

# ═══════════════════════════════════════════════════════════════════
# D-507: Family-based DSR (N_trials per family, not global)
# ═══════════════════════════════════════════════════════════════════

_FAMILY_N_TRIALS_DEFAULT = {
    "trend": 500, "mr": 500, "momentum": 500,
    "vol": 500, "volume": 500, "funding": 500,
}

def deflated_sharpe_family(sharpe_ann, n_obs, family, family_n_trials=None):
    """Family-based DSR: N_trials per family."""
    if family_n_trials is None:
        family_n_trials = _FAMILY_N_TRIALS_DEFAULT.get(family, 500)
    return deflated_sharpe(sharpe_ann, n_obs, family_n_trials, annualized=True)
'''

def add_family_dsr():
    log("PHASE 3: Adding family-based DSR to audit_core...")
    path = ROOT / "research_lab/audit_core.py"
    content = path.read_text()
    if "def deflated_sharpe_family" in content:
        log("  SKIP (already exists)"); return
    content += FAMILY_DSR_CODE
    ast.parse(content)
    path.write_text(content)
    log("  ✓ deflated_sharpe_family added")

# ═══════════════════════════════════════════════════════════════════
# PHASE 4: Discovery Lifecycle
# ═══════════════════════════════════════════════════════════════════

LIFECYCLE_CODE = '''"""D-507: Discovery lifecycle — Candidate → Confirmed → Paper-Ready → Paper-Active."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
LIFECYCLE_FILE = ROOT / "research_lab" / "logs" / "discovery_lifecycle.json"

STATES = ["candidate", "confirmed", "paper_ready", "paper_active"]

def load_lifecycle():
    if LIFECYCLE_FILE.exists():
        try: return json.loads(LIFECYCLE_FILE.read_text())
        except: pass
    return {"strategies": {}}

def save_lifecycle(data):
    LIFECYCLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIFECYCLE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def transition(strategy_key, new_state, reason=""):
    if new_state not in STATES:
        raise ValueError(f"Invalid state: {new_state}")
    data = load_lifecycle()
    entry = data["strategies"].get(strategy_key, {})
    old = entry.get("state", "none")
    entry["state"] = new_state
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    entry.setdefault("transitions", []).append({
        "from": old, "to": new_state, "at": entry["updated_at"], "reason": reason
    })
    data["strategies"][strategy_key] = entry
    save_lifecycle(data)
    print(f"[LIFECYCLE] {strategy_key}: {old} → {new_state} ({reason})")

def list_by_state(state):
    data = load_lifecycle()
    return [k for k, v in data["strategies"].items() if v.get("state") == state]
'''

def add_lifecycle():
    log("PHASE 4: Adding discovery lifecycle...")
    path = ROOT / "research_lab/discovery_lifecycle.py"
    if path.exists():
        log("  SKIP (exists)"); return
    ast.parse(LIFECYCLE_CODE)
    path.write_text(LIFECYCLE_CODE)
    log("  ✓ discovery_lifecycle.py")

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["infra", "strategies", "verify", "all"], default="all")
    args = ap.parse_args()

    log(f"EXPANSION MASTER — stage={args.stage}")

    if args.stage in ("infra", "all"):
        add_indicators()
        add_family_registry()
        add_family_dsr()
        add_lifecycle()

    if args.stage in ("verify", "all"):
        log("PHASE verify: import check")
        sys.path.insert(0, str(ROOT))
        try:
            from strategies.library.indicators import kama, wma, aroon, keltner, zscore
            log("  ✓ indicators import OK")
            from research_lab.audit_core import deflated_sharpe_family
            log("  ✓ family DSR import OK")
            from strategies.library.families import STRATEGY_FAMILY
            log(f"  ✓ families: {len(STRATEGY_FAMILY)} strategies mapped")
        except Exception as e:
            log(f"  ✗ Import error: {e}"); sys.exit(1)

    log("DONE")

if __name__ == "__main__":
    main()
