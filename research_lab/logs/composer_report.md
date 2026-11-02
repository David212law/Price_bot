# Composer Report


## HYPERLIQUID

- M31 baseline: n=538, SR=8.157

### TREND
- route=M31_ONLY, SR=8.887, n_days=275
- components: []
- weights: {'M31': 0.65, 'CASH': 0.35}

### RANGE
- route=M31_ONLY, SR=8.192, n_days=142
- components: []
- weights: {'M31': 0.65, 'CASH': 0.35}

### NEUTRAL
- route=M31_ONLY, SR=5.804, n_days=111
- components: []
- weights: {'M31': 0.65, 'CASH': 0.35}

## ASTER

- M31 baseline: n=731, SR=8.264

### TREND
- route=M31_ONLY, SR=9.063, n_days=378
- components: []
- weights: {'M31': 0.4, 'CASH': 0.6}

### RANGE
- route=M31_ONLY, SR=8.626, n_days=203
- components: []
- weights: {'M31': 0.4, 'CASH': 0.6}

### NEUTRAL
- route=M31_ONLY, SR=7.301, n_days=144
- components: []
- weights: {'M31': 0.4, 'CASH': 0.6}

## KUCOIN

- M31 baseline: n=1096, SR=7.763

### TREND
- route=M31_ONLY, SR=7.611, n_days=602
- components: []
- weights: {'M31': 0.3, 'CASH': 0.7}

### RANGE
- route=M31_ONLY, SR=7.485, n_days=271
- components: []
- weights: {'M31': 0.3, 'CASH': 0.7}

### NEUTRAL
- route=M31_ONLY, SR=7.52, n_days=213
- components: []
- weights: {'M31': 0.3, 'CASH': 0.7}

### KUCOIN/TREND complements:
- LOW_VOL_CARRY corr=-0.217 SR=5.123
- KELTNER_REV corr=-0.035 SR=4.998
- DUAL_MOMENTUM corr=-0.003 SR=3.829
- KELTNER_REV corr=-0.035 SR=3.775
- ROC corr=0.016 SR=3.632

### KUCOIN/RANGE complements:
- LOW_VOL_CARRY corr=0.065 SR=5.123
- KELTNER_REV corr=-0.095 SR=4.998
- DUAL_MOMENTUM corr=0.177 SR=3.829
- KELTNER_REV corr=-0.095 SR=3.775
- DUAL_MOMENTUM corr=0.177 SR=2.834

### KUCOIN/NEUTRAL complements:
- KELTNER_REV corr=0.061 SR=4.998
- DUAL_MOMENTUM corr=0.056 SR=3.829
- KELTNER_REV corr=0.061 SR=3.775
- DUAL_MOMENTUM corr=0.056 SR=2.834