# PRICE_BOT — Current State Snapshot
**تاریخ:** 2026-11-16 | **نسخه:** v58.24 | **جلسه:** ۵۹

## وضعیت Git
c5366f7c v58.24: Paper 6-month rules from 3 AI consultations + unit fix confirmed


## ۴ ربات Production (Frozen)

| ربات | فایل | Regime | Capital | حفاظت |
|------|------|--------|---------|-------|
| Conservative | wallex_paper_bot.py | CRASH | $9,940 | TETHER |
| Aggressive | wallex_paper_bot_aggressive.py | CRASH | $9,940 | TETHER |
| HL | hl_predictive_bot.py | CRASH | $9,996.50 | TETHER |
| Combined | wallex_combined_bot.py | CRASH | $9,940 | TETHER |

## ۱ ربات Lab

| ربات | فایل | Cron |
|------|------|------|
| Lab | wallex_lab.py | دستی |

## ۳ Researcher فعال

| Researcher | خطوط | خروجی | Sharpe |
|------------|------|--------|--------|
| researcher_predictive.py | 858 | researcher_pending.json | TMN 3.62 / USDT 3.63 / GLOBAL 2.41 |
| researcher_lab.py | 912 | researcher_lab_pending.json | TMN 2.51 / USDT 6.01 / GLOBAL 3.36 |
| researcher_aggressive.py | 843 | researcher_aggressive_pending.json | TMN 3.17 / USDT 2.50 / GLOBAL 3.21 |

## Sharpe نهایی (با DSR)

| ربات | ادعایی | DSR واقعی |
|------|--------|-----------|
| Conservative TMN | 3.62 | 1.76 |
| Conservative USDT | 3.63 | 1.77 |
| Aggressive TMN | 3.17 | 1.31 |
| Aggressive USDT | 2.50 | 0.64 |
| Aggressive GLOBAL | 3.21 | 1.35 |
| Lab TMN | 2.51 | 0.65 |
| Lab USDT | 6.01 | 4.15 |
| Lab GLOBAL | 3.36 | 1.50 |
| Combined TMN | 5.26 | 3.40 |
| Combined USDT | 6.01 | 4.15 |

## باگ‌های fix شده (جلسه ۵۹)

1. RSI Mean Reversion معکوس (باگ ۱)
2. rsi_fast معکوس (باگ ۲)
3. ریال↔دلار در Wallex (باگ ۳)
4. TETHER گم در HL + ۳ Wallex (باگ ۴+۵)
5. Weight normalization در Combined (باگ ۶)
6. get_family ناقص (باگ ۷)
7. **Test Set Contamination** (باگ ۸)
8. **BTCTMN تومان نه ریال** (باگ ۹ — unit ۱۰x)

## قوانین Frozen

- **Production:** ۴ ربات Frozen تا 2027-05-16
- **Lab:** آزاد برای آزمایش
- **Kill Switch:** 90% (تست شده)
- **Fast Momentum:** در همه ۵ ربات
- **Freeze Test Set:** 2026-08-01 تا 2026-11-15

## Paper 6 ماه

- **شروع:** 2026-11-16
- **پایان:** 2027-05-16
- **Live Gate:** Sharpe > 1.5, DD < 15%

## اقدامات باقی‌مانده (جلسه ۶۰)

1. Slippage Stress Test (Lab)
2. True OOS Split (Train/Val/Test)
3. ADX + BB Width (Lab)
4. Correlation Monitor (Runtime)

## آمار پروژه

- کل فایل‌های Python: 22
- کل خطوط Python: 6524
- کل Workflows: 19
- فضای data/: 28M
- فضای archive/: 7.2M
- کل پروژه: 186M
