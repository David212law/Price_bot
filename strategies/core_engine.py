from strategies.indicators import calc_ema, calc_atr
import json
import os
import math
import random
from datetime import datetime, timezone

def load_data(exchange, symbol):
    if exchange == "kucoin":
        path = f"exchanges/kucoin/data/{symbol}_4h.json"
    elif exchange == "aster":
        path = f"data/aster/{symbol}_4h.json"
    else:
        return None
    
    if not os.path.exists(path): return None
    with open(path, 'r') as f: 
        data = json.load(f)
        # Aster format is a list, KuCoin is a dict with 'candles'
        if isinstance(data, dict) and "candles" in data: return data["candles"]
        return data

# ─── اندیکاتورهای مشترک ───
    k = 2.0 / (period + 1)
    e = sum(closes[:period]) / period
    ema[period - 1] = e
    for i in range(period, len(closes)):
        e = closes[i] * k + e * (1 - k)
        ema[i] = e
    return ema

    trs = [0] * len(candles)
    for i in range(1, len(candles)):
        trs[i] = max(candles[i]["h"] - candles[i]["l"], abs(candles[i]["h"] - candles[i-1]["c"]), abs(candles[i]["l"] - candles[i-1]["c"]))
    atr[period] = sum(trs[1:period+1]) / period
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + trs[i]) / period
    return atr

# ─── استراتژی‌ها ───
def strategy_m35(candles):
    """EMA Crossover 50/200"""
    closes = [c["c"] for c in candles]
    ema_fast = calc_ema(closes, 50)
    ema_slow = calc_ema(closes, 200)
    atr = calc_atr(candles, 14)
    
    trades = []
    in_pos = None
    
    for i in range(200, len(candles)):
        if None in [ema_fast[i], ema_slow[i], atr[i-1]]: continue
        
        if not in_pos:
            if ema_fast[i] > ema_slow[i] and ema_fast[i-1] <= ema_slow[i-1]:
                in_pos = {"side": "LONG", "entry": candles[i]["c"], "sl": candles[i]["c"] - (3*atr[i-1])}
            elif ema_fast[i] < ema_slow[i] and ema_fast[i-1] >= ema_slow[i-1]:
                in_pos = {"side": "SHORT", "entry": candles[i]["c"], "sl": candles[i]["c"] + (3*atr[i-1])}
        else:
            exit_price = None
            reason = ""
            if in_pos["side"] == "LONG":
                if candles[i]["l"] <= in_pos["sl"]: exit_price, reason = in_pos["sl"], "SL"
                elif ema_fast[i] < ema_slow[i]: exit_price, reason = candles[i]["c"], "CROSS"
            else:
                if candles[i]["h"] >= in_pos["sl"]: exit_price, reason = in_pos["sl"], "SL"
                elif ema_fast[i] > ema_slow[i]: exit_price, reason = candles[i]["c"], "CROSS"
                
            if exit_price:
                ret = (exit_price - in_pos["entry"]) / in_pos["entry"] if in_pos["side"] == "LONG" else (in_pos["entry"] - exit_price) / in_pos["entry"]
                trades.append({"ret": ret, "reason": reason})
                in_pos = None
    return trades

def calculate_metrics(trades, initial_capital=10000):
    if not trades: return {"error": "No trades"}
    wins = sum(1 for t in trades if t["ret"] > 0)
    gp = sum(t["ret"] for t in trades if t["ret"] > 0)
    gl = abs(sum(t["ret"] for t in trades if t["ret"] <= 0))
    pf = gp / gl if gl > 0 else 99.99
    
    equity = initial_capital
    peak = initial_capital
    max_dd = 0
    for t in trades:
        equity += equity * t["ret"] * 0.01 # 1% risk per trade
        if equity > peak: peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd: max_dd = dd
        
    return {
        "trades": len(trades),
        "win_rate": round((wins / len(trades)) * 100, 2),
        "pf": round(pf, 2),
        "max_dd": round(max_dd * 100, 2),
        "return": round(((equity - initial_capital)/initial_capital)*100, 2)
    }

def run(exchange, strategy_name):
    SYMBOLS = ["XBTUSDTM", "ETHUSDTM", "SOLUSDTM", "BNBUSDTM", "XRPUSDTM", "AVAXUSDTM"] if exchange == "kucoin" else ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"]
    
    all_trades = []
    for sym in SYMBOLS:
        candles = load_data(exchange, sym)
        if not candles: continue
        
        if strategy_name == "M35":
            trades = strategy_m35(candles)
            all_trades.extend(trades)
            
    metrics = calculate_metrics(all_trades)
    print(f"=== Backtest Results: {strategy_name} on {exchange.upper()} ===")
    print(json.dumps(metrics, indent=2))
    
    # ذخیره نتیجه
    os.makedirs("reports/backtest_results", exist_ok=True)
    with open(f"reports/backtest_results/{exchange}_{strategy_name}.json", "w") as f:
        json.dump(metrics, f)
