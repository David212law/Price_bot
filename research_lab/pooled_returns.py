"""D-444: Aggregate returns across all symbols for a strategy."""
import os, json
from collections import defaultdict

RETURNS_DIR = "research_lab/logs/profiles/returns_matrices"

def pooled_returns(exchange, strategy, state):
    files = []
    for key, v in state["done"].items():
        if not isinstance(v, dict): continue
        if v.get("exchange") != exchange: continue
        if v.get("strategy") != strategy: continue
        try: h = key.split(":")[2]
        except: continue
        p = os.path.join(RETURNS_DIR, exchange, f"{strategy}_{h}_{v['symbol']}.json")
        if os.path.exists(p):
            files.append(p)
    if not files: return {}
    sums = defaultdict(float); cnts = defaultdict(int)
    for fp in files:
        try:
            r = json.load(open(fp))
            for d, val in r.items():
                sums[d] += val; cnts[d] += 1
        except: pass
    return {d: sums[d]/cnts[d] for d in sums if cnts[d] > 0}
