# Composer Report


## HYPERLIQUID

- M31 baseline: n=538, SR=8.157

### TREND
- route=M31_ONLY, SR=8.887, n_days=275
- components: []
- weights: {'M31': 0.65, 'CASH': 0.35}

### RANGE
- route=A, SR=9.635, n_days=176
- components: ['M31', 'KELTNER_REV_ETH']
- weights: {'M31': 0.175, 'KELTNER_REV_ETH': 0.175, 'CASH': 0.65}

### NEUTRAL
- route=A, SR=6.834, n_days=131
- components: ['M31', 'KELTNER_REV_ETH']
- weights: {'M31': 0.175, 'KELTNER_REV_ETH': 0.175, 'CASH': 0.65}

## ASTER

- M31 baseline: n=731, SR=8.264

### TREND
- route=M31_ONLY, SR=9.063, n_days=378
- components: []
- weights: {'M31': 0.4, 'CASH': 0.6}

### RANGE
- route=A, SR=9.515, n_days=218
- components: ['M31', 'KELTNER_REV_ETHUSDT']
- weights: {'M31': 0.3, 'KELTNER_REV_ETHUSDT': 0.3, 'CASH': 0.4}

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
- route=A, SR=8.515, n_days=271
- components: ['M31', 'KELTNER_REV_ETHUSDTM']
- weights: {'M31': 0.35, 'KELTNER_REV_ETHUSDTM': 0.35, 'CASH': 0.30000000000000004}

### NEUTRAL
- route=M31_ONLY, SR=7.52, n_days=213
- components: []
- weights: {'M31': 0.3, 'CASH': 0.7}

### HYPERLIQUID/TREND complements:
- KELTNER_REV corr=-0.029 SR=5.379

### HYPERLIQUID/RANGE complements:
- KELTNER_REV corr=-0.184 SR=5.379

### HYPERLIQUID/NEUTRAL complements:
- KELTNER_REV corr=0.027 SR=5.379

### ASTER/TREND complements:
- KELTNER_REV corr=-0.032 SR=5.457
- KELTNER_REV corr=-0.032 SR=5.456

### ASTER/RANGE complements:
- KELTNER_REV corr=0.073 SR=5.457
- KELTNER_REV corr=0.073 SR=5.456

### ASTER/NEUTRAL complements:
- KELTNER_REV corr=-0.048 SR=5.457
- KELTNER_REV corr=-0.048 SR=5.456

### KUCOIN/TREND complements:
- KELTNER_REV corr=-0.035 SR=4.998

### KUCOIN/RANGE complements:
- KELTNER_REV corr=-0.095 SR=4.998

### KUCOIN/NEUTRAL complements:
- KELTNER_REV corr=0.061 SR=4.998