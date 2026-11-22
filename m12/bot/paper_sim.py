import json, os, sys, argparse, hashlib
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_CORE)
sys.path.insert(0, _CORE)

from calc import regime_label, cost_basis, pnl_long, pnl_short, position_qty, sl_tp, should_kill
from m12_strategies import STRATEGIES

DATA_DIR = os.path.join(_ROOT, "data")
CONFIG = os.path.join(_CORE, "config.json")

DEFAULT_FEE = {"TMN": 0.006, "USDT": 0.0026, "GLOBAL": 0.001}

def _calc_sharpe(equity_curve):
    """Daily Sharpe from equity curve (each step = 1 day)."""
    if len(equity_curve) < 3: return 0.0
    rets = [(equity_curve[i] / equity_curve[i-1] - 1)
            for i in range(1, len(equity_curve)) if equity_curve[i-1] > 0]
    if len(rets) < 2: return 0.0
    import statistics
    m = statistics.mean(rets)
    s = statistics.stdev(rets)
    if s == 0: return 0.0
    return round(m / s * (365 ** 0.5), 3)

SPREAD = 0.005

def load_market(fname, suffix=None, min_len=300, limit_symbols=None):
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        return {}
    raw = json.load(open(path))
    out = {}
    for k, v in raw.items():
        if not isinstance(v, (dict, list)) or len(v) < min_len:
            continue
        if suffix:
            if not k.endswith(suffix):
                continue
            sym = k[:-len(suffix)]
        else:
            sym = k
        if isinstance(v, dict):
            items = sorted(v.items(), key=lambda kv: kv[0])
            prices = [float(x) for _, x in items]
        else:
            prices = [float(x) for x in v]
        if len(prices) >= min_len:
            out[sym] = prices
    if limit_symbols:
        # keep most liquid by length
        keep = dict(sorted(out.items(), key=lambda kv: -len(kv[1]))[:limit_symbols])
        return keep
    return out

def to_candles(prices, spread=SPREAD):
    return [{"t": i, "o": p, "h": p * (1 + spread), "l": p * (1 - spread), "c": p, "v": 1.0}
            for i, p in enumerate(prices)]

def config_hash():
    try:
        with open(CONFIG) as f:
            return hashlib.md5(f.read().encode()).hexdigest()[:8]
    except Exception:
        return "unknown"

def score(active, candles):
    """Weighted ensemble score: sign based on last trade ret (>0 -> +1 else -1)."""
    total_w, total_sig = 0.0, 0.0
    for sname, weight in active.items():
        fn = STRATEGIES.get(sname)
        if not fn or weight == 0:
            continue
        try:
            trades = fn(candles) or []
            if not trades:
                continue
            last = trades[-1]
            # only accept if strategy produced a trade in last few bars (match bot)
            if last.get("t", 0) < candles[-3]["t"]:
                continue
            sig = 1.0 if last.get("ret", 0) > 0 else -1.0
            total_sig += weight * sig
            total_w += weight
        except Exception:
            continue
    return total_sig / total_w if total_w > 0 else 0.0

