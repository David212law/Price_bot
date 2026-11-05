from collections import defaultdict
import requests
import os
"""D-531: Shared utility functions. Single source of truth."""
import json
from pathlib import Path


def sharpe(vals, periods=365):
    if not vals or len(vals) < 10:
        return 0.0
    m = sum(vals) / len(vals)
    var = sum((x - m) ** 2 for x in vals) / len(vals)
    sd = var ** 0.5
    return (m / sd) * (periods ** 0.5) if sd > 0 else 0.0


def corr(a, b, dates):
    if len(dates) < 30:
        return 0.0
    va = [a.get(d, 0.0) for d in dates]
    vb = [b.get(d, 0.0) for d in dates]
    ma = sum(va) / len(va)
    mb = sum(vb) / len(vb)
    cov = sum((va[i] - ma) * (vb[i] - mb) for i in range(len(va)))
    sa = sum((x - ma) ** 2 for x in va) ** 0.5
    sb = sum((x - mb) ** 2 for x in vb) ** 0.5
    return round(cov / (sa * sb), 3) if sa * sb > 0 else 0.0


def compute_momentum(history, lookback=6):
    if len(history) < lookback * 2:
        return None
    recent = [r["rate"] for r in history[-lookback:]]
    older = [r["rate"] for r in history[:lookback]]
    return sum(recent) / len(recent), sum(older) / len(older), history[-1]["rate"]


def load_returns_file(exchange, strategy, hash_val, symbol):
    p = Path(f"research_lab/logs/profiles/returns_matrices/{exchange}/{strategy}_{hash_val}_{symbol}.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


# === Merged from bale_notifier.py ===
def send_bale(msg):
    token = os.environ.get("BALE_BOT_TOKEN")
    chat_id = os.environ.get("BALE_CHAT_ID")
    if not token or not chat_id: 
        print(f"[BALE] Skipped: {msg[:80]}")
        return
    url = f"https://tapi.bale.ai/bot{token}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
    except Exception as e: print(f"[BALE] Error: {e}")

# === Merged from pooled_returns.py ===
"""D-444: Aggregate returns across all symbols for a strategy."""



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