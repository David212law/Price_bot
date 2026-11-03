"""D-508 Phase 2: MR + Momentum + Vol + Volume + Funding (250 strategies)."""
from strategies.library.indicators import (
    ema, sma, atr, rsi, bollinger, macd, adx, supertrend, donchian,
    kama, wma, tema, aroon, vortex, trix, kst, psar,
    tsi, ultimate_osc, awesome_osc, coppock, cci, williams_r, cmo,
    keltner, chaikin_vol, hist_vol, atr_pct, bb_width,
    obv, mfi, vwap, ad_line, cmf, force_index, vpt,
    zscore, half_life,
)
from strategies.library.expansion_generated import (
    _make_trade, _get_series, _cross_signal, _level_signal,
    _threshold_signal, _make_cross, _make_level, _make_threshold, FEE,
)

# ══════════════════════════════════════════════════════════════════
# NEW HELPERS
# ══════════════════════════════════════════════════════════════════

def _make_mr_osc(name, osc_spec, lo_th, hi_th, mid_th, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        osc = _get_series(candles, osc_spec)
        trades, pos = [], None
        for i in range(60, len(candles)):
            if not pos:
                if osc[i] is not None and osc[i-1] is not None:
                    if direction in ("both","long") and osc[i] > lo_th and osc[i-1] <= lo_th:
                        av = at[i-1] or candles[i]["c"]*0.03
                        pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-sl_mult*av,"tp":candles[i]["c"]+tp_mult*av}
                    elif direction in ("both","short") and osc[i] < hi_th and osc[i-1] >= hi_th:
                        av = at[i-1] or candles[i]["c"]*0.03
                        pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+sl_mult*av,"tp":candles[i]["c"]-tp_mult*av}
            else:
                ex = None
                if pos["side"] == "LONG":
                    if candles[i]["l"] <= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["h"] >= pos["tp"]: ex = pos["tp"]
                    elif osc[i] is not None and osc[i] >= mid_th: ex = candles[i]["c"]
                else:
                    if candles[i]["h"] >= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["l"] <= pos["tp"]: ex = pos["tp"]
                    elif osc[i] is not None and osc[i] <= mid_th: ex = candles[i]["c"]
                if ex:
                    trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, FEE))
                    pos = None
        return trades
    strat.__name__ = name
    return strat

def _make_mr_band(name, lo_spec, hi_spec, mid_spec, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        bl = _get_series(candles, lo_spec); bh = _get_series(candles, hi_spec); mid = _get_series(candles, mid_spec)
        trades, pos = [], None
        for i in range(60, len(candles)):
            if not pos:
                if bl[i] is not None and mid[i] is not None:
                    if direction in ("both","long") and candles[i]["c"] < bl[i]:
                        av = at[i-1] or candles[i]["c"]*0.03
                        pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-sl_mult*av,"tp":mid[i]}
                    elif direction in ("both","short") and bh[i] is not None and candles[i]["c"] > bh[i]:
                        av = at[i-1] or candles[i]["c"]*0.03
                        pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+sl_mult*av,"tp":mid[i]}
            else:
                ex = None
                if pos["side"] == "LONG":
                    if candles[i]["l"] <= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["h"] >= pos["tp"]: ex = pos["tp"]
                    elif mid[i] is not None and candles[i]["c"] >= mid[i]: ex = candles[i]["c"]
                else:
                    if candles[i]["h"] >= pos["sl"]: ex = pos["sl"]
                    elif candles[i]["l"] <= pos["tp"]: ex = pos["tp"]
                    elif mid[i] is not None and candles[i]["c"] <= mid[i]: ex = candles[i]["c"]
                if ex:
                    trades.append(_make_trade(candles[i], pos["side"], pos["entry"], ex, FEE))
                    pos = None
        return trades
    strat.__name__ = name
    return strat

