"""Funding rate strategies (5 variants of M31)."""
import math

def _daily_returns(funding_records, entry_thr, exit_thr, cooldown_h=1, leverage=3):
    """Simulate M31 with given threshold. Returns list of daily returns."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > 12: hist.pop(0)
        avg = sum(hist) / len(hist)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            daily[day] += r["rate"] * leverage
            if avg < exit_thr:
                in_pos = False
                last_exit = r["t"]
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if avg > entry_thr and r["rate"] > 0 and hours_since >= cooldown_h:
                in_pos = True
    return dict(daily)

def m31_sma(funding_records, period=12, entry_thr=0.00001, exit_thr=0.000005, leverage=3):
    """M31 with SMA(period) entry/exit. Baseline variant."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > period: hist.pop(0)
        avg = sum(hist) / len(hist)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            daily[day] += r["rate"] * leverage
            if avg < exit_thr:
                in_pos = False
                last_exit = r["t"]
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if avg > entry_thr and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_ema(funding_records, period=12, entry_thr=0.00001, exit_thr=0.000005, leverage=3):
    """M31 with EMA entry/exit."""
    from datetime import datetime, timezone
    from collections import defaultdict
    if not funding_records: return {}
    k = 2.0 / (period + 1)
    ema_v = funding_records[0]["rate"]
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        ema_v = r["rate"] * k + ema_v * (1 - k)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            daily[day] += r["rate"] * leverage
            if ema_v < exit_thr:
                in_pos = False
                last_exit = r["t"]
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if ema_v > entry_thr and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_threshold(funding_records, entry_thr=0.00003, exit_thr=0.000005, leverage=3):
    """M31 with direct threshold (no smoothing)."""
    from datetime import datetime, timezone
    from collections import defaultdict
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if in_pos:
            daily[day] += r["rate"] * leverage
            if r["rate"] < exit_thr:
                in_pos = False
                last_exit = r["t"]
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if r["rate"] > entry_thr and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_quantile(funding_records, window=50, quantile=0.7, leverage=3):
    """M31 with quantile-based threshold (dynamic)."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > window: hist.pop(0)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if len(hist) < window:
            continue
        sorted_h = sorted(hist)
        thr = sorted_h[int(len(sorted_h) * quantile)]
        if in_pos:
            daily[day] += r["rate"] * leverage
            if r["rate"] < 0:
                in_pos = False
                last_exit = r["t"]
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if r["rate"] > thr and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

def m31_momentum(funding_records, lookback=6, leverage=3):
    """M31 that enters when funding is trending up (recent > older)."""
    from datetime import datetime, timezone
    from collections import defaultdict
    hist = []
    in_pos = False
    last_exit = 0
    daily = defaultdict(float)
    for r in funding_records:
        hist.append(r["rate"])
        if len(hist) > lookback * 2: hist.pop(0)
        day = datetime.fromtimestamp(r["t"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if len(hist) < lookback * 2:
            continue
        recent_avg = sum(hist[-lookback:]) / lookback
        older_avg = sum(hist[:lookback]) / lookback
        if in_pos:
            daily[day] += r["rate"] * leverage
            if r["rate"] < 0:
                in_pos = False
                last_exit = r["t"]
        else:
            hours_since = (r["t"] - last_exit) / 3600000
            if recent_avg > older_avg and r["rate"] > 0 and hours_since >= 1:
                in_pos = True
    return dict(daily)

FUNDING_STRATEGIES = {
    "M31_SMA": (m31_sma, {"period":[12,24], "entry_thr":[0.00001], "exit_thr":[0.000005]}),
    "M31_EMA": (m31_ema, {"period":[12,24], "entry_thr":[0.00001], "exit_thr":[0.000005]}),
    "M31_THRESHOLD": (m31_threshold, {"entry_thr":[0.00003,0.00005], "exit_thr":[0.000005]}),
    "M31_QUANTILE": (m31_quantile, {"window":[30,50], "quantile":[0.6,0.7,0.8]}),
    "M31_MOMENTUM": (m31_momentum, {"lookback":[4,6,12]}),
}

# NOTE: These return dict of daily returns, NOT trade list like other strategies.
# Screening engine must handle them separately.


def strat_funding_mean_rev(records, lookback=30, z_threshold=2.0, fee_multiplier=1.0):
    """D-442: Funding MR — fade extreme funding rates (low vol by design)."""
    from collections import defaultdict
    from datetime import datetime, timezone
    if not records or len(records) < lookback * 3:
        return {}
    daily_sum = defaultdict(float); daily_n = defaultdict(int)
    for r in records:
        try:
            day = datetime.fromtimestamp(int(r["t"])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            daily_sum[day] += float(r["rate"]); daily_n[day] += 1
        except: continue
    daily = {d: daily_sum[d]/daily_n[d] for d in daily_sum if daily_n[d] > 0}
    days = sorted(daily.keys())
    if len(days) < lookback + 10: return {}
    fee = 0.0006 * fee_multiplier
    out = {}; pos = 0
    for i in range(lookback, len(days)):
        window = [daily[days[j]] for j in range(i-lookback, i)]
        m = sum(window)/len(window)
        v = sum((x-m)**2 for x in window)/(len(window)-1) if len(window) > 1 else 0
        sigma = v ** 0.5
        if sigma == 0: continue
        z = (daily[days[i]] - m) / sigma
        if pos != 0 and abs(z) < 0.5:
            pos = 0; continue
        just_entered = False
        if pos == 0:
            if z > z_threshold: pos = -1; just_entered = True
            elif z < -z_threshold: pos = 1; just_entered = True
        if pos != 0:
            daily_ret = -pos * daily[days[i]]
            if just_entered: daily_ret -= fee
            out[days[i]] = daily_ret
    return out


FUNDING_STRATEGIES["FUNDING_MEAN_REV"] = (
    strat_funding_mean_rev,
    {"lookback": [20, 30, 50], "z_threshold": [1.5, 2.0, 2.5]}
)
