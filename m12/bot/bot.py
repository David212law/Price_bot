import json, os, sys
from datetime import datetime, timezone
_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_CORE)
sys.path.insert(0, _CORE)
from calc import regime_label
from m12_strategies import STRATEGIES

CONFIG = os.path.join(_CORE, "config.json")
STATE = os.path.join(_HERE, "state.json")
DATA_DIR = os.path.join(_ROOT, "data")

INITIAL = 10000.0
MAX_POS = 5
POS_PCT = 0.15  # 15% capital per position
FEE = {"TMN": 0.006, "USDT": 0.0026, "GLOBAL": 0.001}
FEE_RT = 0.005  # legacy fee for signal evaluation
KILL = 0.85

def load_market(fname, suffix=None):
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path): return {}
    raw = json.load(open(path))
    out = {}
    for k, v in raw.items():
        if not isinstance(v, (dict, list)) or len(v) < 100: continue
        if suffix:
            if not k.endswith(suffix): continue
            sym = k[:-len(suffix)]
        else: sym = k
        if isinstance(v, dict):
            items = sorted(v.items(), key=lambda kv: kv[0])
            prices = [float(x) for _, x in items]
        else:
            prices = [float(x) for x in v]
        if len(prices) >= 100: out[sym] = prices
    return out

def to_candles(prices, spread=0.005):
    return [{"t": i, "o": p, "h": p*(1+spread), "l": p*(1-spread), "c": p, "v": 1.0}
            for i, p in enumerate(prices)]

def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"capital": INITIAL, "equity": INITIAL, "peak": INITIAL,
            "positions": {}, "history": [], "last_regime": None,
            "kill_switch": False, "created": datetime.now(timezone.utc).isoformat()}

def save_state(s):
    json.dump(s, open(STATE, "w"), indent=2)

def send_bale(msg):
    import urllib.request
    tok, ch = os.environ.get("BALE_BOT_TOKEN",""), os.environ.get("BALE_CHAT_ID","")
    if not tok or not ch: print(f"[BALE] {msg}"); return
    try:
        req = urllib.request.Request(
            f"https://tapi.bale.ai/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": ch, "text": msg}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e: print(f"[BALE] {e}")

def score(symbol, candles, active, fee):
    """Compute weighted signal score for one symbol."""
    total_w = 0.0; total_sig = 0.0
    for sname, weight in active.items():
        if sname not in STRATEGIES: continue
        try:
            trades = STRATEGIES[sname](candles) or []
            if not trades: continue
            last = trades[-1]
            # Only use signals from last few bars
            if last.get("t", 0) < candles[-3]["t"]: continue
            sig = 1.0 if last["ret"] > 0 else -1.0
            total_sig += weight * sig
            total_w += weight
        except Exception:
            continue
    return total_sig / total_w if total_w > 0 else 0.0

def open_position(state, market, sym, price, side, size_pct, fee):
    alloc = state["capital"] * size_pct
    if alloc < 10: return False
    qty = alloc / price
    cost = alloc * (1 + fee / 2)  # half fee on entry
    if cost > state["capital"]: return False
    state["capital"] -= cost
    state["positions"][f"{market}:{sym}"] = {
        "market": market, "symbol": sym, "side": side, "qty": qty,
        "entry": price, "cost": cost, "fee": fee,
        "opened": datetime.now(timezone.utc).isoformat(),
        "sl": price * (0.95 if side == "LONG" else 1.05),
        "tp": price * (1.10 if side == "LONG" else 0.90),
    }
    state["history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "action": "OPEN", "market": market, "symbol": sym, "side": side,
        "price": round(price, 6), "qty": round(qty, 8), "cost": round(cost, 4),
        "pnl": 0,
    })
    send_bale(f"🟢 OPEN {market}:{sym} {side} @ {price:.4f} | cost=${cost:.2f}")
    return True

def close_position(state, key, price, reason):
    pos = state["positions"].get(key)
    if not pos: return False  # ← NO FAKE CLOSE (unlike M31)
    fee = pos["fee"]
    exit_value = pos["qty"] * price * (1 - fee / 2)
    pnl = exit_value - pos["cost"]
    state["capital"] += exit_value
    del state["positions"][key]
    state["history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "action": "CLOSE", "market": pos["market"], "symbol": pos["symbol"],
        "side": pos["side"], "price": round(price, 6),
        "qty": round(pos["qty"], 8), "pnl": round(pnl, 4), "reason": reason,
    })
    send_bale(f"🔴 CLOSE {pos['market']}:{pos['symbol']} @ {price:.4f} | PnL: {pnl:+.4f} ({reason})")
    return True