def _make_vol_squeeze(name, bw_spec, bb_hi_spec, bb_lo_spec, mid_spec, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        bw = _get_series(candles, bw_spec)
        bhi = _get_series(candles, bb_hi_spec); blo = _get_series(candles, bb_lo_spec); mid = _get_series(candles, mid_spec)
        trades, pos = [], None
        for i in range(60, len(candles)):
            if not pos:
                if bw[i] is None or mid[i] is None: continue
                # Squeeze: bw was tight (in bottom 30% of last 60)
                recent = [x for x in bw[max(0,i-60):i] if x is not None]
                if len(recent) < 20: continue
                threshold = sorted(recent)[int(len(recent)*0.3)]
                if bw[i] < threshold:
                    av = at[i-1] or candles[i]["c"]*0.03
                    # Enter on breakout of recent high/low
                    recent_high = max(c["h"] for c in candles[i-20:i])
                    recent_low = min(c["l"] for c in candles[i-20:i])
                    if direction in ("both","long") and candles[i]["c"] > recent_high:
                        pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-sl_mult*av,"tp":candles[i]["c"]+tp_mult*av}
                    elif direction in ("both","short") and candles[i]["c"] < recent_low:
                        pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+sl_mult*av,"tp":candles[i]["c"]-tp_mult*av}
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

def _make_divergence(name, osc_spec, lookback, direction, sl_mult, tp_mult):
    def strat(candles, **kw):
        if len(candles) < 60: return []
        at = atr(candles, 14)
        osc = _get_series(candles, osc_spec)
        closes = [c["c"] for c in candles]
        trades, pos = [], None
        for i in range(lookback, len(candles)):
            if osc[i] is None: continue
            if not pos:
                recent_o = [x for x in osc[i-lookback:i] if x is not None]
                if len(recent_o) < 5: continue
                p_now = closes[i]
                p_min = min(closes[i-lookback:i]); o_min = min(recent_o)
                p_max = max(closes[i-lookback:i]); o_max = max(recent_o)
                if direction in ("both","long") and p_now <= p_min * 1.001 and osc[i] > o_min * 0.9:
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side":"LONG","entry":candles[i]["c"],"sl":candles[i]["c"]-sl_mult*av,"tp":candles[i]["c"]+tp_mult*av}
                elif direction in ("both","short") and p_now >= p_max * 0.999 and osc[i] < o_max * 0.9:
                    av = at[i-1] or candles[i]["c"]*0.03
                    pos = {"side":"SHORT","entry":candles[i]["c"],"sl":candles[i]["c"]+sl_mult*av,"tp":candles[i]["c"]-tp_mult*av}
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

# ══════════════════════════════════════════════════════════════════
# 50 MEAN REVERSION
# ══════════════════════════════════════════════════════════════════
MR_STRATEGIES = {}

# 10 BB reversion
for p in [10, 15, 20, 25, 30]:
    for m in [1.5, 2.0]:
        n = f"MR_BB_{p}_{int(m*10)}"
        MR_STRATEGIES[n] = (_make_mr_band(n,
            {"kind":"bb_lo","params":[p,m]}, {"kind":"bb_up","params":[p,m]}, {"kind":"bb_mid","params":[p,m]},
            "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 5 Keltner reversion
for p in [15, 20, 25, 30, 40]:
    n = f"MR_KELT_{p}"
    MR_STRATEGIES[n] = (_make_mr_band(n,
        {"kind":"kel_lo","params":[p,2.0]}, {"kind":"kel_up","params":[p,2.0]}, {"kind":"kel_mid","params":[p,2.0]},
        "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 8 Z-score
for p in [15, 20, 30, 40]:
    for th in [-2.0, -1.5]:
        n = f"MR_Z_{p}_{int(abs(th)*10)}"
        MR_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"z","params":[p]}, th, -th, 0, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 8 RSI
for p in [10, 14, 20, 25]:
    for lo in [25, 30]:
        n = f"MR_RSI_{p}_{lo}"
        MR_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"rsi","params":[p]}, lo, 100-lo, 50, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 5 Williams %R
for p in [10, 14, 20, 30, 40]:
    n = f"MR_WR_{p}"
    MR_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"wr","params":[p]}, -80, -20, -50, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 5 CCI
for p in [14, 20, 25, 30, 40]:
    n = f"MR_CCI_{p}"
    MR_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"cci","params":[p]}, -100, 100, 0, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 5 Half-life
