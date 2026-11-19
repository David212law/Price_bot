"""M12 Calc — only place where math happens."""

def regime_label(ret_30d):
    if ret_30d > 0.10:  return "BULL"
    if ret_30d > -0.10: return "FLAT"
    if ret_30d > -0.25: return "BEAR"
    return "CRASH"

def win_rate(wons):
    if not wons: return 0.0
    return round(sum(wons) / len(wons), 4)

def mean(vals):
    if not vals: return 0.0
    return round(sum(vals) / len(vals), 6)

def sharpe(returns, periods_per_year=1):
    if len(returns) < 2: return 0.0
    m = mean(returns)
    var = sum((x - m) ** 2 for x in returns) / (len(returns) - 1)
    s = var ** 0.5
    if s == 0: return 0.0
    return round(m / s * (periods_per_year ** 0.5), 4)

def bootstrap_ci(returns, n_iter=200, conf=0.95, seed=42):
    import random
    if len(returns) < 10: return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(n_iter):
        s = [rng.choice(returns) for _ in returns]
        means.append(sum(s) / len(s))
    means.sort()
    lo = means[int((1-conf)/2 * n_iter)]
    hi = means[int((1-(1-conf)/2) * n_iter)]
    return (round(lo, 6), round(hi, 6))

def normalize(d):
    total = sum(d.values())
    if total == 0: return {k: 0.0 for k in d}
    return {k: round(v / total, 4) for k, v in d.items()}

def correlation(x, y):
    """Pearson correlation. Requires same length, n>=3."""
    if len(x) != len(y) or len(x) < 3:
        return 0.0
    n = len(x)
    mx, my = sum(x)/n, sum(y)/n
    cov = sum((x[i]-mx)*(y[i]-my) for i in range(n)) / (n-1)
    sx = (sum((v-mx)**2 for v in x) / (n-1)) ** 0.5
    sy = (sum((v-my)**2 for v in y) / (n-1)) ** 0.5
    if sx == 0 or sy == 0: return 0.0
    return round(cov / (sx * sy), 4)


# ═════ Bot position math (testable) ═════

def cost_basis(qty, entry):
    return round(qty * entry, 4)

def pnl_long(qty, entry, exit_price, fee):
    notional = qty * entry + qty * exit_price
    return round(qty * (exit_price - entry) - notional * fee / 2, 4)

def pnl_short(qty, entry, exit_price, fee):
    notional = qty * entry + qty * exit_price
    return round(qty * (entry - exit_price) - notional * fee / 2, 4)

def position_qty(capital, size_pct, price):
    if capital <= 0 or price <= 0 or size_pct <= 0:
        return 0.0
    return round((capital * size_pct) / price, 8)

def sl_tp(entry, side, sl_pct=0.05, tp_pct=0.10):
    if side == "LONG":
        return round(entry*(1-sl_pct),6), round(entry*(1+tp_pct),6)
    return round(entry*(1+sl_pct),6), round(entry*(1-tp_pct),6)

def should_close(side, cur, sl, tp):
    if side == "LONG":
        if cur <= sl: return "SL"
        if cur >= tp: return "TP"
    else:
        if cur >= sl: return "SL"
        if cur <= tp: return "TP"
    return None

def should_kill(equity, initial, threshold=0.85):
    return equity < initial * threshold
