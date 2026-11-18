"""M12 Strategies — all 43 from library (Trade API)."""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from strategies.library.trend import (strat_ema_cross, strat_macd, strat_adx_trend,
    strat_supertrend, strat_donchian, strat_ichimoku, strat_price_sma,
    strat_dual_momentum, strat_triple_ema, strat_parabolic_sar)
from strategies.library.mean_reversion import (strat_bollinger, strat_rsi_reversal,
    strat_zscore, strat_keltner_reversion, strat_rsi_divergence, strat_mean_rev_sma,
    strat_connors_rsi, strat_rsi_mean)
from strategies.library.momentum import (strat_roc, strat_momentum_sma,
    strat_momentum_ema, strat_elder_impulse, strat_rsi_momentum, strat_price_momentum)
from strategies.library.volatility import (strat_bb_squeeze, strat_atr_breakout,
    strat_keltner_squeeze, strat_vol_breakout_donchian, strat_nr_breakout)
from strategies.library.volume import strat_obv, strat_vwap, strat_mfi, strat_volume_breakout

STRATEGIES = {
    "ema_cross_20_50": lambda c: strat_ema_cross(c, 20, 50),
    "ema_cross_50_200": lambda c: strat_ema_cross(c, 50, 200),
    "macd_12_26": lambda c: strat_macd(c, 12, 26, 9),
    "adx_trend": lambda c: strat_adx_trend(c, 14, 25),
    "supertrend": lambda c: strat_supertrend(c, 10, 3.0),
    "donchian_20": lambda c: strat_donchian(c, 20),
    "ichimoku": lambda c: strat_ichimoku(c, 9, 26),
    "price_sma_50": lambda c: strat_price_sma(c, 50),
    "dual_momentum": lambda c: strat_dual_momentum(c, 20, 50),
    "triple_ema": lambda c: strat_triple_ema(c, 10, 20, 50),
    "parabolic_sar": lambda c: strat_parabolic_sar(c),
    "bb_20_2": lambda c: strat_bollinger(c, 20, 2.0),
    "bb_30_2.5": lambda c: strat_bollinger(c, 30, 2.5),
    "rsi_14_30_70": lambda c: strat_rsi_reversal(c, 14, 30, 70),
    "rsi_21_25_75": lambda c: strat_rsi_reversal(c, 21, 25, 75),
    "zscore_20": lambda c: strat_zscore(c, 20, 2.0),
    "keltner_rev": lambda c: strat_keltner_reversion(c, 20, 2.0),
    "rsi_divergence": lambda c: strat_rsi_divergence(c, 14, 10),
    "mean_rev_sma_50": lambda c: strat_mean_rev_sma(c, 50, 0.02),
    "connors_rsi": lambda c: strat_connors_rsi(c, 3, 200),
    "rsi_mean": lambda c: strat_rsi_mean(c, 14, 40, 60),
    "roc_10": lambda c: strat_roc(c, 10, 0.02),
    "roc_20": lambda c: strat_roc(c, 20, 0.02),
    "momentum_sma_20": lambda c: strat_momentum_sma(c, 20, 0.01),
    "momentum_ema": lambda c: strat_momentum_ema(c, 10, 30),
    "elder_impulse": lambda c: strat_elder_impulse(c, 13),
    "rsi_momentum_14": lambda c: strat_rsi_momentum(c, 14, 60),
    "price_momentum_20": lambda c: strat_price_momentum(c, 20, 0.015),
    "bb_squeeze_20": lambda c: strat_bb_squeeze(c, 20, 50),
    "atr_breakout_14": lambda c: strat_atr_breakout(c, 14, 1.5),
    "keltner_squeeze": lambda c: strat_keltner_squeeze(c, 20, 2.0),
    "vol_breakout_donch": lambda c: strat_vol_breakout_donchian(c, 20, 1.0),
    "nr_breakout": lambda c: strat_nr_breakout(c, 7, 20),
    "obv": lambda c: strat_obv(c, 20),
    "vwap": lambda c: strat_vwap(c, 20, 0.01),
    "mfi": lambda c: strat_mfi(c, 14, 20, 80),
    "volume_breakout": lambda c: strat_volume_breakout(c, 20, 2.0),
}
