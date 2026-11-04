# PROJECT-ROOT-INJECT (D-356 fix)
import os as _os, sys as _sys
_project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _project_root not in _sys.path: _sys.path.insert(0, _project_root)

import json, os, requests, time
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0
M31_PCT = 0.80  # D-313  # D-306: 100%
M35_PCT = 0.0  # D-306  # D-286
M40_PCT = 0.0  # D-306  # D-286
M41_PCT = 0.0  # D-306  # D-286 # تخصیص جدید برای Diversifier
KELTNER_PCT = 0.0  # D-397c — پیش‌فرض خاموش، از active_weights فعال می‌شود
M31_LEVERAGE = 3  # D-310
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005
STATE_FILE = "exchanges/hyperliquid/state/m11_hl_shadow_rp_portfolio.json"
SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]

def fetch_funding(symbol):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (4 * 3600 * 1000)
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": now_ms}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return sum(float(rec["fundingRate"]) for rec in r.json())
    except: pass
    return 0.0

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f: return json.load(f)
    return {"signals": []}


def _log_close(state, sym, strat, pnl_val):
    if "history" not in state: state["history"] = []
    state["history"].append({"time": int(time.time() * 1000), "strat": strat, "symbol": sym, "pnl": round(pnl_val, 4)})


def load_active_weights(exchange, regime=None):
    """D-401: regime-aware weights loader. Backward-compatible with flat format."""
    import json, os
    path = "exchanges/active_weights_shadow_hl.json"
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        ex_data = data.get(exchange, {})
        if not ex_data:
            return None
        regime_keys = {"TREND","RANGE","NEUTRAL","UNKNOWN"}
        if any(k in regime_keys for k in ex_data.keys()):
            if regime and regime in ex_data:
                return ex_data[regime]
            for fb in ("UNKNOWN","TREND"):
                if fb in ex_data:
                    return ex_data[fb]
            return None
        return ex_data
    except Exception as _e:
        print(f"[SHADOW-HL-W] load error: {_e}")
        return None

