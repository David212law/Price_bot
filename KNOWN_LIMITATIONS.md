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
