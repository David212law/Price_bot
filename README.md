# Price_bot

An automated trading bot with regime-aware adaptive strategy selection.

## What It Does

- **Researcher**: Discovers winning strategies across 3 markets (Wallex TMN, Wallex USDT, Hyperliquid) every 3 days.
- **Wallex Bot**: Trades in Iranian Toman market (daily).
- **HL Bot**: Trades on Hyperliquid global market (daily).
- **M31 Bots**: 11 legacy bots running delta-neutral funding strategy.

## Architecture

- **4-Layer Pipeline**: Discovery → Execution → Legacy → Reporting
- **Adaptive Mode**: Exposure adjusts based on market regime (BULL/BEAR/CRASH)
- **4-Tier Approval**: Normal (30d stable) / Emergency Loss / Emergency Alpha / Human
- **Safety**: Holdout 20%, Slippage, Kill Switch, Survival Mode

## Tested Results

| Market | Strategy | B&H |
|--------|----------|-----|
| 2022 (Bear) | -5.7% | -65.3% |
| 2023 (Bull) | +103.4% | +154.2% |
| Wallex 2024-2026 | +97.5% | +97.6% |

**Compound return (2022+2023): +91.8%** (Adaptive Mode)

## Quick Start

See `PIPELINE_STATE.md` for detailed architecture and rules.

## ⚠️ DISCLAIMER

This software is for **educational and research purposes only**. 
It is NOT financial advice. Trading cryptocurrency carries significant risk 
of loss. Use at your own risk. The authors are not responsible for any 
financial losses incurred by using this software.

Always test with Paper trading before risking real money.

## License

MIT License — see LICENSE file.
