#!/usr/bin/env python3
"""D-551 Paper Bot — Hybrid_v3_Wallex (Toman market)"""
import json, os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SYMBOL = "USDTTMN"
STATE_FILE = "exchanges/wallex/state/v3_hybrid_state.json"
FEE_RT = 0.006
VOL_MULT_WARN = 1.5
VOL_MULT_DEF = 2.5
DD_THRESHOLD = 0.20
MA_PERIOD = 50
CONFIRM_DAYS = 3


def fetch_history(days=200):
    end = int(datetime.now().timestamp())
    start = end - days * 86400
    url = f"https://api.wallex.ir/v1/udf/history?symbol={SYMBOL}&resolution=1D&from={start}&to={end}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        if data.get("s") != "ok": return {}
        out = {}
        for t, c in zip(data["t"], data["c"]):
            out[datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")] = float(c)
        return out
    except Exception as e:
        print(f"[ERROR] fetch: {e}")
        return {}


def load_state():
    p = Path(STATE_FILE)
    if not p.exists():
        return {
            "initial_capital": 10000.0,
            "equity": 10000.0,
            "usdt_amount": 0.0,
            "cash_tmn": 10000.0,
            "peak_equity": 10000.0,
            "regime_history": [],
            "last_run": None,
            "trades": [],
        }
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"initial_capital": 10000.0, "equity": 10000.0,
                "usdt_amount": 0.0, "cash_tmn": 10000.0, "peak_equity": 10000.0,
                "regime_history": [], "last_run": None, "trades": []}


def save_state(state):
    p = Path(STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    tmp = str(p) + ".tmp"
    Path(tmp).write_text(json.dumps(state, indent=2))
    Path(tmp).replace(p)


def compute_regime(prices, history_dates):
    if len(history_dates) < MA_PERIOD + 25:
        return {}
    dates = history_dates[:-1]
    returns = []
    for i in range(1, len(dates)):
        p0 = prices[dates[i-1]]
        p1 = prices[dates[i]]
        if p0 > 0: returns.append((p1 - p0) / p0)
    if len(returns) < 20:
        return {}
    recent = returns[-20:]
    mean_r = sum(recent) / len(recent)
    var = sum((r - mean_r)**2 for r in recent) / len(recent)
    current_vol = var ** 0.5
    vols = []
    for i in range(20, len(returns) + 1):
        w = returns[i-20:i]
        m = sum(w) / 20
        v = sum((r - m)**2 for r in w) / 20
        vols.append(v ** 0.5)
    vols.sort()
    median_vol = vols[len(vols) // 2] if vols else current_vol
    last_ma = [prices[d] for d in dates[-MA_PERIOD:]]
    ma50 = sum(last_ma) / len(last_ma)
    current_price = prices[dates[-1]]
    return {
        "vol_ratio": round(current_vol / median_vol, 2) if median_vol > 0 else 1.0,
        "median_vol": round(median_vol, 6),
        "current_vol": round(current_vol, 6),
        "ma50": round(ma50, 0),
        "current_price": round(current_price, 0),
        "below_ma": current_price < ma50,
    }


def decide(regime_data, dd, confirm_history):
    vr = regime_data.get("vol_ratio", 1.0)
    below_ma = regime_data.get("below_ma", False)
    if dd > DD_THRESHOLD and below_ma:
        signal = "defensive"
    elif vr > VOL_MULT_DEF and below_ma:
        signal = "defensive"
    elif vr > VOL_MULT_WARN and below_ma:
        signal = "warning"
    else:
        signal = "normal"
    confirm_history.append(signal)
    if len(confirm_history) > CONFIRM_DAYS:
        confirm_history.pop(0)
    if len(confirm_history) >= CONFIRM_DAYS and all(s == signal for s in confirm_history):
        confirmed = signal
    else:
        confirmed = "normal"
    if confirmed == "defensive": return 0.80, signal, confirmed
    if confirmed == "warning":   return 0.40, signal, confirmed
    return 0.0, signal, confirmed


def rebalance(state, target_cash_pct, current_price):
    current_equity = state["usdt_amount"] * current_price + state["cash_tmn"]
    if current_equity <= 0: return state, 0
    target_cash = current_equity * target_cash_pct
    target_usdt_value = current_equity - target_cash
    current_usdt_value = state["usdt_amount"] * current_price
    diff = target_usdt_value - current_usdt_value
    if abs(diff) < current_equity * 0.01:
        return state, 0
    if diff > 0:
        fee = diff * (FEE_RT / 2)
        buy = (diff - fee) / current_price
        state["cash_tmn"] = max(0, state["cash_tmn"] - diff)
        state["usdt_amount"] += buy
        action = "buy"
    else:
        sell_val = -diff
        fee = sell_val * (FEE_RT / 2)
        state["usdt_amount"] = max(0, state["usdt_amount"] - sell_val / current_price)
        state["cash_tmn"] += sell_val - fee
        action = "sell"
    state["trades"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "action": action, "value": abs(diff), "fee": fee, "price": current_price,
    })
    return state, 1


def send_bale(msg):
    token = os.environ.get("BALE_BOT_TOKEN", "")
    chat = os.environ.get("BALE_CHAT_ID", "")
    if not token or not chat:
        print(f"[BALE-SKIP] {msg}")
        return
    try:
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat, "text": msg}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[BALE-ERR] {e}")


def main():
    print(f"=== Hybrid_v3_Wallex — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")
    state = load_state()
    history = fetch_history(200)
    if not history:
        print("[ABORT] no data"); return
    dates = sorted(history.keys())
    if len(dates) < 60:
        print(f"[ABORT] short history: {len(dates)}"); return
    current_price = history[dates[-1]]
    print(f"USDTTMN: {current_price:,.0f} Toman ({dates[-1]})")
    state["equity"] = state["usdt_amount"] * current_price + state["cash_tmn"]
    state["peak_equity"] = max(state["peak_equity"], state["equity"])
    dd = (state["peak_equity"] - state["equity"]) / state["peak_equity"] if state["peak_equity"] > 0 else 0
    regime = compute_regime(history, dates)
    print(f"Regime: vol_ratio={regime.get('vol_ratio')}, below_ma={regime.get('below_ma')}, dd={dd*100:.2f}%")
    target_cash, signal, confirmed = decide(regime, dd, state["regime_history"])
    current_cash_pct = state["cash_tmn"] / state["equity"] if state["equity"] > 0 else 1.0
    print(f"Signal: {signal} → confirmed={confirmed} → target_cash={target_cash*100:.0f}% (current={current_cash_pct*100:.1f}%)")
    n_trades = 0
    if abs(target_cash - current_cash_pct) > 0.01:
        state, n_trades = rebalance(state, target_cash, current_price)
        state["equity"] = state["usdt_amount"] * current_price + state["cash_tmn"]
    save_state(state)
    roi = (state["equity"] / state["initial_capital"] - 1) * 100
    print(f"Equity: {state['equity']:,.0f} | ROI: {roi:+.2f}% | Trades: {n_trades}")
    if n_trades > 0:
        last = state["trades"][-1]
        send_bale(f"v3 {last['action'].upper()} | {current_price:,.0f} | {confirmed} | ROI {roi:+.2f}%")


if __name__ == "__main__":
    main()