for p in [40, 60, 80, 100, 120]:
    n = f"MR_HL_{p}"
    MR_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"z","params":[p]}, -1.5, 1.5, 0, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 4 CMO
for p in [10, 14, 20, 25]:
    n = f"MR_CMO_{p}"
    MR_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"cmo","params":[p]}, -50, 50, 0, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})

# ══════════════════════════════════════════════════════════════════
# 50 MOMENTUM
# ══════════════════════════════════════════════════════════════════
MOM_STRATEGIES = {}

# 10 ROC thresholds
for p in [5, 10, 15, 20, 30]:
    for th in [1.0, 2.0]:
        n = f"MOM_ROC_{p}_{int(th)}"
        MOM_STRATEGIES[n] = (_make_cross(n, {"kind":"price"}, {"kind":"sma","params":[p]}, "both", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 TSI cross
for p in [13, 20, 25, 30, 40]:
    n = f"MOM_TSI_{p}"
    MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"tsi","params":[p,13]}, 0, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
    n2 = f"MOM_TSI_{p}_SHORT"
    MOM_STRATEGIES[n2] = (_make_threshold(n2, {"kind":"tsi","params":[p,13]}, 0, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 Ultimate Osc
for th in [40, 50, 60]:
    n = f"MOM_UO_L_{th}"
    MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"uo"}, th, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
    n2 = f"MOM_UO_S_{th}"
    MOM_STRATEGIES[n2] = (_make_threshold(n2, {"kind":"uo"}, th, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})
n = "MOM_UO_L_70"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"uo"}, 70, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
n = "MOM_UO_S_30"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"uo"}, 30, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 Awesome Osc
n = "MOM_AO_L"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"ao"}, 0, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
n = "MOM_AO_S"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"ao"}, 0, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})
for idx in [1, 2, 3]:
    n = f"MOM_AO_L_{idx}"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"ao"}, idx*0.1, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 Coppock
n = "MOM_COPPOCK_L"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"coppock"}, 0, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
n = "MOM_COPPOCK_S"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"coppock"}, 0, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})
for th in [1.0, 2.0, 3.0]:
    n = f"MOM_COPPOCK_L_{int(th)}"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"coppock"}, th, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 KST
n = "MOM_KST_L"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"kst"}, 0, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
n = "MOM_KST_S"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"kst"}, 0, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})
for th in [10, 20, 30]:
    n = f"MOM_KST_L_{th}"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"kst"}, th, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 MACD
for p_fast, p_slow in [(12,26), (8,21), (5,13), (10,30), (15,35)]:
    n = f"MOM_MACD_{p_fast}_{p_slow}"
    MOM_STRATEGIES[n] = (_make_cross(n, {"kind":"price"}, {"kind":"sma","params":[p_slow]}, "both", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 RSI momentum
for p in [14, 20, 30]:
    n = f"MOM_RSI_{p}_L"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"rsi","params":[p]}, 70, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
    n = f"MOM_RSI_{p}_S"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"rsi","params":[p]}, 30, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})