def run_papersim(start_idx, end_idx, markets_data, config, fee_map, max_pos=5, pos_pct=0.15,
                  sl_pct=0.05, tp_pct=0.10, kill=0.85, initial_capital=10000.0):
    # State
    state = {
        "capital": initial_capital,
        "equity": initial_capital, "_equity_curve": [],
        "peak": initial_capital,
        "positions": {},   # key -> pos
        "history": [],
        "kill_switch": False,
    }

    # Must have TMN BTC for regime
    btc_series = markets_data["TMN"].get("BTC")
    if not btc_series:
        raise RuntimeError("BTC missing in TMN market data")

    for t in range(max(50, start_idx), end_idx):
        # Regime from BTC (same as bot)
        if t - 30 < 0:
            continue
        regime = regime_label(btc_series[t] / btc_series[t - 30] - 1)

        # CLOSE check (SL/TP)
        for key in list(state["positions"].keys()):
            pos = state["positions"][key]
            market, sym = pos["market"], pos["symbol"]
            series = markets_data.get(market, {}).get(sym)
            if not series or t >= len(series):
                continue
            cur = series[t]

            if pos["side"] == "LONG":
                if cur <= pos["sl"]:
                    exit_price = pos["sl"]
                    pnl = pnl_long(pos["qty"], pos["entry"], exit_price, pos["fee"])
                    state["capital"] += pos["cost"] + pnl
                    del state["positions"][key]
                    state["history"].append({"t": t, "action": "CLOSE", "market": market, "symbol": sym,
                                              "side": pos["side"], "price": exit_price, "pnl": pnl, "reason": "SL"})
                elif cur >= pos["tp"]:
                    exit_price = pos["tp"]
                    pnl = pnl_long(pos["qty"], pos["entry"], exit_price, pos["fee"])
                    state["capital"] += pos["cost"] + pnl
                    del state["positions"][key]
                    state["history"].append({"t": t, "action": "CLOSE", "market": market, "symbol": sym,
                                              "side": pos["side"], "price": exit_price, "pnl": pnl, "reason": "TP"})
            else:  # SHORT
                if cur >= pos["sl"]:
                    exit_price = pos["sl"]
                    pnl = pnl_short(pos["qty"], pos["entry"], exit_price, pos["fee"])
                    state["capital"] += pos["cost"] + pnl
                    del state["positions"][key]
                    state["history"].append({"t": t, "action": "CLOSE", "market": market, "symbol": sym,
                                              "side": pos["side"], "price": exit_price, "pnl": pnl, "reason": "SL"})
                elif cur <= pos["tp"]:
                    exit_price = pos["tp"]
                    pnl = pnl_short(pos["qty"], pos["entry"], exit_price, pos["fee"])
                    state["capital"] += pos["cost"] + pnl
                    del state["positions"][key]
                    state["history"].append({"t": t, "action": "CLOSE", "market": market, "symbol": sym,
                                              "side": pos["side"], "price": exit_price, "pnl": pnl, "reason": "TP"})

        # OPEN check (same scan order as bot)
        for market, syms in markets_data.items():
            active = config.get(market, {}).get(regime, {})
            if not active:
                continue
            fee = fee_map.get(market, 0.0)

            for sym, series in syms.items():
                if len(state["positions"]) >= max_pos:
                    break
                key = f"{market}:{sym}"
                if key in state["positions"]:
                    continue
                if t >= len(series):
                    continue
                # Build candles up to t inclusive
                prices_slice = series[: t + 1]
                if len(prices_slice) < 60:
                    continue
                candles = to_candles(prices_slice)

                s = score(active, candles)
                if abs(s) < 0.5:
                    continue
                side = "LONG" if s > 0 else "SHORT"

                # open at current close
                price = series[t]
                qty = position_qty(state["capital"], pos_pct, price)
                if qty == 0:
                    continue
                cost = cost_basis(qty, price)
                if cost > state["capital"]:
                    continue

                sl, tp = sl_tp(price, side, sl_pct=sl_pct, tp_pct=tp_pct)

                state["capital"] -= cost
                state["positions"][key] = {
                    "market": market,
                    "symbol": sym,
                    "side": side,
                    "qty": qty,
                    "entry": price,
                    "cost": cost,
                    "fee": fee,
                    "sl": sl,
                    "tp": tp,
                    "opened": t,
                }
                state["history"].append({"t": t, "action": "OPEN", "market": market, "symbol": sym,
                                          "side": side, "price": price, "qty": qty, "cost": cost})

        # Equity mark-to-market (simple mimic of bot update)
        eq = state["capital"]
        for key, pos in state["positions"].items():
            market, sym = pos["market"], pos["symbol"]
            series = markets_data.get(market, {}).get(sym, [])
            if not series or t >= len(series):
                continue
            cur = series[t]
            if pos["side"] == "LONG":
                eq += pos["qty"] * cur * (1 - pos["fee"] / 2)
            else:
                # rough unrealized, mimic bot's style
                entry_value = pos["qty"] * pos["entry"]
                unreal = entry_value * (pos["entry"] - cur) / pos["entry"]
                eq += pos["cost"] + unreal

        state["equity"] = round(eq, 2)
        state["_equity_curve"].append(state["equity"])
        state["peak"] = max(state["peak"], state["equity"])

        if should_kill(state["equity"], initial_capital, kill):
            state["kill_switch"] = True
            break

    closes = [h for h in state["history"] if h["action"] == "CLOSE"]
    total_pnl = sum(h["pnl"] for h in closes)
    wins = sum(1 for h in closes if h["pnl"] > 0)
    dd = None
    if state["history"]:
        # compute max drawdown from equity snapshots not stored -> approximate using peak/min from positions closes not ideal
        dd = (state["equity"] / state["peak"] - 1) if state["peak"] else 0.0

    return {
        "regime_start": regime_label(btc_series[start_idx] / btc_series[start_idx - 30] - 1) if start_idx >= 31 else None,
        "end_t": t if 't' in locals() else end_idx,
        "equity": state["equity"],
        "_equity_curve_count": len(state.get("_equity_curve", [])),
        "peak": state["peak"],
        "kill": state["kill_switch"],
        "open_final": len(state["positions"]),
        "closed_trades": len(closes),
        "wins": wins,
        "losses": len(closes) - wins,
        "total_pnl": round(total_pnl, 4),
        "dd_ratio": dd,
        "sharpe": _calc_sharpe(state.get("_equity_curve", [])),
        "pnl_per_day": round(total_pnl / max(1, end_idx - start_idx), 4),
        "window_days": end_idx - start_idx,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=90, help="number of latest indices to simulate")
    ap.add_argument("--fee_mode", type=str, default="0", choices=["0", "default"], help="fee=0 for equivalence Gate")
    ap.add_argument("--max_pos", type=int, default=5)
    ap.add_argument("--pos_pct", type=float, default=0.15)
    args = ap.parse_args()

    config = json.load(open(CONFIG))

    # Load markets (historical)
    tmn = load_market("wallex_tmn_all.json", "TMN", min_len=300, limit_symbols=185)
    usdt = load_market("wallex_usdt_all.json", "USDT", min_len=300, limit_symbols=185)
    global_m = load_market("crypto_5y_usd.json", None, min_len=300, limit_symbols=13)

    markets_data = {"TMN": tmn, "USDT": usdt, "GLOBAL": global_m}

    # Determine common end index by BTC series length
    btc = markets_data["TMN"].get("BTC")
    if not btc:
        raise RuntimeError("BTC missing")
    end_idx = min(len(btc) - 1, 4000)
    start_idx = max(31, end_idx - args.window)

    fee_map = DEFAULT_FEE.copy()
    if args.fee_mode == "0":
        fee_map = {"TMN": 0.0, "USDT": 0.0, "GLOBAL": 0.0}

    res = run_papersim(
        start_idx=start_idx,
        end_idx=end_idx,
        markets_data=markets_data,
        config=config,
        fee_map=fee_map,
        max_pos=args.max_pos,
        pos_pct=args.pos_pct,
        kill=0.85,
        initial_capital=10000.0,
    )

    print("========================================")
    print(" M12 PaperSim (multi-step, SL/TP)")
    print(" config_hash:", config_hash())
    print(" fee_mode:", args.fee_mode)
    print(" window:", args.window, "start_idx:", start_idx, "end_idx:", end_idx)
    print("----------------------------------------")
    for k, v in res.items():
        print(f"{k}: {v}")
    print("========================================")

if __name__ == "__main__":
    main()
