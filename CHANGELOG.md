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

