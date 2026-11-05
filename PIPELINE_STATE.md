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

## Recent Decisions

- **D-537** (today): pipeline_contract + health_check + this file
- **D-536** (today): fixed 3 gaps (MLP blacklist, dedup SR, schema)
- **D-535** (today): Aster Shadow TREND heartbeat
- **D-530**: 16 validation tests — MLP FAIL
- **D-529**: researcher_v2 orchestrator
- **D-528**: multi_layer_portfolio (16-test validation)
- **D-522**: M31_MOMENTUM discovered (later blacklisted)