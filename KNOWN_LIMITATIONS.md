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
