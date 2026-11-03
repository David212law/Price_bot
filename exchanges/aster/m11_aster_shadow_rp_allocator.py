# PROJECT-ROOT-INJECT (D-356 fix)
import os as _os, sys as _sys
_project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _project_root not in _sys.path: _sys.path.insert(0, _project_root)

import os
import json
import base64
import requests
import time
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "David212law/Price_bot")
BALE_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT = os.environ.get("BALE_CHAT_ID", "")

STATE_FILE = "exchanges/aster/state/m11_aster_shadow_rp_state.json"
INITIAL_CAPITAL = 10000.0
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"]

# Base Allocations
M31_ALLOC = 0.40  # D-313  # D-306: 100%
A8_ALLOC = 0.0  # D-306  # D-287
A20_ALLOC = 0.0  # D-306  # D-287

# M31 Config
M31_LEVERAGE = 3  # D-310

# A8 Config
A8_RISK = 0.01
A8_TP = 0.02
A8_SL = 0.10
A8_TIME_STOP = 15

# A20 Config
A20_RISK = 0.01
A20_MAX_ALLOC = 0.10

TAKER_FEE = 0.00035
MAKER_FEE = 0.0001

def send_bale(msg):
    if not BALE_TOKEN or not BALE_CHAT: 
        print(f"[BALE] Skipped: {msg[:80]}")
        return
    url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": BALE_CHAT, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Bale Error: {e}")

def load_from_github(filename):
    """D-503: local disk read (migrated from GitHub API to avoid 422/rate-limit)"""
    import os
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f), None
        except Exception as e:
            print(f"[LOAD] {filename}: {e}")
            return {}, None
    return {}, None

def save_to_github(filename, data, sha=None):
    """D-503: local disk write (migrated from GitHub API; sha ignored)"""
    import os
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[SAVE] {filename}: {e}")
        return False

def fetch_klines(symbol, interval="4h", limit=300):
    url = f"https://fapi.asterdex.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in r.json()]
    except: pass
    return []

def fetch_latest_funding(symbol):
    url = f"https://fapi.asterdex.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data: return data[0]["fundingTime"], float(data[0]["fundingRate"])
    except: pass
    return 0, 0.0

def calc_ema(closes, period):
    ema = [None] * len(closes)
    if len(closes) < period: return ema
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

def calc_bb(closes, period, std_mult):
    upper = [None] * len(closes)
    lower = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i-period+1:i+1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = variance ** 0.5
        upper[i] = sma + (std_mult * std)
        lower[i] = sma - (std_mult * std)
    return upper, lower

def calc_rsi_arr(closes, period=14):
    rsi = [None] * len(closes)
    if len(closes) < period + 1: return rsi
    gains, losses = 0, 0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0: gains += change
        else: losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    rsi[period] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi[i] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100.0
    return rsi

def calc_supertrend(candles, period=10, multiplier=3.0):
    atr = [None] * len(candles)
    if len(candles) < period + 1: return [None]*len(candles), [0]*len(candles)
    trs = [0] * len(candles)
    for i in range(1, len(candles)):
        trs[i] = max(candles[i]["h"] - candles[i]["l"], abs(candles[i]["h"] - candles[i-1]["c"]), abs(candles[i]["l"] - candles[i-1]["c"]))
    atr[period] = sum(trs[1:period+1]) / period
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i]) / period
        
    st = [None] * len(candles)
    direction = [1] * len(candles)
    for i in range(period, len(candles)):
        if atr[i] is None: continue
        hl2 = (candles[i]["h"] + candles[i]["l"]) / 2
        upperband = hl2 + (multiplier * atr[i])
        lowerband = hl2 - (multiplier * atr[i])
        if i == period:
            st[i] = upperband
            direction[i] = 1
            continue
        if candles[i]["c"] > st[i-1]:
            direction[i] = 1
            st[i] = max(lowerband, st[i-1]) if direction[i-1] == 1 else lowerband
        else:
            direction[i] = -1
            st[i] = min(upperband, st[i-1]) if direction[i-1] == -1 else upperband
    return st, direction


