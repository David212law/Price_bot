"""M12 Researcher v2 — همه ثابت‌ها در یک جا.

این فایل **تنها منبع حقیقت** برای ثابت‌های researcher است.
"""

# ─── Fees (نرخ کارمزد per market) ───
FEE = {
    "TMN": 0.006,
    "USDT": 0.0026,
    "GLOBAL": 0.001,
}

# ─── Backtest parameters ───
SPREAD = 0.005
START_MS = 1700000000000
DAY_MS = 86400000
MAX_SYMBOLS = 185

# ─── OOS Split ───
SPLIT_PCT = 0.7

# ─── Strategy selection ───
MIN_TRADES_DEFAULT = 20
MIN_TRADES_CRASH = 5
WR_THRESHOLD_DEFAULT = 0.52
WR_THRESHOLD_CRASH = 0.50
CORRELATION_MAX = 0.5

# ─── Regimes ───
REGIMES = ["BULL", "FLAT", "BEAR", "CRASH"]

# ─── Paths ───
DEFAULT_DATA_DIR = "data"
DEFAULT_CONFIG_FILE = "m12/config.json"
DEFAULT_RESULTS_DIR = "results"
