# Pipeline State

**Last updated:** 2026-11-05 19:57 UTC

## ⚠️ READ THIS FIRST

Run `python3 -m research_lab.health_check` before touching any code.

## Contract

- **Source:** `research_lab/pipeline_contract.py`
- **Blacklist:** M31_THRESHOLD, M31_SMA, M31_MOMENTUM, M31_EMA, M31_QUANTILE
- **M31 Caps:** hyperliquid=0.65, aster=0.40, kucoin=0.30

## Stages

1. Composer → composer_report.md
2. Thesis Detection → thesis_evidence.json
3. Thesis Dedup → thesis_deduped.json
4. Multi-Layer → multi_layer_portfolio.json
5. Improve → improvements.json

## Known Real Edges

- ✅ M31 (funding carry) — 3 exchanges
- ✅ Keltner (mean reversion) — 3 exchanges
- ❌ All M31 variants — corr>0.98, blacklisted, no holdout improvement

## Open Items

- (D-528) MLP FAIL — needs diversification
- (D-522) M31_MOMENTUM — confirmed redundant
- (D-379) Live Gate — 2027-05-02
- (D-511) Live Analyzer — use 90d window

## Rules

1. Read before edit
2. Backup before patch
3. `python3 -m research_lab.health_check` after
4. One GAP per commit


## Known Limitations (D-538, manually verified)

### Confirmed vs Candidate Edges
- **M31 (funding carry)** — economic mechanism. Backtest SR~8, expected
  Live SR=2-4 (haircut 50-75%). Real money flows.
- **Keltner (mean reversion)** — statistical pattern only, NO economic
  narrative. cross-exchange consistency 0.81-0.93 does NOT prove
  independence (same OHLCV data across exchanges). Treat as candidate.

### Statistical Caveats
- 2026-12-02 review is pre-statistical: hold=30d yields n<=1 closed trade.
  Metric should be "execution health" not "performance".
- MLP +3.4% improvement has NO CI computed yet. Helper
  `_bootstrap_improvement_ci` now exists but not wired into verdict.
- DSR=0.50 at N=8766 means "survived 8766-candidate selection bias",
  NOT "profitable in live".

### Governance Gaps
- D-460 weight freeze has no emergency override.
- improve_strategy tests vs own baseline, NOT vs M31 (warning now printed).

### Execution Risks (not modeled)
- No latency, no partial fill, no exchange-down, no stop-loss.

### Architecture Notes
- 4 of 12 Paper bots are shadow variants of M31+Keltner (not diversification).
- Aster Shadow TREND: skip/skip in current regimes.
- Bots 10, 12: track artifact strategies for comparison only.

## Recent Decisions

- **D-537** (today): pipeline_contract + health_check + this file
- **D-536** (today): fixed 3 gaps (MLP blacklist, dedup SR, schema)
- **D-535** (today): Aster Shadow TREND heartbeat
- **D-530**: 16 validation tests — MLP FAIL
- **D-529**: researcher_v2 orchestrator
- **D-528**: multi_layer_portfolio (16-test validation)
- **D-522**: M31_MOMENTUM discovered (later blacklisted)
## D-551 (2026-11-06): Hybrid_v3_Wallex
- Status: PROMISING (Paper test)
- Scope: USDTTMN + BTCTMN
- Bot: exchanges/wallex/v3_hybrid_bot.py
- Workflow: wallex_v3_paper.yml (every 4h)

## D-552 (PROVEN): Delta-Neutral Hedge M31
- HL: SR 0.47→11.41, DD 68%→0.21% (unhedged→hedged)
- Aster: SR 0.83→5.13, DD 19%→0.39%
- Delta-neutral confirmed (price contrib ~0.3%)
- ACTION: audit 12 paper bots — hedged or unhedged?

## وضعیت بحرانی (2026-11-06)

**همه ربات‌های Paper متوقف شدند** — کشف شد equity کاملاً FAKE است.

### یافته‌های audit:
- همه ۱۰ ربات Paper UNHEDGED هستند
- خط ۱۱۵ کد فقط funding را محاسبه می‌کند (بدون price P&L)
- DD واقعی در بحران: ۶۸٪ (بر اساس D-552)
- Paper equity نشان می‌دهد DD=۰.۱٪ = FAKE

### اقدامات:
- همه ورک‌فلوهای Paper متوقف (.yml.paused)
- فایل‌های economic v1/v2/v3 به archive/2026-11-06/ آرشیو شد
- نقشه راه migration: MIGRATION_PLAN.md

### تا تکمیل migration:
- هیچ تست Paper
- هیچ تصمیم Live Gate
- همه SR/DD Paper = FAKE


## وضعیت آرشیو (2026-11-06 15:28 UTC)

### آرشیو زائد (archive/2026-11-06/obsolete/):
- regime_detector_v2.py (جایگزین: researcher_v3/regime_v3.py)
- hybrid_manager.py (جایگزین: researcher_v3/combo_builder_v3.py)
- hedge_backtest.py (v1 — نسخه باگ‌دار)
- economic_generator.py + runner.py + v2.py + researcher_v3.py
- economic_library.json
- data/external/ (OI/LS/onchain)
- research/economic/ (v1/v2/v3)

### آرشیو مهم (archive/2026-11-06/important/):
- مستندات: PIPELINE_STATE, DECISIONS, FINAL_REPORT, MIGRATION_PLAN
- Pipeline stages: composer, thesis_detection, thesis_dedup, MLP, improve
- زیرساخت: pipeline_contract, health_check
- Hedge (D-552): hedge_design, hedge_backtest_v2
- Registry: registry.json, econ_registry.json
- researcher_v3/ (کامل)
- baseline_data/ (M31 + Keltner × ۳ صرافی)

### وضعیت fix ربات‌ها:
- 11 allocator از 11 هنوز fix نشده
- Migration: ۲-۳ هفته (MIGRATION_PLAN.md)
- تا fix: Paper متوقف، هیچ تست Paper
