"""D-542: Economic Researcher v3 — OI + L/S + On-chain signals"""
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import urllib.request

ROOT = Path.cwd()
CACHE = ROOT / "data/external"
STATE_PATH = ROOT / "research_lab/logs/profiles/state.json"
RESULTS_PATH = ROOT / "research/economic/v3/v3_results.json"
RET_DIR = ROOT / "research/economic/v3/returns"
RET_MATRIX = ROOT / "research_lab/logs/profiles/returns_matrices"

SYMBOL_MAP = {
    "hyperliquid": {"BTC":"BTC","ETH":"ETH","SOL":"SOL","BNB":"BNB","XRP":"XRP","AVAX":"AVAX"},
    "aster": {"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT","BNB":"BNBUSDT","XRP":"XRPUSDT","AVAX":"AVAXUSDT"},
    "kucoin": {"BTC":"XBTUSDTM","ETH":"ETHUSDTM","SOL":"SOLUSDTM","BNB":"BNBUSDTM","XRP":"XRPUSDTM","AVAX":"AVAXUSDTM"},
}
BN_SYMS = ["BTC","ETH","SOL","BNB","XRP","AVAX"]

def _http(url, t=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(r, timeout=t) as resp:
            return json.loads(resp.read().decode())
    except: return None

def _cache(name, data=None):
    p = CACHE / name
    if data is None:
        if p.exists():
            try: return json.loads(p.read_text())
            except: pass
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))

def fetch_bn_oi(sym):
    c = _cache(f"oi_{sym}.json")
    if c: return c
    d = _http(f"https://fapi.binance.com/futures/data/openInterestHist?symbol={sym}USDT&period=1d&limit=500")
    if not d: _cache(f"oi_{sym}.json",{}); return {}
    out = {}
    for it in d:
        try:
            ts = int(it["timestamp"])/1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            out[dt] = float(it["sumOpenInterest"])
        except: pass
    _cache(f"oi_{sym}.json", out); return out

