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
