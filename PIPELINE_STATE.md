# PRICE_BOT — Pipeline State

**Last updated:** 2026-11-09

## Active Ecosystem (Post-Cleanup)

### Discovery Layer
- `scripts/researcher_predictive.py` — Monday & Thursday 03:00 UTC
  - 306 strategies × 3 markets (TMN, USDT, GLOBAL)
  - Output: `data/researcher_predictive_results.json`
  - Bale notification

### Execution Layer
- `scripts/wallex_paper_bot.py` — Daily 12:00 UTC (Wallex TMN)
- `scripts/hl_predictive_bot.py` — Daily 12:00 UTC (Hyperliquid)

### Legacy Layer (M31 Hedged - 11 bots)
- Aster (5): aster, combo, shadow_lv, shadow_rp, shadow_trend
- Hyperliquid (5): portfolio, shadow, shadow_mlp, shadow_mom, shadow_rp
- KuCoin (1): paper

### Data Fetch (on-demand)
- `scripts/fetch_wallex_fast.py` — Wallex TMN + USDT (parallel)
- `scripts/fetch_crypto_5y.py` — Yahoo Finance crypto
- `scripts/fetch_iran_data.py` — TGJU USD/IRR

## Rules (Locked)
- D-347: AI does not execute code
- D-460: Live Gate = 6 months Paper + Sharpe≥3 + DD≤10%
- D-548: TWO-EDGES-ACCEPT
- D-556: Archive before delete

## Archive
- `archive/2026-11-09/scripts/` — 28 obsolete scripts
- `archive/2026-11-09/workflows/` — 21 obsolete workflows
- `archive/2026-11-09/data/` — 19 obsolete data outputs

## Known Limitations
- Wallex data: only 2.2 years (Sep 2024 → Nov 2026)
- No bear market test for Wallex
- Slippage not modeled for low-liquidity altcoins
