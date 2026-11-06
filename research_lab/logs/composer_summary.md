# Composer Report — 2026-11-06

**Total entries**: 4969  
**Thresholds**: n≥30, q≥4/4, SR>1.5

## HYPERLIQUID

- M31 weaknesses: `['underperform_in_high_vol']`
- M31 by regime: `{'TREND': 8.887, 'RANGE': 8.192, 'NEUTRAL': 5.804}`
- M31 vol: low=13.539, high=4.617

### TREND

- Examined: **1569** | Passed: **4**
- **Rejected by gate**:
  - `quartiles`: 991
  - `no_validation`: 222
  - `pooled_n`: 149
  - `regime_n`: 90
  - `blacklist`: 90
  - `sharpe_ann`: 19
  - `param_fragile`: 3
  - `fee_2x`: 1
- **Top passed**:
  - `KELTNER_REV/ETH`: SR=3.18, q=4/4, n_reg=285, n_pooled=422
  - `KELTNER_REV/BNB`: SR=2.58, q=4/4, n_reg=228, n_pooled=422
  - `KELTNER_REV/SOL`: SR=2.51, q=4/4, n_reg=285, n_pooled=422
  - `KELTNER_REV/BNB`: SR=1.75, q=4/4, n_reg=148, n_pooled=422

### RANGE

- Examined: **1557** | Passed: **4**
- **Rejected by gate**:
  - `quartiles`: 706
  - `regime_n`: 542
  - `pooled_n`: 120
  - `blacklist`: 90
  - `no_validation`: 76
  - `sharpe_ann`: 17
  - `param_fragile`: 1
  - `fee_2x`: 1
- **Top passed**:
  - `KELTNER_REV/ETH`: SR=3.18, q=4/4, n_reg=34, n_pooled=422
  - `KELTNER_REV/BNB`: SR=2.58, q=4/4, n_reg=54, n_pooled=422
  - `KELTNER_REV/SOL`: SR=2.51, q=4/4, n_reg=35, n_pooled=422
  - `KELTNER_REV/BNB`: SR=1.75, q=4/4, n_reg=24, n_pooled=422

### NEUTRAL

- Examined: **1564** | Passed: **4**
- **Rejected by gate**:
  - `quartiles`: 692
  - `regime_n`: 588
  - `pooled_n`: 120
  - `blacklist`: 90
  - `no_validation`: 52
  - `sharpe_ann`: 17
  - `param_fragile`: 1
- **Top passed**:
  - `KELTNER_REV/ETH`: SR=3.18, q=4/4, n_reg=49, n_pooled=422
  - `KELTNER_REV/BNB`: SR=2.58, q=4/4, n_reg=46, n_pooled=422
  - `KELTNER_REV/SOL`: SR=2.51, q=4/4, n_reg=51, n_pooled=422
  - `KELTNER_REV/BNB`: SR=1.75, q=4/4, n_reg=23, n_pooled=422

## ASTER

- M31 weaknesses: `['underperform_in_high_vol']`
- M31 by regime: `{'TREND': 9.063, 'RANGE': 8.626, 'NEUTRAL': 7.301}`
- M31 vol: low=21.665, high=8.434

### TREND

- Examined: **1769** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 1159
  - `no_validation`: 265
  - `pooled_n`: 152
  - `blacklist`: 90
  - `regime_n`: 70
  - `sharpe_ann`: 27
  - `param_fragile`: 1
- **Top passed**:
  - `KELTNER_REV/AVAXUSDT`: SR=4.56, q=4/4, n_reg=386, n_pooled=508
  - `KELTNER_REV/ETHUSDT`: SR=3.72, q=4/4, n_reg=334, n_pooled=508
  - `KELTNER_REV/SOLUSDT`: SR=3.19, q=4/4, n_reg=345, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=2.90, q=4/4, n_reg=286, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=2.43, q=4/4, n_reg=184, n_pooled=508

### RANGE

- Examined: **1756** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 892
  - `regime_n`: 515
  - `pooled_n`: 147
  - `blacklist`: 90
  - `no_validation`: 82
  - `sharpe_ann`: 25
