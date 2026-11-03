"""D-508: 300 diverse strategies — generated from compact spec.
Phase 1: Trend (50). Phases 2/3 will be appended later.
"""
from strategies.library.indicators import (
    ema, sma, atr, rsi, bollinger, macd, adx, supertrend, donchian,
    kama, wma, tema, vwma, aroon, vortex, trix, kst, psar,
    tsi, ultimate_osc, awesome_osc, coppock, cci, williams_r, cmo,
    keltner, chaikin_vol, hist_vol, atr_pct, bb_width,
    obv, mfi, vwap, ad_line, cmf, force_index, vpt,
    zscore, half_life,
)
FEE = 0.0006

def _make_trade(candle, side, entry, exit_p, fee):
    gross = (exit_p - entry) / entry if side == "LONG" else (entry - exit_p) / entry
    return {"t": candle["t"], "ret": gross - (fee * 2)}

def _get_series(candles, spec):
    kind = spec["kind"]; params = spec.get("params", [])
    closes = [c["c"] for c in candles]
    if kind == "price": return closes
    if kind == "ema": return ema(closes, *params)
    if kind == "sma": return sma(closes, *params)
    if kind == "kama": return kama(closes, *params)
    if kind == "wma": return wma(closes, *params)
    if kind == "tema": return tema(closes, *params)
    if kind == "dch_hi": return donchian(candles, *params)[0]
    if kind == "dch_lo": return donchian(candles, *params)[1]
    if kind == "st": return supertrend(candles, *params)[0]
    if kind == "st_dir": return supertrend(candles, *params)[1]
    if kind == "psar": return psar(candles, *params)
    if kind == "aroon_up": return aroon(candles, *params)[0]
    if kind == "aroon_dn": return aroon(candles, *params)[1]
    if kind == "vp": return vortex(candles, *params)[0]
    if kind == "vm": return vortex(candles, *params)[1]
    if kind == "trix": return trix(closes, *params)
    if kind == "kst": return kst(closes)
    if kind == "tsi": return tsi(closes, *params)
    if kind == "uo": return ultimate_osc(candles)
    if kind == "ao": return awesome_osc(candles)
    if kind == "coppock": return coppock(closes)
    if kind == "cci": return cci(candles, *params)
    if kind == "wr": return williams_r(candles, *params)
    if kind == "cmo": return cmo(closes, *params)
    if kind == "rsi": return rsi(closes, *params)
    if kind == "mfi": return mfi(candles, *params)
    if kind == "obv": return obv(candles)
    if kind == "ad": return ad_line(candles)
    if kind == "cmf": return cmf(candles, *params)
    if kind == "vpt": return vpt(candles)
    if kind == "fi": return force_index(candles, *params)
    if kind == "vwap": return vwap(candles, *params)
    if kind == "z": return zscore(closes, *params)
    if kind == "hl": return half_life(closes, *params)
    if kind == "bb_up": return bollinger(closes, *params)[0]
    if kind == "bb_lo": return bollinger(closes, *params)[2]
    if kind == "bb_mid": return bollinger(closes, *params)[1]
    if kind == "bb_width": return bb_width(closes, *params)
    if kind == "kel_up": return keltner(candles, *params)[0]
    if kind == "kel_lo": return keltner(candles, *params)[2]
    if kind == "kel_mid": return keltner(candles, *params)[1]
    if kind == "atr_pct": return atr_pct(candles, *params)
    if kind == "hist_vol": return hist_vol(closes, *params)
    raise ValueError(f"unknown kind: {kind}")

def _cross_signal(a, b, i):
    if i < 1 or a[i] is None or b[i] is None or a[i-1] is None or b[i-1] is None: return 0
    if a[i] > b[i] and a[i-1] <= b[i-1]: return 1
    if a[i] < b[i] and a[i-1] >= b[i-1]: return -1
    return 0

def _level_signal(price, level, i, side):
    if i < 1 or price[i] is None or level[i] is None or price[i-1] is None or level[i-1] is None: return 0
    if side == "LONG" and price[i] > level[i] and price[i-1] <= level[i-1]: return 1
    if side == "SHORT" and price[i] < level[i] and price[i-1] >= level[i-1]: return 1
    return 0

