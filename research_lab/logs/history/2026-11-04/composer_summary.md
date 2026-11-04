# Composer Report — 2026-11-04

**Total entries**: 4700  
**Thresholds**: n≥30, q≥4/4, SR>1.5

## HYPERLIQUID

- M31 weaknesses: `['underperform_in_high_vol']`
- M31 by regime: `{'TREND': 8.887, 'RANGE': 8.192, 'NEUTRAL': 5.804}`
- M31 vol: low=13.539, high=4.617

### TREND

- Examined: **1449** | Passed: **6**
- **Rejected by gate**:
  - `quartiles`: 991
  - `no_validation`: 222
  - `regime_n`: 90
  - `blacklist`: 90
  - `pooled_n`: 29
  - `fee_2x`: 15
  - `param_fragile`: 5
  - `sharpe_ann`: 1
- **Top passed**:
  - `KELTNER_REV/ETH`: SR=5.39, q=4/4, n_reg=198, n_pooled=422
  - `KELTNER_REV/ETH`: SR=5.38, q=4/4, n_reg=285, n_pooled=422
  - `KELTNER_REV/BNB`: SR=5.01, q=4/4, n_reg=228, n_pooled=422
  - `KELTNER_REV/BNB`: SR=4.56, q=4/4, n_reg=148, n_pooled=422
  - `KELTNER_REV/SOL`: SR=3.98, q=4/4, n_reg=285, n_pooled=422
- **Pending**: `WEAK_PASS`
  - Weights: `M31=98.2%, KELTNER_REV_ETH=1.8%`
  - SR=8.004, n_days=331
  - Reasons: ['improvement=1.01<1.10']

### RANGE

- Examined: **1437** | Passed: **6**
- **Rejected by gate**:
  - `quartiles`: 706
  - `regime_n`: 542
  - `blacklist`: 90
  - `no_validation`: 76
  - `fee_2x`: 13
  - `param_fragile`: 3
  - `sharpe_ann`: 1
- **Top passed**:
  - `KELTNER_REV/ETH`: SR=5.39, q=4/4, n_reg=17, n_pooled=422
  - `KELTNER_REV/ETH`: SR=5.38, q=4/4, n_reg=34, n_pooled=422
  - `KELTNER_REV/BNB`: SR=5.01, q=4/4, n_reg=54, n_pooled=422
  - `KELTNER_REV/BNB`: SR=4.56, q=4/4, n_reg=24, n_pooled=422
  - `KELTNER_REV/SOL`: SR=3.98, q=4/4, n_reg=35, n_pooled=422
- **Pending**: `STRICT_PASS`
  - Weights: `M31=98.6%, KELTNER_REV_ETH=1.4%`
  - SR=9.635, n_days=176

### NEUTRAL

- Examined: **1444** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 692
  - `regime_n`: 588
  - `blacklist`: 90
  - `no_validation`: 52
  - `fee_2x`: 13
  - `param_fragile`: 3
  - `sharpe_ann`: 1
- **Top passed**:
  - `KELTNER_REV/ETH`: SR=5.39, q=4/4, n_reg=24, n_pooled=422
  - `KELTNER_REV/ETH`: SR=5.38, q=4/4, n_reg=49, n_pooled=422
  - `KELTNER_REV/BNB`: SR=5.01, q=4/4, n_reg=46, n_pooled=422
  - `KELTNER_REV/BNB`: SR=4.56, q=4/4, n_reg=23, n_pooled=422
  - `KELTNER_REV/SOL`: SR=3.98, q=4/4, n_reg=51, n_pooled=422
- **Pending**: `STRICT_PASS`
  - Weights: `M31=98.8%, KELTNER_REV_ETH=1.2%`
  - SR=6.834, n_days=131

## ASTER

- M31 weaknesses: `['underperform_in_high_vol']`
- M31 by regime: `{'TREND': 9.063, 'RANGE': 8.626, 'NEUTRAL': 7.301}`
- M31 vol: low=21.665, high=8.434

### TREND

- Examined: **1623** | Passed: **7**
- **Rejected by gate**:
  - `quartiles`: 1159
  - `no_validation`: 265
  - `blacklist`: 90
  - `regime_n`: 70
  - `fee_2x`: 20
  - `param_fragile`: 6
  - `pooled_n`: 6
- **Top passed**:
  - `KELTNER_REV/AVAXUSDT`: SR=5.46, q=4/4, n_reg=386, n_pooled=508
  - `KELTNER_REV/ETHUSDT`: SR=5.46, q=4/4, n_reg=334, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=5.03, q=4/4, n_reg=184, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=4.36, q=4/4, n_reg=286, n_pooled=508
  - `KELTNER_REV/SOLUSDT`: SR=3.58, q=4/4, n_reg=345, n_pooled=508
- **Pending**: `WEAK_PASS`
  - Weights: `M31=98.2%, KELTNER_REV_AVAXUSDT=1.8%`
  - SR=8.61, n_days=441
  - Reasons: ['improvement=1.04<1.10']

### RANGE

- Examined: **1610** | Passed: **7**
- **Rejected by gate**:
  - `quartiles`: 892
  - `regime_n`: 515
  - `blacklist`: 90
  - `no_validation`: 82
  - `fee_2x`: 18
  - `param_fragile`: 5
  - `pooled_n`: 1
