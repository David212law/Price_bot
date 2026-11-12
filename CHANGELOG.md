# PRICE_BOT — Changelog
All significant changes to strategies, thresholds, and architecture.

## 2026-11-09 — v11.0 → v11.1 (Human-in-the-loop restored)
- RESTORED: Human-in-the-loop for strategies with Sharpe < 1.0
- CHANGED: Auto-approve condition from 3 days to 30 days stability
- ADDED: Changelog for all auto-approvals
- REASON: Previous version removed Human entirely, which is unsafe.


## 2026-11-09 — v11.2 (Stability window adjusted)
- CHANGED: Auto-approve stability window from 30 days to 7 days
- REASON: 30 days made system too slow to adapt. 7 days = 1 week, balances safety and freshness.


## 2026-11-09 — v15.0: Emergency approval for urgent situations
- ADDED: EMERGENCY-LOSS: If Kill Switch active + defensive strategy Sharpe > 1.5 → immediate approval
- ADDED: EMERGENCY-ALPHA: If strategy Sharpe > 2.0 (very strong) → immediate approval
- REASON: Some situations require immediate action (loss prevention, alpha capture)

## 2026-11-09 — v16.0: Adaptive Mode deployed
- ADDED: Adaptive exposure in Wallex and HL bots
- RULES:
  - BULL_STRONG: 100% BTC (Aggressive)
  - BULL: 80% BTC
  - FLAT: 30-80% BTC (based on 30d momentum)
  - BEAR: 30% BTC
  - CRASH: 0% BTC (Defensive)
- REASON: Adaptive mode gave +103.4% in 2023 and -5.7% in 2022 (best compound +91.8%)

## 2026-11-09 — v17.1: Researcher frequency = every 3 days
- CHANGED: Researcher runs every 3 days (was daily or monthly)
- REASON: Balance between freshness (every 3 days) and noise reduction (10 runs/month)
- Auto-approve still requires: 7d stable + 30d in top3 + Sharpe > 1.0
- Emergency still triggers immediately for loss/alpha


## 2026-11-09 — v18.1: High-frequency for predictive bots
- CHANGED: Wallex Bot and HL Bot run every 4 hours (was daily)
- UNCHANGED: Researcher every 3 days, M31 bots daily
- REASON: Adaptive Mode needs frequent updates. Public repo, but keeping resource usage reasonable.


## 2026-11-09 — v12.0 (RETROACTIVE: Human-in-the-loop دو سطحی)
- RESTORED: Human-in-the-loop in two-tier form
- RULE: Sharpe > 1.0 in Holdout → Auto-approve (after 7 days stable)
- RULE: Sharpe < 1.0 in Holdout → Human approval required
- REASON: Balance between automation and safety.
  NOTE: Retroactive entry — added 2026-11-11 during audit v19.0.


## 2026-11-09 — v13.0 (RETROACTIVE: کد = گزارش)
- FIXED: auto_approve_v3.py now actually checks Sharpe > 1.0 (was only checking stability)
- FIXED: Contradiction between report (claimed Sharpe check) and code (did not check)
- REASON: Code and report must match. Audit revealed gap.
  NOTE: Retroactive entry — added 2026-11-11 during audit v19.0.


## 2026-11-11 — v19.1: Audit fixes (Kill Switch JSON + Survival 2D + CI)
- FIXED: Kill Switch now writes to data/kill_switch_active.json (Wallex + HL)
  - Was: only `return` on equity < 90%, no JSON write, no cross-bot notification
  - Now: writes {active, last_triggered, reason, bot} and returns
- FIXED: Researcher JSON guard in Wallex
  - Was: fallback to bh_BTC if researcher_predictive_results.json missing
  - Now: exit with error, no fallback trading
- ADDED: Survival Mode 2D in Wallex
  - Detects Iran currency crisis (USD/IRR 30d change > 20%)
  - In BEAR/CRASH + iran_crisis → exposure 70% BTC (was 30% / 0%)
  - REASON: BTC outperforms Tether in Iran-specific currency crises
- FIXED: state["initialized"] flag (Wallex + HL)
  - Was: `or not state["holdings"]` triggered rebalance every empty-state run
  - Now: explicit `initialized` flag; only rebalance on regime/asset change
- ADDED: CI/CD workflow (.github/workflows/ci.yml)
  - Syntax check + health check on every push/PR
- RESTORED: iran_data_fetch.yml from archive (weekly TGJU update)
- AUDIT: Full code audit vs reports (v19.0) revealed 5 gaps, all now fixed.

## 2026-11-12 — v29.0: Final Paper Ready
- ARCHIVED: build_wallex_strategies.py (moved to build_strategies in Researcher)
- ADDED: build_highfreq.py + data/high_freq_strategies.json (265 strategies for reference)
- CHANGED: TMN max 5 strategies, USDT max 20, GLOBAL max 10 (commission-aware)
- FIXED: Kill Switch auto-reset on fresh state (v28.8)
- NOTE: GLOBAL 3.67 (v23.5) was overfitting; 2.98 (v29.0) is realistic.