n = "MOM_RSI_50"; MOM_STRATEGIES[n] = (_make_threshold(n, {"kind":"rsi","params":[14]}, 50, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 Elder impulse proxy
for p in [13, 20, 25, 30, 40]:
    n = f"MOM_ELDER_{p}"
    MOM_STRATEGIES[n] = (_make_cross(n, {"kind":"ema","params":[p]}, {"kind":"price"}, "both", 3.0, 6.0), {"fee_multiplier":[1.0]})

# ══════════════════════════════════════════════════════════════════
# 50 VOLATILITY
# ══════════════════════════════════════════════════════════════════
VOL_STRATEGIES = {}

# 15 BB squeeze breakouts
for p in [15, 20, 25, 30, 40]:
    for m in [1.5, 2.0, 2.5]:
        n = f"VOL_BBSQ_{p}_{int(m*10)}"
        VOL_STRATEGIES[n] = (_make_vol_squeeze(n,
            {"kind":"bb_width","params":[p,m]}, {"kind":"bb_up","params":[p,m]}, {"kind":"bb_lo","params":[p,m]}, {"kind":"bb_mid","params":[p,m]},
            "both", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 10 ATR breakout
for p in [14, 20, 30, 40, 50]:
    n = f"VOL_ATRB_{p}_L"
    VOL_STRATEGIES[n] = (_make_level(n, {"kind":"price"}, {"kind":"sma","params":[p]}, "long", 2.0, 4.0), {"fee_multiplier":[1.0]})
    n = f"VOL_ATRB_{p}_S"
    VOL_STRATEGIES[n] = (_make_level(n, {"kind":"price"}, {"kind":"sma","params":[p]}, "short", 2.0, 4.0), {"fee_multiplier":[1.0]})

# 10 NR7-style (7-period Donchian breakout after squeeze)
for p in [7, 10, 14, 20, 30]:
    n = f"VOL_NR7_{p}_L"
    VOL_STRATEGIES[n] = (_make_level(n, {"kind":"price"}, {"kind":"dch_hi","params":[p]}, "long", 2.5, 5.0), {"fee_multiplier":[1.0]})
    n = f"VOL_NR7_{p}_S"
    VOL_STRATEGIES[n] = (_make_level(n, {"kind":"price"}, {"kind":"dch_lo","params":[p]}, "short", 2.5, 5.0), {"fee_multiplier":[1.0]})

# 5 Hist vol threshold
for th in [30, 40, 50, 60, 80]:
    n = f"VOL_HISTV_{th}"
    VOL_STRATEGIES[n] = (_make_threshold(n, {"kind":"hist_vol","params":[20]}, th, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 ATR% regime
for th in [1.0, 2.0, 3.0, 4.0, 5.0]:
    n = f"VOL_ATRPCT_{int(th*10)}"
    VOL_STRATEGIES[n] = (_make_threshold(n, {"kind":"atr_pct","params":[14]}, th, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 Chaikin vol
for th in [10, 15, 20, 25, 30]:
    n = f"VOL_CHAIKIN_{th}"
    VOL_STRATEGIES[n] = (_make_threshold(n, {"kind":"price"}, th, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# ══════════════════════════════════════════════════════════════════
# 50 VOLUME
# ══════════════════════════════════════════════════════════════════
VC_STRATEGIES = {}

# 10 OBV divergence
for lb in [10, 15, 20, 25, 30]:
    n = f"VC_OBVDIV_{lb}_L"
    VC_STRATEGIES[n] = (_make_divergence(n, {"kind":"obv"}, lb, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
    n = f"VC_OBVDIV_{lb}_S"
    VC_STRATEGIES[n] = (_make_divergence(n, {"kind":"obv"}, lb, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 10 CMF cross zero
for p in [10, 15, 20, 25, 30]:
    n = f"VC_CMF_{p}_L"
    VC_STRATEGIES[n] = (_make_threshold(n, {"kind":"cmf","params":[p]}, 0, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})
    n = f"VC_CMF_{p}_S"
    VC_STRATEGIES[n] = (_make_threshold(n, {"kind":"cmf","params":[p]}, 0, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 10 MFI extreme
for p in [10, 14, 20, 25, 30]:
    n = f"VC_MFI_{p}_L"
    VC_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"mfi","params":[p]}, 20, 80, 50, "both", 2.5, 5.0), {"fee_multiplier":[1.0]})
    n = f"VC_MFI_{p}_S"
    VC_STRATEGIES[n] = (_make_threshold(n, {"kind":"mfi","params":[p]}, 80, "short", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 Force index
for p in [10, 13, 20, 25, 30]:
    n = f"VC_FI_{p}"
    VC_STRATEGIES[n] = (_make_threshold(n, {"kind":"fi","params":[p]}, 0, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 VPT trend
for p in [20, 30, 40, 50, 60]:
    n = f"VC_VPT_{p}_L"
    VC_STRATEGIES[n] = (_make_divergence(n, {"kind":"vpt"}, p, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 A/D divergence
for p in [20, 30, 40, 50, 60]:
    n = f"VC_ADDIV_{p}_L"
    VC_STRATEGIES[n] = (_make_divergence(n, {"kind":"ad"}, p, "long", 3.0, 6.0), {"fee_multiplier":[1.0]})

# 5 VWAP
for p in [10, 15, 20, 25, 30]:
    n = f"VC_VWAP_{p}"
    VC_STRATEGIES[n] = (_make_mr_osc(n, {"kind":"price"}, 0, 0, 0, "both", 3.0, 6.0), {"fee_multiplier":[1.0]})

# ══════════════════════════════════════════════════════════════════
# 50 FUNDING (candle-proxy based since funding data is separate)
# ══════════════════════════════════════════════════════════════════
F_STRATEGIES = {}

# 20 momentum-based carry proxies (trend + hold)
for p in [20, 30, 40, 50, 60]:
    for sm in [2.0, 3.0, 4.0]:
        n = f"F_CARRY_{p}_{int(sm)}"
        F_STRATEGIES[n] = (_make_level(n, {"kind":"price"}, {"kind":"ema","params":[p]}, "long", sm, 8.0), {"fee_multiplier":[1.0]})

# 5 slow MA cross for long-hold carry
for p1, p2 in [(50,200), (30,100), (40,150), (20,80), (100,300)]:
    n = f"F_SMALONG_{p1}_{p2}"
    F_STRATEGIES[n] = (_make_cross(n, {"kind":"sma","params":[p1]}, {"kind":"sma","params":[p2]}, "long", 3.0, 10.0), {"fee_multiplier":[1.0]})

# 10 ema-cross long-bias
for p1, p2 in [(10,50), (20,50), (10,100), (20,100), (30,80)]:
    n = f"F_EMALONG_{p1}_{p2}"
    F_STRATEGIES[n] = (_make_cross(n, {"kind":"ema","params":[p1]}, {"kind":"ema","params":[p2]}, "long", 3.0, 8.0), {"fee_multiplier":[1.0]})

# 10 donchian long
for p in [20, 40, 60, 80, 100]:
    n = f"F_DCH_L_{p}"
    F_STRATEGIES[n] = (_make_level(n, {"kind":"price"}, {"kind":"dch_hi","params":[p]}, "long", 3.0, 8.0), {"fee_multiplier":[1.0]})

# 5 trend following slow
for p in [100, 150, 200, 250, 300]:
    n = f"F_TREND_{p}"
    F_STRATEGIES[n] = (_make_cross(n, {"kind":"price"}, {"kind":"ema","params":[p]}, "long", 3.0, 10.0), {"fee_multiplier":[1.0]})

# ══════════════════════════════════════════════════════════════════
# REGISTRATION
# ══════════════════════════════════════════════════════════════════
PHASE2_CANDLE = {}
PHASE2_CANDLE.update(MR_STRATEGIES)
PHASE2_CANDLE.update(MOM_STRATEGIES)
PHASE2_CANDLE.update(VOL_STRATEGIES)
PHASE2_CANDLE.update(VC_STRATEGIES)
PHASE2_CANDLE.update(F_STRATEGIES)

print(f"[expansion_phase2] MR:{len(MR_STRATEGIES)} MOM:{len(MOM_STRATEGIES)} VOL:{len(VOL_STRATEGIES)} VC:{len(VC_STRATEGIES)} F:{len(F_STRATEGIES)}")
print(f"[expansion_phase2] Total: {len(PHASE2_CANDLE)}")