def _threshold_signal(series, i, th, direction):
    if i < 1 or series[i] is None or series[i-1] is None: return 0
    if direction == "long" and series[i] > th and series[i-1] <= th: return 1
    if direction == "short" and series[i] < th and series[i-1] >= th: return 1
    return 0

def _make_cross(name, a_spec, b_spec, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        a = _get_series(candles, a_spec); b = _get_series(candles, b_spec)
        trades, pos = [], None
        for i in range(60, len(candles)):
            sig = _cross_signal(a, b, i)
            if not pos:
                if sig == 1 and direction in ("both", "long"):
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side": "LONG", "entry": candles[i]["c"],
                           "sl": candles[i]["c"]-sl_mult*av, "tp": candles[i]["c"]+tp_mult*av}
                elif sig == -1 and direction in ("both", "short"):
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side": "SHORT", "entry": candles[i]["c"],
                           "sl": candles[i]["c"]+sl_mult*av, "tp": candles[i]["c"]-tp_mult*av}
            else:
                ex = None
                if pos["side"] == "LONG":
                    if candles[i]["l"] <= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["h"] >= pos["tp"]: ex = pos["tp"]
                    elif sig == -1: ex = candles[i]["c"]
                else:
                    if candles[i]["h"] >= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["l"] <= pos["tp"]: ex = pos["tp"]
                    elif sig == 1: ex = candles[i]["c"]
                if ex:
                    trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, FEE))
                    pos = None
        return trades
    strat.__name__ = name
    return strat

def _make_level(name, p_spec, l_spec, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        p = _get_series(candles, p_spec); l = _get_series(candles, l_spec)
        trades, pos = [], None
        for i in range(60, len(candles)):
            if not pos:
                if direction in ("both", "long") and _level_signal(p, l, i, "LONG"):
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side": "LONG", "entry": candles[i]["c"],
                           "sl": candles[i]["c"]-sl_mult*av, "tp": candles[i]["c"]+tp_mult*av}
                elif direction in ("both", "short") and _level_signal(p, l, i, "SHORT"):
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side": "SHORT", "entry": candles[i]["c"],
                           "sl": candles[i]["c"]+sl_mult*av, "tp": candles[i]["c"]-tp_mult*av}
            else:
                ex = None
                if pos["side"] == "LONG":
                    if candles[i]["l"] <= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["h"] >= pos["tp"]: ex = pos["tp"]
                else:
                    if candles[i]["h"] >= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["l"] <= pos["tp"]: ex = pos["tp"]
                if ex:
                    trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, FEE))
                    pos = None
        return trades
    strat.__name__ = name
    return strat

def _make_threshold(name, s_spec, th, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        s = _get_series(candles, s_spec)
        trades, pos = [], None
        for i in range(60, len(candles)):
            if not pos:
                if direction == "long" and _threshold_signal(s, i, th, "long"):
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side": "LONG", "entry": candles[i]["c"],
                           "sl": candles[i]["c"]-sl_mult*av, "tp": candles[i]["c"]+tp_mult*av}
                elif direction == "short" and _threshold_signal(s, i, th, "short"):
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side": "SHORT", "entry": candles[i]["c"],
                           "sl": candles[i]["c"]+sl_mult*av, "tp": candles[i]["c"]-tp_mult*av}
            else:
                ex = None
                if pos["side"] == "LONG":
                    if candles[i]["l"] <= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["h"] >= pos["tp"]: ex = pos["tp"]
                else:
                    if candles[i]["h"] >= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["l"] <= pos["tp"]: ex = pos["tp"]
                if ex:
                    trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, FEE))
                    pos = None
        return trades
    strat.__name__ = name
    return strat

