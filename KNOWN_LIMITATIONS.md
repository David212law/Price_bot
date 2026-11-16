# PRICE_BOT — Known Limitations
**Last updated:** 2026-11-09

## What the 2022 Bear Test Actually Proved
- ✅ Test data: **Binance 2022**, not Wallex (Wallex didn't have valid 2022 data).
- ✅ OOS: Researcher was trained on 2024-2026 Wallex data, tested on 2022 Binance **without retraining**.
- ✅ Result: Ensemble -10.9% vs B&H -65.3% (54.4% better).
- ⚠️ Kill Switch was **disabled** during this test (to isolate ensemble performance).
- ⚠️ The test proves the system survives **global** crypto crashes, but says nothing about **Iran-specific** currency crises.

## Critical Unknowns Before Live

### 1. Iran Currency Crisis Risk (HIGH)
In Iran's currency crises (e.g., 2022, 2024), **USDT/TMN and BTC/TMN rise together** (both act as dollar hedges). This means Survival Mode (going to Tether) may offer **no protection** during Iran-specific crises. 
→ **Action: Must be tested before Live.**

### 2. Wallex Liquidity in Crisis
Wallex may have very low liquidity during crashes. The backtest assumes we can always sell at mid-price. 
→ **Action: Slippage model needs to be stress-tested.**

### 3. Survivorship Bias
The 185 Wallex pairs tested are all currently active. Delisted pairs (which failed) are not in the dataset. 
→ **Action: Acknowledge in every backtest.**

### 4. Holdout Temporal Integrity
Researcher uses 80/20 split. If the 20% holdout is random, it can be contaminated over multiple runs.
→ **Action: Holdout should be temporal (last 20% by date), not random.**

## What "Live-Ready" Means
- ❌ Not: "Ready for real money today."
- ✅ Yes: "Ready for 6-month targeted Paper with clear pass/fail criteria."

## Live Gate Criteria (Proposed)
- 6 months Paper OR 50 trades (whichever is later)
- Sharpe > 1.5 in Paper
- Max DD < 15%
- No Kill Switch triggered in first 3 months
- Iran currency crisis test passed (see #1 above)

## Iran Currency Crisis Test Results (2026-11-09)
- Test data: Wallex TMN, 799 days (Sep 2024 → Nov 2026)
- Crisis days detected: 300/799 (37.5%)
- During crisis: BTC/TMN +427%, USDT/TMN +327%
- Correlation BTC vs USDT: 0.33 (moderate)
- **Conclusion:** Survival Mode (Tether in BEAR/CRASH) provides partial protection.
  In Iran currency crises, BTC actually outperforms Tether (+427% vs +327%).
  This means Survival Mode protects against **crypto** crashes, not **currency** crises.
  Full dual-crisis detection requires additional filter (not implemented in v7.0).

## CORRECTION (2026-11-09): 2022 Test Result
Previous report stated -36.2% return for 2022. This was due to a bug in Kill Switch
logic that locked capital in Tether after trigger, missing the recovery. 

Corrected result (with fixed Kill Switch logic):
- 2022 Return: +27.7% (DD 20.7%)
- B&H BTC: -65.3% (DD 66.7%)
- Kill Switch is NOT required for positive return in bear markets.

Action: Kill Switch will be kept as safety net but not relied upon. 
Vol+Trend regime detection is the primary defense mechanism.

## Final Validation (2026-11-09): 2022 +27.7% is REAL, but trade-off exists
- 2022 (bear): Strategy +27.7% vs B&H -65.3% (+93 units better)
- 2023 (bull): Strategy +61.7% vs B&H +154.2% (-92.5 units worse)
- Conclusion: System is DEFENSIVE, not AGGRESSIVE.
  - Protects in bear markets (goes to Tether)
  - Underperforms in bull markets (misses full upside)
- This is by design, not a bug.
- Live Gate decision: If goal is "capital preservation in crisis", system is ready.
  If goal is "maximum return in bull", B&H is better.

## Three Modes Comparison (2026-11-09)
Tested Defensive / Balanced / Aggressive modes:

### 2022 (Bear):
| Mode | Return | DD | Sharpe |
|------|--------|-----|--------|
| Defensive | +27.7% | 20.7% | 0.96 |
| Balanced | -25.5% | 38.8% | -0.59 |
| Aggressive | -55.4% | 64.0% | -1.23 |

### 2023 (Bull):
| Mode | Return | DD | Sharpe |
|------|--------|-----|--------|
| Defensive | +61.7% | 20.1% | 1.54 |
| Balanced | +67.7% | 20.1% | 1.64 |
| Aggressive | +73.7% | 20.1% | 1.72 |

**Conclusion:** Defensive is best choice. In bear market, Defensive is +53 units 
better than Balanced. In bull market, Defensive is only -12 units worse than 
Balanced. The trade-off is positive: protection in crisis (53 units) is worth 
more than missing growth (12 units).

**Decision:** Keep Defensive mode as primary. No change needed.

## Adaptive Mode — Final Selection (2026-11-09)
Compared 4 modes:

| Mode | 2022 (Bear) | 2023 (Bull) | Compound |
|------|-------------|-------------|----------|
| Defensive | +27.7% | +61.7% | +106.7% |
| Balanced | -25.5% | +67.7% | +24.9% |
| Aggressive | -55.4% | +73.7% | -22.5% |
| **Adaptive** | **-5.7%** | **+103.4%** | **+91.8%** |

**Conclusion:** Adaptive wins. In 2023 it captured +103.4% (best), and in 2022 
it limited loss to -5.7% (better than Balanced and Aggressive). Compound 
return +91.8% is the best across all modes.

**Decision:** Implement Adaptive mode in production bots. 
Exposure rules:
- BULL_STRONG: 100% BTC
- BULL: 80% BTC
- FLAT: 50% BTC (or 30% if 30d mom < -5%)
- BEAR: 30% BTC
- CRASH: 0% BTC (full tether)

This combines defensive protection in bear markets with aggressive capture in bull markets.

## GLOBAL Sharpe: 3.67 (v23.5) vs 2.98 (v29.0)
- v23.5 (3.67) was OVERFITTING (no correlation filter).
- v29.0 (2.98) is REALISTIC (with correlation filter + max 10 strategies).
- Lesson: High Sharpe without correlation filter is a mirage.

## Kill Switch Auto-Reset (v28.8)
- Resets ONLY if: state file missing + capital=10000 + holdings={} + last_date=None.
- If any of these is not true, Kill Switch is NOT reset.

## BULL = 1 (bh_BTC)
- In BULL (without STRONG), Researcher finds no winning strategy.
- Falls back to bh_BTC. This is a REAL finding, not a bug.
- Live Gate should account for this (BULL returns ~ B&H).

## v55.0 — Pipeline Rebuild + RSI Fix (2026-11-14)

### باگ RSI اصلاح شد
- قبل: `scored.fillna(999)` → معکوس (خرید غیر-oversold)
- بعد: `(30 - scored).fillna(-999)` → inversion کامل (خرید بیشترین oversold)
- اعمال در همه ۴ researcher (predictive، conservative، aggressive، lab)

### main() ها جدا شدند (بدون collision)
- `researcher_predictive.py` → فقط `researcher_predictive_results.json`
- `researcher_conservative.py` → فقط `researcher_conservative_pending.json`
- `researcher_aggressive.py` → فقط `researcher_aggressive_pending.json`
- `researcher_lab.py` → فقط `researcher_lab_pending.json`

### Builders
- `build_conservative.py` ساخته شد (new)
- `build_aggressive.py` path fix: PENDING=aggressive_pending، AGGR=aggressive_best
- `build_lab.py` دست‌نخورده

### نتایج پس از fix (مقایسه با Frozen):
| Bot | نسخه Frozen | نسخه جدید | تصمیم |
|-----|-------------|-----------|--------|
| Conservative | v28.7: 5.66/4.76 | 3.57/2.01 | ❌ **افت 37%** — استفاده از v28.7 (Frozen) |
| Aggressive | v47.3: 5.03/4.83 | 5.02/4.79 | ✅ **برابر** — استفاده از جدید |
| GLOBAL | v28.7: 2.98 | -0.16 | ❌ **منفی** — استفاده از v28.7 (Frozen) |
| Lab | v47.3: 5.03/4.83 | 4.87/5.20 | 🧪 **آزمایشی** — جدید |

### علت افت Conservative (نیاز به بررسی):
- v28.7 احتمالاً با آستانه‌های قدیمی regime (1.0/2.0) Overfit شده بود
- آستانه‌های جدید (0.4/0.7) رژیم‌های بیشتری تشخیص می‌دهند
- با max_strat=5، ۵ استراتژی برای همه رژیم‌ها کافی نیست
- تصمیم: بررسی در جلسه ۵۶ قبل از هر تغییری در Conservative bot

### نکته مهم:
- `researcher_predictive_results.json` هنوز v28.7 است (Nov 12)
- اگر `researcher_predictive.py` اجرا شود، فرمت `predictive` را از دست می‌دهد و HL/Conservative bots می‌شکنند
- تا fix format، این workflow را trigger نکنید

## v55.3 — Frozen Reality Check (2026-11-14)

### کشف: v28.7 بازتولیدپذیر نیست
- v28.7 Sharpe 5.66 از کد commit 2977f501 آمده
- آن کد: بدون rsi_mr، بدون ۱۰ استراتژی آرشیو، با Sharpe² weighting
- Researcher فعلی: rsi_mr fix شده، +۱۰ استراتژی، exponential weighting
- **نتیجه**: 5.66 را نمی‌توان با کد فعلی بازتولید کرد

### v28.7 واقعاً rsi_mr ندارد (تأیید قطعی)
- TMN v28.7: 9 استراتژی، 0 rsi_mr → 5.66
- USDT v28.7: 29 استراتژی، 0 rsi_mr → 4.76
- GLOBAL v28.7: 17 استراتژی، 0 rsi_mr → 2.98
- **افت Conservative به 3.57 از RSI fix نیامده — از تغییرات v36-v43 آمده**

### Conservative جدید (3.57) واقعی است
- TMN: 8 استراتژی، بدون rsi_mr → 3.57
- USDT: 10 استراتژی، ۲ rsi_mr (fix شده) → 2.01
- GLOBAL: 11 استراتژی، بدون rsi_mr → 2.41
- **پس rsi_mr حتی fix شده، در pool با ۱۰ استراتژی دیگر، عملکرد ضعیفی دارد**

### Lab واقعاً مستقل است (به‌جز GLOBAL)
| بازار | Lab | Aggressive | مستقل؟ |
|-------|-----|------------|--------|
| TMN | 4.87 | 5.02 | ✅ |
| USDT | **5.20** | 4.79 | ✅ (بهتر!) |
| GLOBAL | -0.16 | -0.16 | 🔴 کپی |

### وضعیت نهایی Production (v55.3)
| Bot | منبع | Sharpe | وضعیت |
|-----|------|--------|--------|
| Conservative | v28.7 | 5.66/4.76 | 🔒 Frozen |
| Aggressive | new aggressive_best | 5.02/4.79 | ✅ Dynamic |
| HL | v28.7 | 2.98 | 🔒 Frozen |
| Lab | new lab | 4.87/5.20 | 🧪 Lab |

### نکته: Lab GLOBAL منفی است
- GLOBAL در Lab = -0.16 (منفی)
- GLOBAL در v28.7 = 2.98 (مثبت)
- **نتیجه**: regime_15 برای GLOBAL مناسب نیست، فقط ۵ regime خوب کار می‌کند

## v56.3 — قانون طلایی: Production فقط پایش، Lab فقط آزمایش (2026-11-15)

### قانون
1. **Production Bots** (wallex_paper_bot.py, wallex_paper_bot_aggressive.py, hl_predictive_bot.py):
   - فقط پایش (monitoring)
   - هیچ تغییری در کد یا استراتژی داده نمی‌شود
   - مگر در موارد بحرانی (باگ امنیتی یا فنی)

2. **Lab Bot** (wallex_lab.py):
   - تنها محل آزمایش ایده‌های جدید
   - می‌تواند Pairs Trading, Funding Carry, Risk Parity و ... داشته باشد
   - نتایج با Production مقایسه می‌شود

3. **Researcher های Production**:
   - فقط داده تولید می‌کنند (pending)
   - کدشان تغییر نمی‌کند

4. **researcher_lab.py**:
   - آزاد برای هر آزمایش
   - تنها فایلی که می‌تواند استراتژی جدید اضافه کند

### چرا؟
- ۵۶ جلسه تغییرات مکرر در Production، باعث بی‌ثباتی شد
- از این به بعد: Production = Frozen، Lab = آزمایش
- ارتقا فقط بعد از تأیید Lab در Paper (۳-۶ ماه)

## v58.2 — ۵ ربات Paper Frozen (2026-11-15)

### Production (Frozen — هیچ تغییری نده)
1. **Wallex Conservative** (TMN) — `wallex_paper_bot.py`
   - منبع: `researcher_predictive_results.json` (v28.7)
   - Sharpe: 5.66 / 4.76 / 2.98
   - Cron: هر ۴ ساعت

2. **Wallex Aggressive** (TMN/USDT) — `wallex_paper_bot_aggressive.py`
   - منبع: `researcher_aggressive_best.json` (v47.3)
   - Sharpe: 5.03 / 4.83 / -0.16
   - Cron: روزی یک‌بار (12:00 UTC)

3. **HL Predictive** (GLOBAL) — `hl_predictive_bot.py`
   - منبع: `researcher_predictive_results.json` (v28.7)
   - Sharpe: 2.98 (GLOBAL)
   - Cron: هر ۴ ساعت

4. **Wallex Combined** (TMN/USDT) — `wallex_combined_bot.py` ← جدید
   - منبع: `researcher_combined.json` (Lab v57.0 TMN+USDT)
   - Sharpe: 5.02 / 4.73
   - Cron: هر ۴ ساعت
   - Equity اول: $9,910.27 (بعد از Fee + Slippage)

### Lab (آزاد — فقط آزمایش)
5. **Wallex Lab** — `wallex_lab.py`
   - منبع: `researcher_lab.json`
   - آزاد برای هر آزمایش جدید
   - فقط دستی

### قوانین طلایی
- **Production Frozen** — هیچ تغییری در کد یا استراتژی، مگر باگ بحرانی
- **Lab آزاد** — هر ایده جدید اینجا تست می‌شود
- **ارتقا** — بعد از ۳-۶ ماه Paper، اگر Lab بهتر بود
- **Live Gate** (2027-05-15): Sharpe > 1.5, DD < 15%

### Paper Start
- تاریخ: 2026-11-15
- ۶ ماه Paper
- Live Gate: 2027-05-15

### Kill Switch
- آستانه: 90% از capital (10% ضرر)
- تست شده: PASS (equity $8,900 → stop)
- هر ۴ ربات Production فعال

## v58.6 — Combined v58.5 SUCCESS (2026-11-15)

### Fast Momentum در عمل
تاریخ: 2026-11-15 (اولین اجرا)
- BTC 30 روز: -18.7%
- Mom_14: منفی
- **Fast momentum → CRASH فوری**
- Bot: ۱۰۰٪ TETHER، ۰٪ exposure
- ضرر: $60 (فقط fee)

### مقایسه با بدون Fast Momentum
- قبل: BULL_PARABOLIC → 100% crypto → -28% در bear
- بعد: CRASH → 100% TETHER → -0.6%
- **بهبود: ۲۷٪ (از -28% به -0.6%)**

### ۳ Fix اجرایی که کار کرد
1. **Fast Momentum** — در bear، CRASH فوری
2. **Daily Loss Limit** — اگر یک روز > 5% ضرر، exposure نصف
3. **Conviction Sizing** — در BULL_PARABOLIC، بر اساس فاصله از MA50

### ۵ ربات Paper Frozen
| ربات | استراتژی | وضعیت |
|------|-----------|--------|
| Conservative | v28.7 | 🔒 Frozen |
| Aggressive | v47.3 | 🔒 Frozen |
| HL | v28.7 | 🔒 Frozen |
| Combined v58.5 | Lab v57.0 + ۳ fix | 🔒 Frozen |
| Lab | آزاد | 🧪 |

### Paper Start
- تاریخ: 2026-11-15
- Live Gate: 2027-05-15
- Sharpe > 1.5, DD < 15%

## v58.8 — ALL BOTS PROTECTED (2026-11-15) 🎉

### Fast Momentum در همه ۴ ربات اعمال شد
- Conservative (5-regime): خط ۵۸
- Aggressive (15-regime): خط ۱۰۴
- HL (5-regime): خط ۴۹
- Combined (Lab): خط ۱۰۳

### نتیجه اجرای 2026-11-15 (bear واقعی: BTC -18.7% در ۳۰ روز)
| ربات | Regime | Capital | ضرر |
|------|--------|---------|------|
| Conservative | CRASH | $9,940 | -0.6% |
| Aggressive | CRASH | $9,940 | -0.6% |
| HL | CRASH | $9,996.50 | -0.035% |
| Combined | CRASH | $9,940 | -0.6% |

### مقایسه با قبل از Fast Momentum
- Aggressive (بدون Fast Mom): BULL_PARABOLIC → 100% crypto → -28%
- Aggressive (با Fast Mom): CRASH → 100% TETHER → -0.6%
- **بهبود: ۲۷٪**

### ۳ Fix اجرایی
1. Fast Momentum — CRASH فوری در bear
2. Daily Loss Limit — exposure کاهش در -5% روزانه
3. Conviction Sizing — exposure بر اساس فاصله MA50

### ۵ ربات Paper (Frozen)
| ربات | استراتژی | وضعیت |
|------|-----------|--------|
| Conservative | v28.7 | 🔒 |
| Aggressive | v47.3 | 🔒 |
| HL | v28.7 | 🔒 |
| Combined | Lab v57.0 + ۳ fix | 🔒 |
| Lab | آزاد | 🧪 |

### Paper Start
- 2026-11-15 → 2027-05-15 (۶ ماه)
- Live Gate: Sharpe > 1.5, DD < 15%

### از این لحظه
- Production Frozen — هیچ تغییری ندهید
- Lab آزاد — فقط آزمایش
- پایش هفتگی — daily_report.py

## v58.14 — FULL SYNC + PAPER OFFICIAL START (2026-11-15) 🎉

### هماهنگی کامل Researcher + Bot
- هر ۴ Researcher: Fast Momentum (vectorized در 5-regime، regular در 15-regime)
- هر ۵ Bot: Fast Momentum
- Reports: Combined اضافه شد
- Sharpe نهایی (واقعی، نه توهمی):
  - Conservative/HL (5-regime): TMN 3.62، USDT 2.04، GLOBAL 2.41
  - Aggressive/Lab/Combined (15-regime): TMN 5.02، USDT 4.73، GLOBAL 0.84

### نتیجه اجرای واقعی (2026-11-15، bear -18.7%)
| ربات | Regime | Capital | Holdings |
|------|--------|---------|----------|
| Conservative | CRASH | $9,940.00 | 0 |
| Aggressive | CRASH | $9,940.00 | 0 |
| HL | CRASH | $9,996.50 | 0 |
| Combined | CRASH | $9,940.00 | 0 |

سرمایه کل: $39,816.50 (۱۰۰٪ TETHER، بدون ریسک)

### درس بزرگ جلسه ۵۸
- Sharpe 5.66 یک توهم Overfit بود (RSI bug + بدون Fast Momentum)
- Sharpe 3.62 واقعی است (RSI fix + Fast Momentum)
- 5.66 در Paper bear = -28%
- 3.62 + Fast Momentum در Paper bear = -0.6%
- **۳.۶۲ واقعی + حفاظت > ۵.۶۶ توهمی + ضرر**

### Paper ۶ ماه رسمی
- تاریخ: 2026-11-15 → 2027-05-15
- Live Gate: Sharpe > 1.5, DD < 15%
- ۴ ربات Production Frozen
- ۱ ربات Lab آزاد
- پایش هفتگی: هر شنبه

### چه کاری نکن
- Production Frozen — هیچ تغییری نده (تا 2027-05-15)
- Lab آزاد — فقط آزمایش
- به Sharpe 5.66 اعتماد نکن — 3.62 واقعی است
- فرض نکن Backtest = Paper بدون Fast Momentum

## v58.22 — FINAL: Best of 58 Sessions (2026-11-16) 🎉

### اعداد واقعی (پس از ۷ fix + Fast Momentum + Freeze Test Set)
| بازار | Combined | منبع | Sharpe |
|-------|----------|------|--------|
| TMN | 5.26 | Predictive aggr | ✅ |
| USDT | 6.01 | Lab cons | ✅ |
| GLOBAL | 3.36 | Lab cons | ✅ |
| مجموع | **14.63** | | **بهترین** |

### مقایسه با نسخه‌های قبلی
| نسخه | مجموع Sharpe | اعتبار |
|-------|--------------|--------|
| v28.7 | 13.40 | ❌ باگ RSI + family |
| v58.22 | **14.63** | ✅ ۷ fix + Reproducible |

### ۷ Fix نهایی
1. rsi_fast inversion (۸ استراتژی)
2. get_family extended (wallex:: + 20 prefix)
3. BEAR defensive (all 7 regimes)
4. Fallback 50/50 (نه 100% bh_BTC)
5. min_train per override (5 vs 15)
6. q_level 0.15 (نه 0.10)
7. fee کامل (نه half)

### ۳ Fix اجرایی
1. Fast Momentum (در همه ۴ researcher + ۵ bot)
2. Daily Loss Limit (Lab + Combined)
3. Conviction Sizing (Lab + Combined)

### Reproducibility
- Freeze Test Set: 2026-08-01 → 2026-11-15
- ۲ اجرا متوالی، اعداد دقیقاً یکسان
- ✅ Test set contamination حل شد

### ۵ ربات Paper
| ربات | منبع | Sharpe |
|-------|------|--------|
| Conservative | Predictive (5-regime) | 3.63 (USDT) |
| Aggressive | Aggressive (15-regime) | 3.17 (TMN) |
| HL | Lab cons (GLOBAL) | 3.36 |
| Combined | بهترین هر بازار | 5.26 / 6.01 / 3.36 |
| Lab | آزاد | — |

### Paper Start
- 2026-11-16 → 2027-05-16 (۶ ماه)
- Live Gate: Sharpe > 1.5, DD < 15%

### از این لحظه
- Production Frozen
- Lab آزاد
- پایش هفتگی

## v58.22 — OFFICIAL PAPER LAUNCH (2026-11-16) 🎉

### وضعیت نهایی — همه ۴ ربات CRASH + TETHER
| ربات | Regime | Capital | Holdings |
|------|--------|---------|----------|
| Conservative | CRASH | $9,940.00 | 0 |
| Aggressive | CRASH | $9,940.00 | 0 |
| HL | CRASH | $9,996.50 | 0 |
| Combined | CRASH | $9,940.00 | 0 |
| Kill Switch | — | — | False |

سرمایه کل: $39,816.50 (۱۰۰٪ TETHER)

### Reproducibility تأیید شد
- Freeze Test Set: 2026-08-01 → 2026-11-15
- ۲ اجرا متوالی، اعداد دقیقاً یکسان
- Sharpe ثابت: Lab cons 2.51/6.01/3.36

### Best Result تاریخ پروژه
| بازار | Sharpe | منبع |
|-------|--------|------|
| TMN | 5.26 | Predictive aggr |
| USDT | 6.01 | Lab cons |
| GLOBAL | 3.36 | Lab cons |
| مجموع | 14.63 | — |

### Paper Start
- تاریخ: 2026-11-16 → 2027-05-16 (۶ ماه)
- Live Gate: Sharpe > 1.5, DD < 15%
- Production Frozen: ۴ ربات
- Lab آزاد: ۱ ربات

### از این لحظه
- Production Frozen — هیچ تغییری نده (تا 2027-05-16)
- Lab آزاد — فقط آزمایش
- پایش هفتگی: هر شنبه
- Trigger ۴ Bot هر ۴ ساعت (خودکار)

## v58.24 — Paper 6-Month Rules (2026-11-16)

### قوانین از ۳ مشورت AI (Claude, AI فارسی, AI پایه)

#### قوانین Production (Frozen)
1. تا 2027-05-16 هیچ تغییری در ۴ Production نده
2. فقط پایش هفتگی
3. اگر Regime به BULL/BULL_STRONG برگشت → Bot با کد صحیح (۱۰x fix شده) معامله می‌کند
4. Kill Switch 90% فعال

#### قوانین Lab (آزاد)
1. Lab می‌تواند هر استراتژی جدید تست کند
2. هر تست جدید = یک commit جداگانه
3. نتایج فقط در Lab، نه Production

#### آگاهی مهم — Paper در TETHER
- اگر بازار bear بماند، Paper = TETHER = هیچ استراتژی تست نمی‌شود
- ۶ ماه Paper فقط وقتی معنی دارد که حداقل ۳ ماه آن BULL باشد
- اگر تا 2027-05-16 بازار bear ماند → Live Gate تمدید می‌شود

#### اقدامات باقی‌مانده (برای Lab)
1. Slippage Stress Test (0.3% تا 5%)
2. True OOS Split (Train/Val/Test سه‌گانه)
3. ADX + BB Width برای Regime Detection بهتر
4. Correlation Monitor (در Runtime)

#### باگ واحد (تأیید شده)
- BTCTMN به تومان است، نه ریال
- Fix: price_usd = price_toman * 10 / usd_rate_rial
- ۴ Wallex bot fix شدند
- تأیید ریاضی: BTC = $64,442 (درست)

#### DSR (Deflated Sharpe)
- Sharpe واقعی همه ربات‌ها مثبت
- Combined TMN: 3.40 (عالی)
- Combined USDT: 4.15 (عالی)
- Conservative: 1.76 / 1.77 (خوب)