- **Top passed**:
  - `KELTNER_REV/AVAXUSDT`: SR=4.56, q=4/4, n_reg=85, n_pooled=508
  - `KELTNER_REV/ETHUSDT`: SR=3.72, q=4/4, n_reg=50, n_pooled=508
  - `KELTNER_REV/SOLUSDT`: SR=3.19, q=4/4, n_reg=45, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=2.90, q=4/4, n_reg=83, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=2.43, q=4/4, n_reg=45, n_pooled=508

### NEUTRAL

- Examined: **1761** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 885
  - `regime_n`: 543
  - `pooled_n`: 146
  - `blacklist`: 90
  - `no_validation`: 68
  - `sharpe_ann`: 24
- **Top passed**:
  - `KELTNER_REV/AVAXUSDT`: SR=4.56, q=4/4, n_reg=92, n_pooled=508
  - `KELTNER_REV/ETHUSDT`: SR=3.72, q=4/4, n_reg=55, n_pooled=508
  - `KELTNER_REV/SOLUSDT`: SR=3.19, q=4/4, n_reg=66, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=2.90, q=4/4, n_reg=65, n_pooled=508
  - `KELTNER_REV/BNBUSDT`: SR=2.43, q=4/4, n_reg=39, n_pooled=508

## KUCOIN

- M31 weaknesses: `[]`
- M31 by regime: `{'TREND': 7.611, 'RANGE': 7.485, 'NEUTRAL': 7.52}`
- M31 vol: low=8.831, high=7.731

### TREND

- Examined: **1631** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 1239
  - `no_validation`: 226
  - `blacklist`: 90
  - `regime_n`: 32
  - `sharpe_ann`: 31
  - `pooled_n`: 7
  - `param_fragile`: 1
- **Top passed**:
  - `KELTNER_REV/BNBUSDTM`: SR=2.55, q=4/4, n_reg=355, n_pooled=649
  - `KELTNER_REV/SOLUSDTM`: SR=2.50, q=4/4, n_reg=400, n_pooled=649
  - `KELTNER_REV/ETHUSDTM`: SR=2.41, q=4/4, n_reg=424, n_pooled=649
  - `KELTNER_REV/BNBUSDTM`: SR=1.83, q=4/4, n_reg=222, n_pooled=649
  - `KELTNER_REV/XRPUSDTM`: SR=1.72, q=4/4, n_reg=320, n_pooled=649

### RANGE

- Examined: **1619** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 969
  - `regime_n`: 488
  - `blacklist`: 90
  - `no_validation`: 42
  - `sharpe_ann`: 22
  - `pooled_n`: 3
- **Top passed**:
  - `KELTNER_REV/BNBUSDTM`: SR=2.55, q=4/4, n_reg=65, n_pooled=649
  - `KELTNER_REV/SOLUSDTM`: SR=2.50, q=4/4, n_reg=45, n_pooled=649
  - `KELTNER_REV/ETHUSDTM`: SR=2.41, q=4/4, n_reg=49, n_pooled=649
  - `KELTNER_REV/BNBUSDTM`: SR=1.83, q=4/4, n_reg=31, n_pooled=649
  - `KELTNER_REV/XRPUSDTM`: SR=1.72, q=4/4, n_reg=33, n_pooled=649

### NEUTRAL

- Examined: **1625** | Passed: **5**
- **Rejected by gate**:
  - `quartiles`: 1009
  - `regime_n`: 443
  - `blacklist`: 90
  - `no_validation`: 48
  - `sharpe_ann`: 27
  - `pooled_n`: 3
- **Top passed**:
  - `KELTNER_REV/BNBUSDTM`: SR=2.55, q=4/4, n_reg=79, n_pooled=649
  - `KELTNER_REV/SOLUSDTM`: SR=2.50, q=4/4, n_reg=78, n_pooled=649
  - `KELTNER_REV/ETHUSDTM`: SR=2.41, q=4/4, n_reg=72, n_pooled=649
  - `KELTNER_REV/BNBUSDTM`: SR=1.83, q=4/4, n_reg=37, n_pooled=649
  - `KELTNER_REV/XRPUSDTM`: SR=1.72, q=4/4, n_reg=74, n_pooled=649