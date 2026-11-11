# PRICE_BOT — Pipeline State (Synced)
**Last updated:** 2026-11-09

## Active Ecosystem
### 1. Discovery (Researcher)
- `researcher_predictive.py` (Mon/Thu 03:00 UTC)
  - Tests 306 strategies × 3 markets.

### 2. Execution (Predictive)
- `wallex_paper_bot.py` (Daily 12:00 UTC) - Iran TMN
- `hl_predictive_bot.py` (Daily 12:00 UTC) - Global HL

### 3. Legacy (M31 Hedged)
- All 11 bots run **Daily at 14:00 UTC** (reduced from every 4 hours).

### 4. Reporting
- Unified Dashboard at `reports/daily_report.py` (Runs daily at 20:00 UTC).

## Rules
- D-347: AI does not execute.
- D-460: Live Gate freeze.
- D-544: NO-DELETE-FREEZE (bots are paused, not deleted).