def fetch_funding_interval(symbol):
    url = f"https://fapi.asterdex.com/fapi/v1/fundingInfo?symbol={symbol}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data:
                return int(data[0].get("fundingIntervalHours", 8))
    except: pass
    return 8 # پیش‌فرض


def load_active_weights(exchange, regime=None):
    """D-401b: regime-aware. Backward-compatible."""
    import json, os
    path = "exchanges/active_weights_shadow_aster_rp.json"
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
        print(f"[WEIGHTS-COMBO] load error: {_e}")
        return None

def main():
    # RUNTIME-REGIME-CHECK (D-356)
    try:
        from research_lab.regime_detector import get_current_regime, should_activate_strategy
        _regime, _adx = get_current_regime()
        print(f"[REGIME-COMBO] {_regime} (ADX={_adx:.2f})")
        globals()['_CURRENT_REGIME'] = _regime
    except Exception as _e:
        print(f"[REGIME-COMBO] detection failed: {_e}")
        globals()['_CURRENT_REGIME'] = 'UNKNOWN'


    print(f"=== M11-Aster SHADOW-RP ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ===")
    
    # LOAD ACTIVE WEIGHTS (D-389: before state init)
    _current_regime = globals().get('_CURRENT_REGIME', 'UNKNOWN')

    # D-436: Aster COMBO only for RANGE/NEUTRAL — skip entirely in TREND


    _w = load_active_weights("aster", regime=_current_regime)
    _keltner_pct = 0.0
    # D-435: Keltner فقط در RANGE/NEUTRAL (mean-reversion)
    _keltner_allowed = _current_regime in ("RANGE", "NEUTRAL", "UNKNOWN")
    if not _keltner_allowed:
        print(f"[GATE] Keltner skipped in {_current_regime} (mean-reversion)")
    if _w:
        try: _keltner_pct = float(_w.get("KELTNER_REV_AVAXUSDT", _w.get("KELTNER", 0.0)))
        except (TypeError, ValueError): _keltner_pct = 0.0
    if _keltner_pct > 0: print(f"[KELTNER-COMBO] Active: {_keltner_pct*100:.1f}%")
    if _w:
        globals()["M31_ALLOC"] = _w.get("M31", globals()["M31_ALLOC"])
        globals()["A8_ALLOC"] = _w.get("A8", globals()["A8_ALLOC"])
        globals()["A20_ALLOC"] = _w.get("A20", globals()["A20_ALLOC"])
        print(f"[CONFIG-COMBO] Aster: M31={globals()['M31_ALLOC']*100:.0f}%, A8={globals()['A8_ALLOC']*100:.0f}%, A20={globals()['A20_ALLOC']*100:.0f}%")

    state, sha = load_from_github(STATE_FILE)
    # اصلاح کلیدهای وضعیت برای رفع باگ سرمایه
    if not isinstance(state, dict) or "m31_capital" not in state:
        state = {
            "total_equity": INITIAL_CAPITAL,
            "m31_capital": INITIAL_CAPITAL * M31_ALLOC,
            "a8_capital": INITIAL_CAPITAL * A8_ALLOC,
            "a20_capital": INITIAL_CAPITAL * A20_ALLOC,
            "keltner_capital": INITIAL_CAPITAL * _keltner_pct,
            "keltner_pos": {},
            "cash_capital": INITIAL_CAPITAL * (1.0 - M31_ALLOC - A8_ALLOC - A20_ALLOC - _keltner_pct),
            "m31_last_funding_time": {sym: 0 for sym in SYMBOLS},
            "a8_positions": {},
            "a20_positions": {},
            "history": []
        }

    # MIGRATE: backfill cash_capital for existing state (D-389f)
    if "keltner_capital" not in state: state["keltner_capital"] = INITIAL_CAPITAL * _keltner_pct
    if "keltner_pos" not in state: state["keltner_pos"] = {}
    if "cash_capital" not in state:
        _inv = sum(p.get("invested",0) for pos in [state.get("a8_positions",{}),state.get("a20_positions",{})] for p in pos.values())
        _alloc = state.get("m31_capital",0)+state.get("a8_capital",0)+state.get("a20_capital",0)
        state["cash_capital"] = max(0, INITIAL_CAPITAL - _alloc - _inv - state.get("keltner_capital", 0))
        print(f"[MIGRATE] cash_capital initialized: ${state['cash_capital']:.2f}")

    data_4h = {}
    data_1d = {}
    current_prices = {}
    
    for sym in SYMBOLS:
        k4 = fetch_klines(sym, "4h", 300)
        k1 = fetch_klines(sym, "1d", 300)
        if k4 and k1:
            data_4h[sym] = k4
            data_1d[sym] = k1
            current_prices[sym] = k4[-1]["c"]

    if len(data_4h) < len(SYMBOLS): 
        print(f"⚠️ Data missing. Proceeding with {len(data_4h)} symbols.")
        send_bale(f"⚠️ Aster Data missing. Proceeding with {len(data_4h)} symbols.")

    # ── M31 Funding Logic ──
    m31_alloc = state["m31_capital"]
    for sym in SYMBOLS:
        f_time, f_rate = fetch_latest_funding(sym)
        if f_time > state["m31_last_funding_time"].get(sym, 0):
            if f_rate > 0:
                income = (m31_alloc / len(SYMBOLS)) * M31_LEVERAGE * f_rate
                state["m31_capital"] += income
                state["m31_last_funding_time"][sym] = f_time
                print(f"[M31] {sym} Funding received: {income:.4f} USDT (Rate: {f_rate*100:.4f}%)")
                send_bale(f"🟢 M31 Funding | {sym} | +{income:.4f} USDT")

    # ── Calculate current equity ──
    # D-421: Keltner COMBO logic
    if _keltner_pct > 0:
        try:
            from strategies.library.indicators import ema as _ema, atr as _atr
            for sym in SYMBOLS:
                _cd = fetch_klines(sym, "4h", 100)
                if not _cd or len(_cd) < 30: continue
                _cl = [x["c"] for x in _cd]
                _e = _ema(_cl, 20); _a = _atr(_cd, 20)
                if not _e or not _a or _e[-1] is None or _a[-1] is None: continue
                _up = _e[-1] + 2.0*_a[-1]; _lo = _e[-1] - 2.0*_a[-1]
                _last = _cd[-1]; _cur = _last["c"]
                _pos = state["keltner_pos"].get(sym)
                if _pos:
                    _ex = None
                    if _pos["side"] == "LONG":
                        if _last["l"] <= _pos["sl"]: _ex = _pos["sl"]
                        elif _last["h"] >= _pos["tp"]: _ex = _pos["tp"]
                    else:
                        if _last["h"] >= _pos["sl"]: _ex = _pos["sl"]
                        elif _last["l"] <= _pos["tp"]: _ex = _pos["tp"]
                    if _ex is not None:
                        _g = ((_ex-_pos["entry"])/_pos["entry"] if _pos["side"]=="LONG" else (_pos["entry"]-_ex)/_pos["entry"])
                        _pnl = _pos["invested"] * (_g - 2*TAKER_FEE)
                        state["keltner_capital"] += _pos["invested"] + _pnl
                        state["history"].append({"time": _last["t"], "strat": "KELTNER_COMBO", "sym": sym, "pnl": round(_pnl,4)})
                        del state["keltner_pos"][sym]
                        print(f"[KELTNER-COMBO] {sym} CLOSE {_pos['side']} @ {_ex:.2f} | PnL {_pnl:+.2f}")
                elif len(state["keltner_pos"]) < 3:
                    _side = None
                    if _cur < _lo: _side, _sl, _tp = "LONG", _lo-_a[-1], _e[-1]
                    elif _cur > _up: _side, _sl, _tp = "SHORT", _up+_a[-1], _e[-1]
                    if _side:
                        _alloc = state["keltner_capital"] * 0.15
                        if _alloc > 10 and state["keltner_capital"] >= _alloc:
                            state["keltner_capital"] -= _alloc
                            state["keltner_pos"][sym] = {"side": _side, "entry": _cur, "invested": _alloc, "sl": _sl, "tp": _tp}
                            print(f"[KELTNER-COMBO] {sym} OPEN {_side} @ {_cur:.2f}")
        except Exception as _e:
            print(f"[KELTNER-COMBO] error: {_e}")
    _ktm = 0.0
    for _s, _p in state.get("keltner_pos", {}).items():
        _ck = fetch_klines(_s, "4h", 5)
        if _ck:
            _cc = _ck[-1]["c"]
            _gg = ((_cc-_p["entry"])/_p["entry"] if _p["side"]=="LONG" else (_p["entry"]-_cc)/_p["entry"])
            _ktm += _p["invested"] * (1 + _gg)
        else:
            _ktm += _p["invested"]

    equity = state["m31_capital"] + state["a8_capital"] + state["a20_capital"] + state.get("keltner_capital", 0) + _ktm + state.get("cash_capital", 0)
    
    for sym, pos in list(state["a8_positions"].items()):
        equity += pos["units"] * current_prices[sym]
    for sym, pos in list(state["a20_positions"].items()):
        if pos["side"] == "LONG":
            equity += pos["units"] * current_prices[sym]
        else:
            pnl_pct = (pos["entry_price"] - current_prices[sym]) / pos["entry_price"]
            equity += pos["invested"] + (pos["invested"] * pnl_pct)
            
    state["total_equity"] = equity
    # D-392: track peak equity for Kill Switch
    _cur = state["total_equity"]
    state["peak_equity"] = max(state.get("peak_equity", _cur), _cur)
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    a8_equity = equity * A8_ALLOC
    a20_equity = equity * A20_ALLOC

    # ── Check Exits ──
    for sym, pos in list(state["a8_positions"].items()):
        if sym not in data_4h or sym not in current_prices: continue
        c = data_4h[sym][-1]
        exited = False
        exit_price = c["c"]
        
        if (len(data_4h[sym]) - pos["entry_idx"]) >= A8_TIME_STOP:
            exited, reason = True, "TIME_STOP"
        elif c["l"] <= pos["initial"] * (1 - A8_SL):
            exited, exit_price, reason = True, pos["initial"] * (1 - A8_SL), "SL"
        elif c["h"] >= pos["avg"] * (1 + A8_TP):
            exited, exit_price, reason = True, pos["avg"] * (1 + A8_TP), "TP"
            
        if exited:
            exit_val = pos["units"] * exit_price * (1 - TAKER_FEE)
            pnl = exit_val - pos["invested"]
            state["a8_capital"] += exit_val
            state["history"].append({"time": c["t"], "strat": "A8", "sym": sym, "pnl": pnl})
            del state["a8_positions"][sym]
            print(f"[A8] {sym} CLOSED ({reason}) | PnL: {pnl:+.2f}")
            send_bale(f"🔵 A8 CLOSED ({reason}) | {sym} | PnL: {pnl:+.2f}")

    for sym, pos in list(state["a20_positions"].items()):
        if sym not in data_4h or sym not in current_prices: continue
        c = data_4h[sym][-1]
        st_dir = calc_supertrend(data_4h[sym])[1][-1]
        exited = False
        exit_price = c["c"]
        
        if pos["side"] == "LONG":
            if c["l"] <= pos["sl"]:
                exited, exit_price, reason = True, pos["sl"], "SL"
            elif st_dir == -1:
                exited, reason = True, "ST_FLIP"
        elif pos["side"] == "SHORT":
            if c["h"] >= pos["sl"]:
                exited, exit_price, reason = True, pos["sl"], "SL"
            elif st_dir == 1:
                exited, reason = True, "ST_FLIP"
                
        if exited:
            if pos["side"] == "LONG":
                ret = (exit_price * (1 - TAKER_FEE) - pos["entry_price"] * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
            else:
                ret = (pos["entry_price"] * (1 - TAKER_FEE) - exit_price * (1 + TAKER_FEE)) / (pos["entry_price"] * (1 + TAKER_FEE))
            pnl = pos["invested"] * ret
            state["a20_capital"] += (pos["invested"] + pnl)
            state["history"].append({"time": c["t"], "strat": "A20", "sym": sym, "pnl": pnl})
            del state["a20_positions"][sym]
            print(f"[A20] {sym} CLOSED ({reason}) | PnL: {pnl:+.2f}")
            send_bale(f"🔵 A20 CLOSED ({reason}) | {sym} | PnL: {pnl:+.2f}")

    # ── Check Entries ──
    for sym in SYMBOLS:
        # A8 Entry
        if sym not in state["a8_positions"] and len(state["a8_positions"]) < 3:
            if sym not in data_4h: continue
            c = data_4h[sym][-1]
            closes = [x["c"] for x in data_4h[sym]]
            _, bb_l = calc_bb(closes, 20, 2.0)
            rsi = calc_rsi_arr(closes, 14)
            ema_1d = calc_ema([x["c"] for x in data_1d[sym]], 200)
            
            if None not in [bb_l[-1], rsi[-1], ema_1d[-1]]:
                if c["c"] > ema_1d[-1] and c["c"] <= bb_l[-1] and rsi[-1] < 35:
                    alloc = a8_equity * A8_RISK
                    if alloc > 10 and state["a8_capital"] >= alloc:
                        state["a8_capital"] -= alloc
                        units = (alloc * (1 - MAKER_FEE)) / c["c"]
                        state["a8_positions"][sym] = {
                            "initial": c["c"], "avg": c["c"], "units": units, 
                            "invested": alloc, "entry_idx": len(data_4h[sym]) - 1
                        }
                        print(f"[A8] {sym} OPENED at {c['c']:.2f}")
                        send_bale(f"🟢 A8 OPENED | {sym} at {c['c']:.2f}")

        # A20 Entry
        if sym not in state["a20_positions"] and len(state["a20_positions"]) < 3:
            if sym not in data_4h: continue
            st, st_dir = calc_supertrend(data_4h[sym])
            if st[-1] is not None and st_dir[-1] != st_dir[-2]:
                side = "LONG" if st_dir[-1] == 1 else "SHORT"
                c = data_4h[sym][-1]
                risk_amount = a20_equity * A20_RISK
                sl = st[-1]
                risk_per_unit = abs(c["c"] - sl)
                
                if risk_per_unit > 0:
                    alloc = min((risk_amount / risk_per_unit) * c["c"], a20_equity * A20_MAX_ALLOC)
                    if alloc > 10 and state["a20_capital"] >= alloc:
                        state["a20_capital"] -= alloc
                        units = alloc / c["c"]
                        state["a20_positions"][sym] = {
                            "side": side, "entry_price": c["c"], 
                            "units": units, "invested": alloc, "sl": sl
                        }
                        print(f"[A20] {sym} OPENED {side} at {c['c']:.2f}")
                        send_bale(f"🟢 A20 OPENED {side} | {sym} at {c['c']:.2f}")

    if save_to_github(STATE_FILE, state, sha):
        roi = ((state["total_equity"] - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
        print(f"✅ State saved. Equity: {state['total_equity']:.2f} USDT (ROI: {roi:+.2f}%)")

    # (active_weights loaded at start of main - D-389)
if __name__ == "__main__":
    main()
