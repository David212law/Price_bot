"""D-442: Exotic low-vol strategies — different mechanisms."""
from strategies.library.indicators import ema, atr


def _trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}


def strat_pairs_relative(candles, lookback=20, z_threshold=2.0, fee_multiplier=1.0):
    """Short-term return reversal. Low vol by design."""
    if not candles or len(candles) < 30: return []
    fee = 0.0006 * fee_multiplier
    trades = []
    for i in range(6, len(candles) - 1):
        r = candles[i]["c"] / candles[i-6]["c"] - 1
        if r > 0.02:
            trades.append(_trade(candles[i], "SHORT", candles[i]["c"], candles[i+1]["c"], fee))
        elif r < -0.02:
            trades.append(_trade(candles[i], "LONG", candles[i]["c"], candles[i+1]["c"], fee))
    return trades


def strat_low_vol_carry(candles, atr_p=20, pct_window=100, vol_pct_threshold=0.30,
                         fee_multiplier=1.0):
    """Trend entry only when vol is LOW."""
    if not candles or len(candles) < pct_window + 30: return []
    closes = [c["c"] for c in candles]
    e_fast = ema(closes, 20); e_slow = ema(closes, 50)
    a = atr(candles, atr_p)
    fee = 0.0006 * fee_multiplier
    trades = []; pos = None
    for i in range(pct_window, len(candles)):
        if None in (e_fast[i], e_slow[i], a[i]): continue
        window_atr = [a[j] for j in range(i-pct_window, i) if a[j] is not None]
        if len(window_atr) < 20: continue
        pct_rank = sum(1 for x in window_atr if x < a[i]) / len(window_atr)
        is_low_vol = pct_rank < vol_pct_threshold
        if pos is None and is_low_vol:
            if e_fast[i] > e_slow[i] and e_fast[i-1] <= e_slow[i-1]:
                pos = {"side": "LONG", "entry": closes[i], "tp": closes[i] + 3*a[i], "sl": closes[i] - 2*a[i]}
            elif e_fast[i] < e_slow[i] and e_fast[i-1] >= e_slow[i-1]:
                pos = {"side": "SHORT", "entry": closes[i], "tp": closes[i] - 3*a[i], "sl": closes[i] + 2*a[i]}
        elif pos is not None:
            if not is_low_vol:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], closes[i], fee))
                pos = None; continue
            ex = None
            if pos["side"] == "LONG":
                if candles[i]["l"] <= pos["sl"]: ex = pos["sl"]
                elif candles[i]["h"] >= pos["tp"]: ex = pos["tp"]
            else:
                if candles[i]["h"] >= pos["sl"]: ex = pos["sl"]
                elif candles[i]["l"] <= pos["tp"]: ex = pos["tp"]
            if ex:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades


def strat_mtf_confirmation(candles, fast=20, slow=50, mtf_mult=6, fee_multiplier=1.0):
    """4h EMA cross + 1d trend agreement."""
    if not candles or len(candles) < slow * 3: return []
    closes = [c["c"] for c in candles]
    e_fast = ema(closes, fast); e_slow = ema(closes, slow)
    fee = 0.0006 * fee_multiplier
    a = atr(candles, 14)
    daily_closes = [candles[i]["c"] for i in range(mtf_mult-1, len(candles), mtf_mult)]
    daily_t = list(range(mtf_mult-1, len(candles), mtf_mult))
    if len(daily_closes) < 30: return []
    d_ema = ema(daily_closes, 20)
    daily_to_4h = {d_idx: c_idx for d_idx, c_idx in enumerate(daily_t)}
    trades = []; pos = None
    for i in range(slow + mtf_mult, len(candles)):
        if None in (e_fast[i], e_slow[i], e_fast[i-1], e_slow[i-1], a[i-1]): continue
        recent_d_idx = None
        for d_idx, c_idx in daily_to_4h.items():
            if c_idx <= i and d_ema[d_idx] is not None:
                recent_d_idx = d_idx
        if recent_d_idx is None or recent_d_idx < 3: continue
        d_now = d_ema[recent_d_idx]
        d_prev = d_ema[recent_d_idx-3]
        if d_now is None or d_prev is None: continue
        d_trend_up = d_now > d_prev
        d_trend_dn = d_now < d_prev
        if pos is None:
            if e_fast[i] > e_slow[i] and e_fast[i-1] <= e_slow[i-1] and d_trend_up:
                pos = {"side": "LONG", "entry": closes[i], "sl": closes[i] - 2*a[i-1]}
            elif e_fast[i] < e_slow[i] and e_fast[i-1] >= e_slow[i-1] and d_trend_dn:
                pos = {"side": "SHORT", "entry": closes[i], "sl": closes[i] + 2*a[i-1]}
        else:
            exit_p = None
            if pos["side"] == "LONG":
                if candles[i]["l"] <= pos["sl"]: exit_p = pos["sl"]
                elif e_fast[i] < e_slow[i] and e_fast[i-1] >= e_slow[i-1]: exit_p = closes[i]
            else:
                if candles[i]["h"] >= pos["sl"]: exit_p = pos["sl"]
                elif e_fast[i] > e_slow[i] and e_fast[i-1] <= e_slow[i-1]: exit_p = closes[i]
            if exit_p:
                trades.append(_trade(candles[i], pos["side"], pos["entry"], exit_p, fee))
                pos = None
    return trades


CANDLE_STRATEGIES = {
    "PAIRS_RELATIVE": (strat_pairs_relative, {"lookback": [20, 30], "z_threshold": [1.5, 2.0]}),
    "LOW_VOL_CARRY": (strat_low_vol_carry, {"vol_pct_threshold": [0.20, 0.30, 0.40]}),
    "MTF_CONFIRMATION": (strat_mtf_confirmation, {"fast": [20], "slow": [50], "mtf_mult": [6]}),
}




    {"lookback": [30, 50], "z_threshold": [1.5, 2.0, 2.5]}
)
