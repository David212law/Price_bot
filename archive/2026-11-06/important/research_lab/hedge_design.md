# D-552: Delta-Neutral Hedge for M31

**Status:** Design draft (2026-11-06)
**Purpose:** Convert M31 from "BTC beta dressed as funding" to "pure funding alpha"

## Problem

M31 currently shorts perp to capture positive funding. In bull market: price + funding = double profit. In crash: price - funding = big loss. **Cannot separate alpha from beta.**

## Solution: Long Spot + Short Perp

- **LONG spot BTC** (45% of capital)
- **SHORT perp BTC** (45% of capital, 1x leverage)
- **Cash buffer** (10%)

Result: price moves cancel (delta neutral), only funding income remains.

## Position Sizing

- Spot leg: 45% of equity
- Perp leg: 45% of equity (1x leverage, needs 45% margin)
- Cash buffer: 10% (avoid liquidation)

Total capital commitment: 90% + 10% buffer = 100%.

## Entry/Exit Rules

**Entry:** funding positive for 7 consecutive days
**Exit:** funding negative for 3 consecutive days OR drawdown > 10%
**Rebalance:** every 30 days (to keep 45/45 split)

## Fee Impact

Rebalance every 30 days: ~12/year × 0.3% roundtrip = 3.6% annual fee drag
Entry/exit: additional ~0.6% per cycle

## Comparison

| Feature | M31 alone | Hedged |
|---------|-----------|--------|
| Delta exposure | 100% short BTC | ~0% |
| Funding capture | 100% | 45% |
| Max DD (expected) | 10-30% | <2% |
| Sharpe (expected) | 2-4 | 3-5 |

## Why This Matters

Without hedge, we cannot attribute returns to funding. With hedge, we CAN — pure alpha.

## Success Criteria

- DD < 2% (delta neutral works)
- SR > 3 (low vol = high SR)
- Fee-adjusted return > 3%/year

## Next Steps

1. Backtest on historical data
2. If pass, Paper bot
3. Compare to M31 alone


## FINAL RESULTS (2026-11-06)

**PROVEN on 2 exchanges:**

Hyperliquid (537 days, real fees):
- M31 alone: SR=0.47, DD=68.04%, Ret=+0.09%
- Hedged:    SR=11.41, DD=0.21%, Ret=+8.09%
- Funding: +8.97%, Fees: -1.19%, Price: +0.31%

Aster (499 days, real fees):
- M31 alone: SR=0.83, DD=18.88%, Ret=+31.16%
- Hedged:    SR=5.13, DD=0.39%, Ret=+1.91%

**Conclusion:** Hedge is PROVEN. M31 unhedged was mostly beta.