def fetch_bn_ls(sym):
    c = _cache(f"ls_{sym}.json")
    if c: return c
    d = _http(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={sym}USDT&period=1d&limit=500")
    if not d: _cache(f"ls_{sym}.json",{}); return {}
    out = {}
    for it in d:
        try:
            ts = int(it["timestamp"])/1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            out[dt] = float(it["longShortRatio"])
        except: pass
    _cache(f"ls_{sym}.json", out); return out

def fetch_onchain(metric):
    c = _cache(f"onchain_{metric}.json")
    if c: return c
    d = _http(f"https://api.blockchain.info/charts/{metric}?timespan=2years&format=json")
    if not d or "values" not in d: _cache(f"onchain_{metric}.json",{}); return {}
    out = {}
    for it in d["values"]:
        try:
            ts = int(it["x"])
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            out[dt] = float(it["y"])
        except: pass
    _cache(f"onchain_{metric}.json", out); return out

def rolling_z_pct(vals, i, w=30):
    if i < w: return 0, 0.5
    win = vals[i-w:i]
    m = sum(win)/len(win)
    v = sum((x-m)**2 for x in win)/len(win)
    sd = v**0.5
    z = (vals[i]-m)/sd if sd > 0 else 0
    pct = sum(1 for x in win if x < vals[i])/len(win)
    return z, pct

def build_signals(series, lookback=20):
    """From dict {date: val}, build {date: {'v','roc','z','pct','accel'}}"""
    dates = sorted(series.keys())
    vals = [series[d] for d in dates]
    out = {}
    for i in range(lookback+5, len(dates)):
        d = dates[i]
        z, pct = rolling_z_pct(vals, i)
        roc = (vals[i]-vals[i-lookback])/abs(vals[i-lookback]) if vals[i-lookback] != 0 else 0
        accel = 0
        if i >= 10 and vals[i-lookback] != 0 and vals[i-lookback*2] != 0:
            r1 = (vals[i]-vals[i-lookback])/abs(vals[i-lookback])
            r2 = (vals[i-lookback]-vals[i-lookback*2])/abs(vals[i-lookback*2])
            accel = r1-r2
        out[d] = {"v":vals[i],"roc":roc,"z":z,"pct":pct,"accel":accel}
    return out

def load_returns(exchange, symbol):
    sym = SYMBOL_MAP[exchange].get(symbol)
    if not sym: return {}
    f = RET_MATRIX / exchange / f"M31_EMA_078447f0_{sym}.json"
    if not f.exists():
        # try any M31_EMA for this symbol
        candidates = list((RET_MATRIX/exchange).glob(f"M31_EMA_*_{sym}.json"))
        if not candidates: return {}
        f = candidates[0]
    try: return json.loads(f.read_text())
    except: return {}

def sharpe(vals):
    if len(vals)<10: return 0.0
    m = sum(vals)/len(vals)
    v = sum((x-m)**2 for x in vals)/len(vals)
    sd = v**0.5
    return round((m/sd)*(365**0.5),2) if sd>0 else 0.0

def quartile_pf(vals):
    if len(vals)<20: return [0,0,0,0], False
    n = len(vals); pfs=[]
    for i in range(4):
        ch = vals[i*n//4:(i+1)*n//4]
        w = sum(v for v in ch if v>0); l = abs(sum(v for v in ch if v<0))
        pfs.append(round(w/l,3) if l>0 else (999 if w>0 else 1))
    return pfs, all(p>1.0 for p in pfs)

def corr(a,b,dates):
    va=[a[d] for d in dates]; vb=[b[d] for d in dates]
    ma=sum(va)/len(va); mb=sum(vb)/len(vb)
    cov=sum((va[i]-ma)*(vb[i]-mb) for i in range(len(va)))
    sa=sum((x-ma)**2 for x in va)**0.5; sb=sum((x-mb)**2 for x in vb)**0.5
    return round(cov/(sa*sb),3) if sa*sb>0 else 0

# ═══ STRATEGY GENERATORS ═══
def gen_strategies():
    s = []
    # 8 OI logics
    for lb in [5,10,20,30]:
        for th in [0.0,0.05]:
            s.append({"id":f"oi_roc_pos_{lb}_{th}","fam":"oi","logic":"oi_roc_pos","params":{"lb":lb,"th":th}})
            s.append({"id":f"oi_roc_neg_{lb}_{th}","fam":"oi","logic":"oi_roc_neg","params":{"lb":lb,"th":th}})
    for lb in [10,20,30,50]:
        s.append({"id":f"oi_div_{lb}_up","fam":"oi","logic":"oi_div_up","params":{"lb":lb}})
        s.append({"id":f"oi_div_{lb}_dn","fam":"oi","logic":"oi_div_dn","params":{"lb":lb}})
    for th in [0.05,0.10,0.90,0.95]:
        s.append({"id":f"oi_ext_{th}","fam":"oi","logic":"oi_extreme","params":{"th":th}})
    for th in [1.5,2.0,-1.5,-2.0]:
        s.append({"id":f"oi_z_{th}","fam":"oi","logic":"oi_zscore","params":{"th":th}})
    for th in [0.7,0.8,-0.7,-0.8]:
        s.append({"id":f"oi_acc_{th}","fam":"oi","logic":"oi_accel","params":{"th":th}})
    for q in [1,2,3,4]:
        s.append({"id":f"oi_q_{q}","fam":"oi","logic":"oi_quartile","params":{"q":q}})
    # 7 L/S logics
    for th in [2.0,2.5,3.0,3.5]:
        s.append({"id":f"ls_ext_hi_{th}","fam":"ls","logic":"ls_ext_hi","params":{"th":th}})
    for th in [0.5,0.4,0.3,0.2]:
        s.append({"id":f"ls_ext_lo_{th}","fam":"ls","logic":"ls_ext_lo","params":{"th":th}})
    for th in [0.05,0.10,0.15,0.20]:
        s.append({"id":f"ls_trend_{th}","fam":"ls","logic":"ls_trend","params":{"th":th}})
    for th in [1.5,2.0,-1.5,-2.0]:
        s.append({"id":f"ls_z_{th}","fam":"ls","logic":"ls_zscore","params":{"th":th}})
    for th in [0.05,0.10,-0.05,-0.10]:
        s.append({"id":f"ls_acc_{th}","fam":"ls","logic":"ls_accel","params":{"th":th}})
    for lb in [10,20,30,50]:
        s.append({"id":f"ls_div_{lb}_up","fam":"ls","logic":"ls_div_up","params":{"lb":lb}})
        s.append({"id":f"ls_div_{lb}_dn","fam":"ls","logic":"ls_div_dn","params":{"lb":lb}})
    for th in [0.10,0.20,0.80,0.90]:
        s.append({"id":f"ls_pct_{th}","fam":"ls","logic":"ls_pct","params":{"th":th}})
    # 6 onchain logics
    for th in [-0.05,0.05,0.10,0.20]:
        s.append({"id":f"addr_mom_{th}","fam":"onchain","logic":"addr_mom","params":{"th":th}})
        s.append({"id":f"tx_mom_{th}","fam":"onchain","logic":"tx_mom","params":{"th":th}})
    for th in [1.5,2.0,-1.5,-2.0]:
        s.append({"id":f"addr_z_{th}","fam":"onchain","logic":"addr_z","params":{"th":th}})
        s.append({"id":f"tx_z_{th}","fam":"onchain","logic":"tx_z","params":{"th":th}})
    for th in [-0.05,0.05,0.10,0.20]:
        s.append({"id":f"hash_mom_{th}","fam":"onchain","logic":"hash_mom","params":{"th":th}})
    for lb in [10,20,30,50]:
        s.append({"id":f"ochain_div_{lb}_up","fam":"onchain","logic":"ochain_div_up","params":{"lb":lb}})
        s.append({"id":f"ochain_div_{lb}_dn","fam":"onchain","logic":"ochain_div_dn","params":{"lb":lb}})
    # combos
    for combo in ["hi_hi","hi_lo","lo_hi","lo_lo"]:
        s.append({"id":f"oi_ls_{combo}","fam":"combo","logic":"oi_ls","params":{"c":combo}})
        s.append({"id":f"oi_oc_{combo}","fam":"combo","logic":"oi_oc","params":{"c":combo}})
        s.append({"id":f"ls_oc_{combo}","fam":"combo","logic":"ls_oc","params":{"c":combo}})
        s.append({"id":f"multi_{combo}","fam":"combo","logic":"multi","params":{"c":combo}})
    return s

def apply_signal(returns, sigs, prices, strat):
    """Apply strategy logic → daily returns dict."""
    logic = strat["logic"]; p = strat["params"]
    out = {}
    for d in sorted(returns.keys()):
        if d not in sigs: continue
        sig = sigs[d]
        prev = sorted([x for x in prices.keys() if x < d])
        if not prev: continue
        prev_d = prev[-1]
        if prev_d not in sigs: continue
        psig = sigs[prev_d]
        r = returns[d]
        pos = 0
        if logic == "oi_roc_pos":
            if psig["roc"] > p["th"]: pos = 1
        elif logic == "oi_roc_neg":
            if psig["roc"] < -p["th"]: pos = -1
        elif logic == "oi_div_up":
            if psig["roc"] > 0 and prices[d] < prices[prev_d]: pos = 1
        elif logic == "oi_div_dn":
            if psig["roc"] > 0 and prices[d] < prices[prev_d]: pos = -1
        elif logic == "oi_extreme":
            if p["th"] < 0.5 and psig["pct"] < p["th"]: pos = 1
            elif p["th"] > 0.5 and psig["pct"] > p["th"]: pos = -1
        elif logic == "oi_zscore":
            if p["th"] > 0 and psig["z"] > p["th"]: pos = -1
            elif p["th"] < 0 and psig["z"] < p["th"]: pos = 1
        elif logic == "oi_accel":
            if p["th"] > 0 and psig["accel"] > p["th"]: pos = 1
            elif p["th"] < 0 and psig["accel"] < p["th"]: pos = -1
        elif logic == "oi_quartile":
            q = int(psig["pct"]*4)
            if p["q"] == 4 and q >= 3: pos = -1
            elif p["q"] == 1 and q == 0: pos = 1
        elif logic == "ls_ext_hi":
            if psig["v"] > p["th"]: pos = -1
        elif logic == "ls_ext_lo":
            if psig["v"] < p["th"]: pos = 1
        elif logic == "ls_trend":
            if psig["roc"] > p["th"]: pos = 1
        elif logic == "ls_zscore":
            if p["th"] > 0 and psig["z"] > p["th"]: pos = -1
            elif p["th"] < 0 and psig["z"] < p["th"]: pos = 1
        elif logic == "ls_accel":
            if p["th"] > 0 and psig["accel"] > p["th"]: pos = 1
            elif p["th"] < 0 and psig["accel"] < p["th"]: pos = -1
        elif logic == "ls_div_up":
            if psig["roc"] > 0 and prices[d] < prices[prev_d]: pos = 1
        elif logic == "ls_div_dn":
            if psig["roc"] > 0 and prices[d] < prices[prev_d]: pos = -1
        elif logic == "ls_pct":
            if p["th"] < 0.5 and psig["pct"] < p["th"]: pos = -1
            elif p["th"] > 0.5 and psig["pct"] > p["th"]: pos = 1
        elif logic in ("addr_mom","tx_mom","hash_mom"):
            if psig["roc"] > p["th"]: pos = 1
            elif psig["roc"] < -p["th"]: pos = -1
        elif logic in ("addr_z","tx_z"):
            if p["th"] > 0 and psig["z"] > p["th"]: pos = -1
            elif p["th"] < 0 and psig["z"] < p["th"]: pos = 1
        elif logic == "ochain_div_up":
            if psig["roc"] > 0 and prices[d] < prices[prev_d]: pos = 1
        elif logic == "ochain_div_dn":
            if psig["roc"] > 0 and prices[d] < prices[prev_d]: pos = -1
        out[d] = r * pos
    return out

def main():
    print("="*72); print(" D-542: Economic Researcher v3 — OI/LS/Onchain"); print("="*72)
    # Fetch data
    print("\n[1] Fetching data...")
    oi_data = {}; ls_data = {}
    for sym in BN_SYMS:
        oi_data[sym] = fetch_bn_oi(sym)
        ls_data[sym] = fetch_bn_ls(sym)
        print(f"  {sym}: OI={len(oi_data[sym])}d, L/S={len(ls_data[sym])}d")
    onchain = {
        "addr": fetch_onchain("n-unique-addresses"),
        "tx": fetch_onchain("n-transactions"),
        "hash": fetch_onchain("hash-rate"),
    }
    for k,v in onchain.items():
        print(f"  onchain_{k}: {len(v)}d")
    # Build signals per symbol
    print("\n[2] Building signals...")
    oi_sigs = {sym: build_signals(oi_data[sym], 20) for sym in BN_SYMS if oi_data[sym]}
    ls_sigs = {sym: build_signals(ls_data[sym], 20) for sym in BN_SYMS if ls_data[sym]}
    oc_sigs = {k: build_signals(v, 20) for k,v in onchain.items() if v}
    # Prices (BTC proxy for on-chain strategies)
    def load_candles(exch, sym):
        sym_map = SYMBOL_MAP[exch].get(sym)
        if not sym_map: return []
        try:
            from strategies.core_engine import load_data
            return load_data(exch, sym_map) or []
        except: return []
    def daily_prices(candles):
        if not candles: return {}
        out = {}
        for c in candles:
            if not isinstance(c,dict): continue
            t = c.get("t"); cl = c.get("c")
            if t is None or cl is None: continue
            try: ts = int(t)/1000 if int(t)>1e10 else int(t)
            except: continue
            d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            out[d] = float(cl)
        return out
    # Generate strategies
    strategies = gen_strategies()
    print(f"\n[3] Generated {len(strategies)} strategies")
    # Backtest
    print("\n[4] Backtesting...")
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"done":{}}
    import shutil
    if STATE_PATH.exists():
        shutil.copy(STATE_PATH, str(STATE_PATH)+".bak_D542")
    results = []
    RET_DIR.mkdir(parents=True, exist_ok=True)
    for si, strat in enumerate(strategies):
        if si % 20 == 0: print(f"  [{si+1}/{len(strategies)}] {strat['logic']}")
        fam = strat["fam"]
        for exch in ["hyperliquid","aster","kucoin"]:
            syms = BN_SYMS if fam != "onchain" else ["BTC"]
            for sym in syms:
                rets = load_returns(exch, sym)
                if len(rets) < 100: continue
                if fam == "oi" and sym not in oi_sigs: continue
                if fam == "ls" and sym not in ls_sigs: continue
                if fam == "onchain":
                    sigs = oc_sigs.get("addr", {})
                elif fam == "combo":
                    if strat["logic"] == "oi_ls" and (sym not in oi_sigs or sym not in ls_sigs): continue
                    sigs = oi_sigs.get(sym, {})
                else:
                    sigs = (oi_sigs if fam=="oi" else ls_sigs).get(sym, {})
                if not sigs: continue
                candles = load_candles(exch, sym)
                prices = daily_prices(candles)
                if len(prices) < 100: continue
                strat_rets = apply_signal(rets, sigs, prices, strat)
                if len(strat_rets) < 60: continue
                vals = [strat_rets[d] for d in sorted(strat_rets.keys())]
                sr = sharpe(vals)
                if sr < 2: continue  # lower threshold for v3 (initial screen)
                pfs, qpass = quartile_pf(vals)
                wins = [v for v in vals if v>0]; losses = [-v for v in vals if v<0]
                pf = sum(wins)/sum(losses) if losses else (999 if wins else 1)
                wr = len(wins)/len(vals)*100
                ret_file = RET_DIR/exch/f"{strat['id']}_{sym}.json"
                ret_file.parent.mkdir(parents=True, exist_ok=True)
                ret_file.write_text(json.dumps(strat_rets))
                key = f"economic_v3:{strat['id']}:{exch}:{sym}"
                m = {"n":len(vals),"pf":round(pf,3),"wr":round(wr,1),"sharpe_daily":round(sr/(365**0.5),4),"sufficient":len(vals)>=30}
                state["done"][key] = {"strategy":strat["id"],"params":strat["params"],"kind":"economic_v3","exchange":exch,"symbol":sym,"n_total":len(vals),"status":"profiled","metrics_by_regime":{"TREND":m,"RANGE":m,"NEUTRAL":m},"validation":{"n":len(vals),"pf":round(pf,3),"wr":round(wr,1),"sharpe_daily":round(sr/(365**0.5),4),"sharpe_ann":sr,"quartile_pf":pfs,"quartiles_pass":4 if qpass else sum(1 for x in pfs if x>1),"stress":{},"calmar":{}}}
                results.append({"key":key,"family":fam,"logic":strat["logic"],"exchange":exch,"symbol":sym,"n":len(vals),"sr":sr,"qpass":qpass})
    # Save state
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"\n💾 Saved {len(results)} results")
    # Artifact detection
    print("\n[5] Artifact detection...")
    m31_rets = {}
    for exch in ["hyperliquid","aster","kucoin"]:
        sym = SYMBOL_MAP[exch]["BTC"]
        for f in (RET_MATRIX/exch).glob(f"M31_EMA_*_{sym}.json"):
            try: m31_rets[exch] = json.loads(f.read_text()); break
            except: pass
    verified = []
    for r in results:
        ret_file = RET_DIR/r["exchange"]/f"{r['logic']}.json"
        # try find
        matched = list((RET_DIR/r["exchange"]).glob(f"*{r['logic']}*_{r['symbol']}.json"))
        if not matched: 
            # Get from state
            continue
        try: strat_rets = json.loads(matched[0].read_text())
        except: continue
        if r["exchange"] not in m31_rets: continue
        common = sorted(set(strat_rets.keys()) & set(m31_rets[r["exchange"]].keys()))
        if len(common) < 60: continue
        c = corr(strat_rets, m31_rets[r["exchange"]], common)
        split = int(len(common)*0.7)
        te = common[split:]
        sr_test = sharpe([strat_rets[d] for d in te])
        m31_test = sharpe([m31_rets[r["exchange"]][d] for d in te])
        imp = (sr_test/m31_test - 1)*100 if m31_test > 0 else 0
        verified.append({**r, "corr_m31":c, "imp":round(imp,1), "sr_test":sr_test})
    # Classify
    by_fam = defaultdict(lambda: {"real":0,"correlated":0,"no_improve":0})
    real_list = []
    for v in verified:
        f = by_fam[v["family"]]
        if abs(v["corr_m31"]) > 0.7: f["correlated"] += 1
        elif v["imp"] < 10: f["no_improve"] += 1
        else:
            f["real"] += 1
            real_list.append(v)
    # Save
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_results": len(results), "n_verified": len(verified),
        "by_family": dict(by_fam),
        "real_candidates": sorted(real_list, key=lambda x:-x["imp"])[:30],
        "all_verified": verified[:100],
    }, indent=2))
    print(f"\n💾 Saved to {RESULTS_PATH}")
    print("\n" + "="*72)
    print(" SUMMARY")
    print("="*72)
    for fam, v in by_fam.items():
        print(f"  {fam:<12}: real={v['real']:>3} corr={v['correlated']:>3} no_imp={v['no_improve']:>3}")
    print(f"\n  REAL CANDIDATES: {len(real_list)}")
    if real_list:
        print("\n  Top real:")
        for r in sorted(real_list, key=lambda x:-x["imp"])[:15]:
            print(f"    {r['logic']:<20} {r['exchange']:<12} {r['symbol']:<6} sr={r['sr']:>6.2f} imp={r['imp']:>+6.1f}% corr={r['corr_m31']:>+6.3f}")

if __name__ == "__main__":
    main()
