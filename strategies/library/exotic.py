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




# ═══════════════════════════════════════════════════════════════
# D-481: 3 new genuinely-different strategies
# ═══════════════════════════════════════════════════════════════

def strat_volume_profile(candles, period=50, va_width=0.7, fee_multiplier=1.0):
    """Volume Profile Reversion: POC/VAH/VAL levels as support/resistance."""
    if len(candles) < period + 20: return []
    fee = 0.0006 * fee_multiplier
    trades = []
    pos = None
    for i in range(period, len(candles)):
        window = candles[i-period:i]
        prices = [c["c"] for c in window]
        volumes = [c["v"] for c in window]
        if not prices or sum(volumes) == 0: continue
        min_p, max_p = min(prices), max(prices)
        if max_p == min_p: continue
        bins = [(max_p - min_p) * j / 20 + min_p for j in range(21)]
        bin_vol = [0.0] * 20
        for cc in window:
            for j in range(20):
                if bins[j] <= cc["c"] < bins[j+1]:
                    bin_vol[j] += cc["v"]; break
        total_vol = sum(bin_vol)
        if total_vol == 0: continue
        poc_idx = bin_vol.index(max(bin_vol))
        poc = (bins[poc_idx] + bins[poc_idx+1]) / 2
        va_vol = bin_vol[poc_idx]
        lo_idx = hi_idx = poc_idx
        target = total_vol * va_width
        while va_vol < target and (lo_idx > 0 or hi_idx < 19):
            if lo_idx > 0 and (hi_idx >= 19 or bin_vol[lo_idx-1] >= bin_vol[hi_idx+1]):
                lo_idx -= 1; va_vol += bin_vol[lo_idx]
            elif hi_idx < 19:
                hi_idx += 1; va_vol += bin_vol[hi_idx]
            else: break
        vah = bins[hi_idx+1]; val = bins[lo_idx]
        last = candles[i]; cur = last["c"]
        if pos is None:
            if cur > vah:
                pos = {"side":"SHORT","entry":cur,"tp":poc,"sl":cur + (vah-val)*0.5}
            elif cur < val:
                pos = {"side":"LONG","entry":cur,"tp":poc,"sl":cur - (vah-val)*0.5}
        else:
            ex = None
            if pos["side"] == "LONG":
                if last["l"] <= pos["sl"]: ex = pos["sl"]
                elif last["h"] >= pos["tp"]: ex = pos["tp"]
            else:
                if last["h"] >= pos["sl"]: ex = pos["sl"]
                elif last["l"] <= pos["tp"]: ex = pos["tp"]
            if ex:
                trades.append(_trade(last, pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades


def strat_weekly_pivot(candles, week_candles=42, fee_multiplier=1.0):
    """Weekly Pivot Breakout: trade breaks of previous week high/low."""
    if len(candles) < week_candles * 2 + 10: return []
    fee = 0.0006 * fee_multiplier
    trades = []
    pos = None
    i = week_candles
    while i < len(candles):
        prev_week = candles[i-week_candles:i]
        week_high = max(c["h"] for c in prev_week)
        week_low = min(c["l"] for c in prev_week)
        end = min(i + week_candles, len(candles))
        for j in range(i, end):
            last = candles[j]; cur = last["c"]
            if pos is None:
                if cur > week_high:
                    pos = {"side":"LONG","entry":cur,"sl":week_high*0.99,"tp":cur*1.03}
                elif cur < week_low:
                    pos = {"side":"SHORT","entry":cur,"sl":week_low*1.01,"tp":cur*0.97}
            else:
                ex = None
                if pos["side"] == "LONG":
                    if last["l"] <= pos["sl"]: ex = pos["sl"]
                    elif last["h"] >= pos["tp"]: ex = pos["tp"]
                else:
                    if last["h"] >= pos["sl"]: ex = pos["sl"]
                    elif last["l"] <= pos["tp"]: ex = pos["tp"]
                if ex:
                    trades.append(_trade(last, pos["side"], pos["entry"], ex, fee))
                    pos = None
            if j == end - 1 and pos is not None:
                trades.append(_trade(last, pos["side"], pos["entry"], cur, fee))
                pos = None
        i = end
    return trades


def strat_volatility_trend(candles, ema_p=20, atr_p=14, atr_mult=1.5, fee_multiplier=1.0):
    """Volatility-Adjusted Trend: trade only when ATR confirms expansion."""
    if len(candles) < max(ema_p, atr_p) + 20: return []
    closes = [c["c"] for c in candles]
    e = ema(closes, ema_p)
    a = atr(candles, atr_p)
    fee = 0.0006 * fee_multiplier
    trades = []
    pos = None
    for i in range(ema_p, len(candles)):
        if e[i] is None or a[i] is None or a[i-1] is None: continue
        atr_rising = a[i] > a[i-1] * 1.1
        if pos is None:
            if closes[i] > e[i] and closes[i-1] <= e[i-1] and atr_rising:
                pos = {"side":"LONG","entry":closes[i],"sl":closes[i]-atr_mult*a[i],"tp":closes[i]+3*atr_mult*a[i]}
            elif closes[i] < e[i] and closes[i-1] >= e[i-1] and atr_rising:
                pos = {"side":"SHORT","entry":closes[i],"sl":closes[i]+atr_mult*a[i],"tp":closes[i]-3*atr_mult*a[i]}
        else:
            last = candles[i]; ex = None
            if pos["side"] == "LONG":
                if last["l"] <= pos["sl"]: ex = pos["sl"]
                elif last["h"] >= pos["tp"]: ex = pos["tp"]
                elif closes[i] < e[i] and closes[i-1] >= e[i-1]: ex = closes[i]
            else:
                if last["h"] >= pos["sl"]: ex = pos["sl"]
                elif last["l"] <= pos["tp"]: ex = pos["tp"]
                elif closes[i] > e[i] and closes[i-1] <= e[i-1]: ex = closes[i]
            if ex:
                trades.append(_trade(last, pos["side"], pos["entry"], ex, fee))
                pos = None
    return trades

CANDLE_STRATEGIES = {
    "PAIRS_RELATIVE": (strat_pairs_relative, {"lookback": [20, 30], "z_threshold": [1.5, 2.0]}),
    "LOW_VOL_CARRY": (strat_low_vol_carry, {"vol_pct_threshold": [0.20, 0.30, 0.40]}),
    "MTF_CONFIRMATION": (strat_mtf_confirmation, {"fast": [20], "slow": [50], "mtf_mult": [6]}),
    "VOLUME_PROFILE": (strat_volume_profile, {"period": [30, 50], "va_width": [0.6, 0.7]}),
    "WEEKLY_PIVOT": (strat_weekly_pivot, {"week_candles": [42], "fee_multiplier": [1.0]}),
    "VOL_TREND": (strat_volatility_trend, {"ema_p": [20, 50], "atr_mult": [1.5, 2.0]}),
}
