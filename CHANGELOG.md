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