# ═══════════════════════════════════════════════════════════════════
# 50 TREND STRATEGIES
# ═══════════════════════════════════════════════════════════════════
TREND_SPECS = [
    ("T_EMA_10_SMA_50", "cross", {"kind": "ema", "params": [10]}, {"kind": "sma", "params": [50]}, "both", 3.0, 6.0),
    ("T_EMA_20_SMA_100", "cross", {"kind": "ema", "params": [20]}, {"kind": "sma", "params": [100]}, "both", 3.0, 6.0),
    ("T_EMA_50_SMA_200", "cross", {"kind": "ema", "params": [50]}, {"kind": "sma", "params": [200]}, "both", 3.0, 6.0),
    ("T_EMA_9_EMA_21", "cross", {"kind": "ema", "params": [9]}, {"kind": "ema", "params": [21]}, "both", 3.0, 6.0),
    ("T_EMA_12_EMA_26", "cross", {"kind": "ema", "params": [12]}, {"kind": "ema", "params": [26]}, "both", 3.0, 6.0),
    ("T_KAMA_10_EMA_50", "cross", {"kind": "kama", "params": [10]}, {"kind": "ema", "params": [50]}, "both", 3.0, 6.0),
    ("T_KAMA_20_EMA_100", "cross", {"kind": "kama", "params": [20]}, {"kind": "ema", "params": [100]}, "both", 3.0, 6.0),
    ("T_WMA_20_EMA_50", "cross", {"kind": "wma", "params": [20]}, {"kind": "ema", "params": [50]}, "both", 3.0, 6.0),
    ("T_TEMA_20_EMA_50", "cross", {"kind": "tema", "params": [20]}, {"kind": "ema", "params": [50]}, "both", 3.0, 6.0),
    ("T_TEMA_10_EMA_30", "cross", {"kind": "tema", "params": [10]}, {"kind": "ema", "params": [30]}, "both", 3.0, 6.0),
    ("T_AROON_UP_DN", "cross", {"kind": "aroon_up", "params": [25]}, {"kind": "aroon_dn", "params": [25]}, "both", 3.0, 6.0),
    ("T_AROON_UP_70", "threshold", {"kind": "aroon_up", "params": [25]}, 70, "long", 3.0, 6.0),
    ("T_AROON_DN_30", "threshold", {"kind": "aroon_dn", "params": [25]}, 30, "short", 3.0, 6.0),
    ("T_VORTEX_LONG", "cross", {"kind": "vp", "params": [14]}, {"kind": "vm", "params": [14]}, "long", 3.0, 6.0),
    ("T_VORTEX_SHORT", "cross", {"kind": "vm", "params": [14]}, {"kind": "vp", "params": [14]}, "short", 3.0, 6.0),
    ("T_TRIX_POS", "threshold", {"kind": "trix", "params": [15]}, 0, "long", 3.0, 6.0),
    ("T_TRIX_NEG", "threshold", {"kind": "trix", "params": [15]}, 0, "short", 3.0, 6.0),
    ("T_KST_POS", "threshold", {"kind": "kst"}, 0, "long", 3.0, 6.0),
    ("T_KST_NEG", "threshold", {"kind": "kst"}, 0, "short", 3.0, 6.0),
    ("T_PSAR_FLIP_LONG", "cross", {"kind": "price"}, {"kind": "psar", "params": [0.02, 0.02, 0.2]}, "long", 3.0, 6.0),
    ("T_PSAR_FLIP_SHORT", "cross", {"kind": "psar", "params": [0.02, 0.02, 0.2]}, {"kind": "price"}, "short", 3.0, 6.0),
    ("T_DONCHIAN_HI_20", "level", {"kind": "price"}, {"kind": "dch_hi", "params": [20]}, "long", 2.5, 5.0),
    ("T_DONCHIAN_LO_20", "level", {"kind": "price"}, {"kind": "dch_lo", "params": [20]}, "short", 2.5, 5.0),
    ("T_DONCHIAN_HI_50", "level", {"kind": "price"}, {"kind": "dch_hi", "params": [50]}, "long", 2.5, 5.0),
    ("T_DONCHIAN_LO_50", "level", {"kind": "price"}, {"kind": "dch_lo", "params": [50]}, "short", 2.5, 5.0),
    ("T_DONCHIAN_HI_100", "level", {"kind": "price"}, {"kind": "dch_hi", "params": [100]}, "long", 2.5, 5.0),
    ("T_DONCHIAN_LO_100", "level", {"kind": "price"}, {"kind": "dch_lo", "params": [100]}, "short", 2.5, 5.0),
    ("T_ST_FLIP_LONG", "cross", {"kind": "price"}, {"kind": "st", "params": [10, 3.0]}, "long", 3.0, 6.0),
    ("T_ST_FLIP_SHORT", "cross", {"kind": "st", "params": [10, 3.0]}, {"kind": "price"}, "short", 3.0, 6.0),
    ("T_ST_20_2_LONG", "cross", {"kind": "price"}, {"kind": "st", "params": [20, 2.0]}, "long", 3.0, 6.0),
    ("T_ST_20_2_SHORT", "cross", {"kind": "st", "params": [20, 2.0]}, {"kind": "price"}, "short", 3.0, 6.0),
    ("T_PRICE_ABOVE_SMA50", "level", {"kind": "price"}, {"kind": "sma", "params": [50]}, "long", 3.0, 6.0),
    ("T_PRICE_BELOW_SMA50", "level", {"kind": "price"}, {"kind": "sma", "params": [50]}, "short", 3.0, 6.0),
    ("T_PRICE_ABOVE_EMA200", "level", {"kind": "price"}, {"kind": "ema", "params": [200]}, "long", 3.0, 6.0),
    ("T_PRICE_BELOW_EMA200", "level", {"kind": "price"}, {"kind": "ema", "params": [200]}, "short", 3.0, 6.0),
    ("T_PRICE_ABOVE_TEMA20", "level", {"kind": "price"}, {"kind": "tema", "params": [20]}, "long", 3.0, 6.0),
    ("T_PRICE_ABOVE_KAMA10", "level", {"kind": "price"}, {"kind": "kama", "params": [10]}, "long", 3.0, 6.0),
    ("T_PRICE_BELOW_KAMA10", "level", {"kind": "price"}, {"kind": "kama", "params": [10]}, "short", 3.0, 6.0),
    ("T_EMA9_PRICE", "cross", {"kind": "ema", "params": [9]}, {"kind": "price"}, "both", 2.5, 5.0),
    ("T_EMA21_PRICE", "cross", {"kind": "ema", "params": [21]}, {"kind": "price"}, "both", 2.5, 5.0),
    ("T_KAMA_10_PRICE", "cross", {"kind": "kama", "params": [10]}, {"kind": "price"}, "both", 2.5, 5.0),
    ("T_WMA_50_PRICE", "cross", {"kind": "wma", "params": [50]}, {"kind": "price"}, "both", 3.0, 6.0),
    ("T_TEMA_20_SMA_50", "cross", {"kind": "tema", "params": [20]}, {"kind": "sma", "params": [50]}, "both", 3.0, 6.0),
    ("T_KAMA_20_SMA_100", "cross", {"kind": "kama", "params": [20]}, {"kind": "sma", "params": [100]}, "both", 3.0, 6.0),
    ("T_VORTEX_LONG_21", "cross", {"kind": "vp", "params": [21]}, {"kind": "vm", "params": [21]}, "long", 3.0, 6.0),
    ("T_ST_10_3_BOTH", "cross", {"kind": "price"}, {"kind": "st", "params": [10, 3.0]}, "both", 3.0, 6.0),
    ("T_AROON_UP_PRICE", "cross", {"kind": "aroon_up", "params": [25]}, {"kind": "price"}, "long", 3.0, 6.0),
    ("T_DCH_EMA_CROSS", "level", {"kind": "ema", "params": [20]}, {"kind": "dch_hi", "params": [20]}, "long", 3.0, 6.0),
    ("T_PSAR_SMA", "cross", {"kind": "price"}, {"kind": "psar", "params": [0.02, 0.02, 0.2]}, "both", 3.0, 6.0),
    ("T_KAMA_TEMA", "cross", {"kind": "kama", "params": [10]}, {"kind": "tema", "params": [20]}, "both", 3.0, 6.0),
    ("T_TRIPLE_CROSS", "cross", {"kind": "ema", "params": [9]}, {"kind": "sma", "params": [21]}, "both", 3.0, 6.0),
]

TREND_STRATEGIES = {}
for spec in TREND_SPECS:
    name, typ, a_spec, b_spec, direction, sl, tp = spec
    if typ == "cross":
        func = _make_cross(name, a_spec, b_spec, direction, sl, tp)
    elif typ == "level":
        func = _make_level(name, a_spec, b_spec, direction, sl, tp)
    elif typ == "threshold":
        func = _make_threshold(name, a_spec, b_spec, direction, sl, tp)
    else:
        continue
    TREND_STRATEGIES[name] = (func, {"fee_multiplier": [1.0]})

print(f"[expansion_generated] {len(TREND_STRATEGIES)} trend strategies registered")