def main():
    # RUNTIME-REGIME-CHECK (D-356)
    try:
        from research_lab.regime_detector import get_current_regime, should_activate_strategy
        _regime, _adx = get_current_regime()
        print(f"[SHADOW-HL-R] {_regime} (ADX={_adx:.2f})")
        globals()['_CURRENT_REGIME'] = _regime
    except Exception as _e:
        print(f"[SHADOW-HL-R] detection failed: {_e}")
        globals()['_CURRENT_REGIME'] = 'UNKNOWN'

    # LOAD ACTIVE WEIGHTS (D-389: before state init)
    _current_regime = globals().get('_CURRENT_REGIME', 'UNKNOWN')
    _w = load_active_weights("hyperliquid", regime=_current_regime)
    if _w:
        print(f"[SHADOW-HL-W] regime={_current_regime} → keys={list(_w.keys())}")
        globals()["M31_PCT"] = _w.get("M31", globals()["M31_PCT"])
        globals()["M35_PCT"] = _w.get("M35", globals()["M35_PCT"])
        globals()["M40_PCT"] = _w.get("M40", globals()["M40_PCT"])
        globals()["M41_PCT"] = _w.get("M41", globals()["M41_PCT"])
        globals()["KELTNER_PCT"] = _w.get("KELTNER", globals()["KELTNER_PCT"])
        print(f"[SHADOW-HL-CFG] HL: M31={globals()['M31_PCT']*100:.0f}%, M35={globals()['M35_PCT']*100:.0f}%, M40={globals()['M40_PCT']*100:.0f}%, M41={globals()['M41_PCT']*100:.0f}%, KELTNER={globals()['KELTNER_PCT']*100:.0f}%")

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f: state = json.load(f)
        if "m41_capital" not in state: state["m41_capital"] = INITIAL_CAPITAL * M41_PCT
        if "m41_pos" not in state: state["m41_pos"] = {}
        if "cash_capital" not in state:
            _inv = sum(p.get("invested",0) for pos in [state.get("m35_pos",{}),state.get("m40_pos",{}),state.get("m41_pos",{})] for p in pos.values())
            # D-488: include keltner_capital in _alloc (D-448 regression fix)
            _alloc = (state.get("m31_capital",0) + state.get("m35_capital",0)
                      + state.get("m40_capital",0) + state.get("m41_capital",0)
                      + state.get("keltner_capital",0))
            state["cash_capital"] = max(0, INITIAL_CAPITAL - _alloc - _inv)
            print(f"[MIGRATE] cash_capital initialized: ${state['cash_capital']:.2f}")
    else:
        state = {
            "total_capital": INITIAL_CAPITAL,
            "m31_capital": INITIAL_CAPITAL * M31_PCT, "m35_capital": INITIAL_CAPITAL * M35_PCT, 
            "m40_capital": INITIAL_CAPITAL * M40_PCT, "m41_capital": INITIAL_CAPITAL * M41_PCT,
            "m31_pos": {}, "m35_pos": {}, "m40_pos": {}, "m41_pos": {}, "history": []
        }

    # 1. M31 Accrual & Signals (بدون تغییر)
    for sym in list(state["m31_pos"].keys()):
        rate = fetch_funding(sym)
        earned = (state["m31_capital"] / len(SYMBOLS)) * rate * M31_LEVERAGE
        state["m31_capital"] += earned

    m31_sigs = load_json("exchanges/hyperliquid/state/m31_signals.json").get("signals", [])
    for sig in m31_sigs:
        if sig["action"] == "OPEN" and sig["symbol"] not in state["m31_pos"]:
            cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
            state["m31_capital"] -= cost
            state["m31_pos"][sig["symbol"]] = {"entry_time": sig["time"]}
        elif sig["action"] == "CLOSE" and sig["symbol"] in state["m31_pos"]:
            cost = (state["m31_capital"] / len(SYMBOLS)) * MAKER_FEE * 2 * M31_LEVERAGE
            state["m31_capital"] -= cost
            del state["m31_pos"][sig["symbol"]]

    # 2. M35 Signals
    m35_sigs = load_json("exchanges/hyperliquid/state/m35_signals.json").get("signals", [])
    for sig in m35_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m35_pos"]:
            alloc = state["m35_capital"] * 0.20
            if alloc > 10 and state["m35_capital"] > alloc:
                state["m35_capital"] -= alloc
                state["m35_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "stop": sig["price"] - (3*sig["atr"]) if sig["action"]=="OPEN_LONG" else sig["price"] + (3*sig["atr"])}

    # 3. M40 Signals
    m40_sigs = load_json("exchanges/hyperliquid/state/m40_signals.json").get("signals", [])
    for sig in m40_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m40_pos"]:
            if len(state["m40_pos"]) < 3:
                alloc = state["m40_capital"] * 0.10
                if alloc > 10 and state["m40_capital"] > alloc:
                    state["m40_capital"] -= alloc
                    state["m40_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "tp": sig["tp"], "sl": sig["sl"]}

    # 4. M41 Signals (Diversifier)
    m41_sigs = load_json("exchanges/hyperliquid/state/m41_signals.json").get("signals", [])
    for sig in m41_sigs:
        if sig["action"] in ["OPEN_LONG", "OPEN_SHORT"] and sig["symbol"] not in state["m41_pos"]:
            # برای M41 از ریسک 0.5% استفاده می‌کنیم (طبق پیش‌ثبت نام)
            alloc = state["m41_capital"] * 0.05 # 5% از سرمایه M41
            if alloc > 10 and state["m41_capital"] > alloc:
                state["m41_capital"] -= alloc
                state["m41_pos"][sig["symbol"]] = {"side": "LONG" if sig["action"]=="OPEN_LONG" else "SHORT", "entry": sig["price"], "invested": alloc, "tp": sig["tp"], "sl": sig["sl"]}

    # KELTNER Reversion (D-397c-v2) — منطق مطابق mean_reversion.py
    if KELTNER_PCT > 0:  # D-437 SHADOW: no regime gate, all regimes
        from strategies.core_engine import load_data
        from strategies.library.indicators import ema as _ema, atr as _atr

        if "keltner_capital" not in state:
            state["keltner_capital"] = INITIAL_CAPITAL * KELTNER_PCT
        if "keltner_pos" not in state:
            state["keltner_pos"] = {}

        MAX_POS, POS_PCT, MIN_ALLOC = 3, 0.15, 10.0

        # الف) بررسی خروج
        for _sym in list(state["keltner_pos"].keys()):
            _cd = load_data("hyperliquid", _sym)
            if not _cd or len(_cd) < 30: continue
            _lst, _pos = _cd[-1], state["keltner_pos"][_sym]
            _ex = None
            if _pos["side"] == "LONG":
                if _lst["l"] <= _pos["sl"]: _ex = _pos["sl"]
                elif _lst["h"] >= _pos["tp"]: _ex = _pos["tp"]
            else:
                if _lst["h"] >= _pos["sl"]: _ex = _pos["sl"]
                elif _lst["l"] <= _pos["tp"]: _ex = _pos["tp"]
            if _ex is not None:
                _g = ((_ex - _pos["entry"]) / _pos["entry"] if _pos["side"] == "LONG"
                      else (_pos["entry"] - _ex) / _pos["entry"])
                _pnl = _pos["invested"] * (_g - 0.0012)
                state["keltner_capital"] += _pos["invested"] + _pnl
                del state["keltner_pos"][_sym]
                _log_close(state, _sym, "KELTNER", _pnl)
                print(f"[SHADOW-HL-K] {_sym} CLOSE {_pos['side']} @ {_ex:.2f} | PnL {_pnl:+.2f}")

        # ب) ورودهای جدید
        _slots = MAX_POS - len(state["keltner_pos"])
        if _slots > 0:
            _cands = []
            for _sym in SYMBOLS:
                if _sym in state["keltner_pos"]: continue
                _cd = load_data("hyperliquid", _sym)
                if not _cd or len(_cd) < 30: continue
                _cl = [x["c"] for x in _cd]
                _e, _a = _ema(_cl, 20), _atr(_cd, 20)
                if not _e or not _a or _e[-1] is None or _a[-1] is None: continue
                _up, _lo = _e[-1] + 2*_a[-1], _e[-1] - 2*_a[-1]
                _cur = _cd[-1]["c"]
                # منطق دقیقاً مطابق mean_reversion.py:105
                if _cur < _lo:   _cands.append(((_lo-_cur)/_a[-1], _sym, "LONG",  _cur, _lo-_a[-1], _e[-1]))
                elif _cur > _up: _cands.append(((_cur-_up)/_a[-1], _sym, "SHORT", _cur, _up+_a[-1], _e[-1]))
            _cands.sort(reverse=True)
            for _st, _sym, _sd, _en, _sl, _tp in _cands[:_slots]:
                _al = state["keltner_capital"] * POS_PCT
                if _al < MIN_ALLOC or _al > state["keltner_capital"]: continue
                state["keltner_capital"] -= _al
                state["keltner_pos"][_sym] = {"side": _sd, "entry": _en, "invested": _al, "sl": _sl, "tp": _tp}
                print(f"[SHADOW-HL-K] {_sym} OPEN {_sd} @ {_en:.2f} | SL={_sl:.2f} TP={_tp:.2f} str={_st:.2f}")

    # 5. محاسبه سرمایه کل
    total_invested = sum(p["invested"] for pos in [state["m35_pos"], state["m40_pos"], state["m41_pos"]] for p in pos.values())
    # MTM پوزیشن‌های باز Keltner
    _ktm = 0.0
    for _s, _p in state.get("keltner_pos", {}).items():
        from strategies.core_engine import load_data as _ld
        _cd = _ld("hyperliquid", _s)
        if _cd:
            _c = _cd[-1]["c"]
            _g = ((_c - _p["entry"]) / _p["entry"] if _p["side"] == "LONG"
                  else (_p["entry"] - _c) / _p["entry"])
            _ktm += _p["invested"] * (1 + _g)
        else:
            _ktm += _p["invested"]
    total_equity = (state["m31_capital"] + state["m35_capital"] + state["m40_capital"]
                    + state["m41_capital"] + state.get("keltner_capital", 0) + _ktm
                    + state.get("cash_capital", 0) + total_invested)
    state["total_capital"] = total_equity
    # D-392: track peak equity for Kill Switch
    _cur = state["total_capital"]
    state["peak_equity"] = max(state.get("peak_equity", _cur), _cur)
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2)
    print(f"Allocator Updated. Total Equity: ${state['total_capital']:.2f}")
    print(f"  M31: ${state['m31_capital']:.2f} | M35: ${state['m35_capital']:.2f} | M40: ${state['m40_capital']:.2f} | M41: ${state['m41_capital']:.2f} | Cash: ${state.get('cash_capital', 0):.2f}")

    # (active_weights loaded at start of main - D-389)
if __name__ == "__main__": main()