def update_equity(state, markets_data):
    eq = state["capital"]
    for key, pos in state["positions"].items():
        sym = pos["symbol"]; market = pos["market"]
        prices = markets_data.get(market, {}).get(sym, [])
        if not prices: continue
        cur = prices[-1]
        if pos["side"] == "LONG":
            eq += pos["qty"] * cur * (1 - pos["fee"] / 2)
        else:  # SHORT
            unrealized = pos["cost"] * (2 * pos["entry"] - cur) / pos["entry"]
            eq += max(0, unrealized)
    state["equity"] = round(eq, 2)
    state["peak"] = max(state.get("peak", eq), eq)

def main():
    print("=" * 70); print(" M12 Bot v2 — all symbols, real positions"); print("=" * 70)
    if not os.path.exists(CONFIG): print("No config. Run researcher first."); return
    config = json.load(open(CONFIG))
    state = load_state()
    if state.get("kill_switch"): print("Kill switch active"); return

    # Load ALL markets
    markets_data = {
        "TMN": load_market("wallex_tmn_all.json", "TMN"),
        "USDT": load_market("wallex_usdt_all.json", "USDT"),
        "GLOBAL": load_market("crypto_5y_usd.json"),
    }
    for m, d in markets_data.items(): print(f"[{m}] {len(d)} symbols")

    # Use BTC (TMN) for regime
    if "BTC" not in markets_data["TMN"]: print("BTC missing"); return
    btc = markets_data["TMN"]["BTC"]
    regime = regime_label(btc[-1] / btc[-31] - 1)
    state["last_regime"] = regime
    print(f"\nRegime: {regime}")

    # ── CLOSE: check all existing positions ──
    for key in list(state["positions"].keys()):
        pos = state["positions"][key]
        market, sym = pos["market"], pos["symbol"]
        prices = markets_data.get(market, {}).get(sym, [])
        if not prices: continue
        cur = prices[-1]
        # SL
        if pos["side"] == "LONG" and cur <= pos["sl"]:
            close_position(state, key, pos["sl"], "SL"); continue
        if pos["side"] == "SHORT" and cur >= pos["sl"]:
            close_position(state, key, pos["sl"], "SL"); continue
        # TP
        if pos["side"] == "LONG" and cur >= pos["tp"]:
            close_position(state, key, pos["tp"], "TP"); continue
        if pos["side"] == "SHORT" and cur <= pos["tp"]:
            close_position(state, key, pos["tp"], "TP"); continue

    # ── OPEN: scan all symbols in each market for signals ──
    for market, mdata in markets_data.items():
        active = config.get(market, {}).get(regime, {})
        if not active: print(f"[{market}] no active strategies for {regime}"); continue
        print(f"[{market}] active: {len(active)} strategies")
        fee = FEE[market]
        opened_this_round = 0
        for sym, prices in mdata.items():
            if len(state["positions"]) >= MAX_POS: break
            key = f"{market}:{sym}"
            if key in state["positions"]: continue  # already holding
            candles = to_candles(prices)
            s = score(sym, candles, active, fee)
            if abs(s) < 0.5: continue
            side = "LONG" if s > 0 else "SHORT"
            if open_position(state, market, sym, prices[-1], side, POS_PCT, fee):
                opened_this_round += 1
        if opened_this_round:
            print(f"  -> opened {opened_this_round} new positions")

    # ── Equity ──
    update_equity(state, markets_data)
    if state["equity"] < INITIAL * KILL:
        send_bale(f"🚨 KILL: ${state['equity']:.2f} < ${INITIAL*KILL:.2f}")
        state["kill_switch"] = True

    save_state(state)

    # ── Report ──
    closes = [h for h in state["history"] if h["action"] == "CLOSE"]
    total_pnl = sum(h["pnl"] for h in closes)
    wins = sum(1 for h in closes if h["pnl"] > 0)
    print(f"\n📊 SUMMARY")
    print(f"  Equity: ${state['equity']:.2f} ({((state['equity']/INITIAL-1)*100):+.2f}%)")
    print(f"  Open: {len(state['positions'])} | Closed: {len(closes)} ({wins}W/{len(closes)-wins}L)")
    print(f"  Total PnL (closed): ${total_pnl:+.2f}")
    print(f"  Capital: ${state['capital']:.2f}")

if __name__ == "__main__":
    main()