- **Top passed**:
  - `KELTNER_REV/AVAXUSDT`: SR=5.46, q=4/4, n_reg=85, n_pooled=508
  - `KELTNER_REV/ETHUSDT`: SR=5.46, q=4/4, n_reg=50, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=5.03, q=4/4, n_reg=45, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=4.36, q=4/4, n_reg=83, n_pooled=508
  - `KELTNER_REV/SOLUSDT`: SR=3.58, q=4/4, n_reg=45, n_pooled=508
- **Pending**: `STRICT_PASS`
  - Weights: `M31=96.9%, KELTNER_REV_AVAXUSDT=3.1%`
  - SR=9.515, n_days=218

### NEUTRAL

- Examined: **1615** | Passed: **7**
- **Rejected by gate**:
  - `quartiles`: 885
  - `regime_n`: 543
  - `blacklist`: 90
  - `no_validation`: 68
  - `fee_2x`: 17
  - `param_fragile`: 5
- **Top passed**:
  - `KELTNER_REV/AVAXUSDT`: SR=5.46, q=4/4, n_reg=92, n_pooled=508
  - `KELTNER_REV/ETHUSDT`: SR=5.46, q=4/4, n_reg=55, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=5.03, q=4/4, n_reg=39, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=4.36, q=4/4, n_reg=65, n_pooled=508
  - `KELTNER_REV/SOLUSDT`: SR=3.58, q=4/4, n_reg=66, n_pooled=508

## KUCOIN

- M31 weaknesses: `[]`
- M31 by regime: `{'TREND': 7.611, 'RANGE': 7.485, 'NEUTRAL': 7.52}`
- M31 vol: low=8.831, high=7.731

### TREND

- Examined: **1628** | Passed: **13**
- **Rejected by gate**:
  - `quartiles`: 1239
  - `no_validation`: 226
  - `blacklist`: 90
  - `regime_n`: 32
  - `fee_2x`: 18
  - `param_fragile`: 5
  - `pooled_n`: 4
  - `sharpe_ann`: 1
- **Top passed**:
  - `MOM_TSI_30_SHORT/XRPUSDTM`: SR=5.25, q=4/4, n_reg=17, n_pooled=136
  - `LOW_VOL_CARRY/SOLUSDTM`: SR=5.12, q=4/4, n_reg=12, n_pooled=183
  - `KELTNER_REV/ETHUSDTM`: SR=5.00, q=4/4, n_reg=424, n_pooled=649
  - `KELTNER_REV/BNBUSDTM`: SR=4.12, q=4/4, n_reg=355, n_pooled=649
  - `DUAL_MOMENTUM/XBTUSDTM`: SR=3.83, q=4/4, n_reg=27, n_pooled=517

### RANGE

- Examined: **1616** | Passed: **8**
- **Rejected by gate**:
  - `quartiles`: 969
  - `regime_n`: 488
  - `blacklist`: 90
  - `no_validation`: 42
  - `fee_2x`: 15
  - `param_fragile`: 3
  - `sharpe_ann`: 1
- **Top passed**:
  - `LOW_VOL_CARRY/SOLUSDTM`: SR=5.12, q=4/4, n_reg=14, n_pooled=183
  - `KELTNER_REV/ETHUSDTM`: SR=5.00, q=4/4, n_reg=49, n_pooled=649
  - `KELTNER_REV/BNBUSDTM`: SR=4.12, q=4/4, n_reg=65, n_pooled=649
  - `DUAL_MOMENTUM/XBTUSDTM`: SR=3.83, q=4/4, n_reg=15, n_pooled=517
  - `KELTNER_REV/BNBUSDTM`: SR=3.77, q=4/4, n_reg=31, n_pooled=649
- **Pending**: `STRICT_PASS`
  - Weights: `M31=97.0%, KELTNER_REV_ETHUSDTM=3.0%`
  - SR=8.515, n_days=271

### NEUTRAL

- Examined: **1622** | Passed: **9**
- **Rejected by gate**:
  - `quartiles`: 1009
  - `regime_n`: 443
  - `blacklist`: 90
  - `no_validation`: 48
  - `fee_2x`: 18
  - `param_fragile`: 4
  - `sharpe_ann`: 1
- **Top passed**:
  - `KELTNER_REV/ETHUSDTM`: SR=5.00, q=4/4, n_reg=72, n_pooled=649
  - `KELTNER_REV/BNBUSDTM`: SR=4.12, q=4/4, n_reg=79, n_pooled=649
  - `DUAL_MOMENTUM/XBTUSDTM`: SR=3.83, q=4/4, n_reg=15, n_pooled=517
  - `KELTNER_REV/BNBUSDTM`: SR=3.77, q=4/4, n_reg=37, n_pooled=649
  - `VC_FI_25/SOLUSDTM`: SR=3.44, q=4/4, n_reg=10, n_pooled=113
- **Pending**: `WEAK_PASS`
  - Weights: `M31=97.2%, KELTNER_REV_ETHUSDTM=2.8%`
  - SR=7.83, n_days=213
  - Reasons: ['improvement=1.04<1.10']