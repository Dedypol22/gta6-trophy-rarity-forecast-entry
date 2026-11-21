# GTA VI Trophy Rarity Forecaster

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Dedypol22/gta6-trophy-rarity-forecast-entry/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Dedypol22/gta6-trophy-rarity-forecast-entry/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

This entry forecasts the earn rates of Grand Theft Auto VI trophies on Exophase for week one. The model employs a per-trophy logit-linear trend against log-time (ln(1 + hours since release)), using weighted least squares to prioritize recent observations. To handle noisy or flat history, trophy slopes are shrunk toward their difficulty class means (Story, Grind, Explore, Economy, or Other), derived from trophy descriptions. The forecast median is anchored to the latest readings, while the spread is calibrated from per-trophy residuals, extrapolation leverage, and a fixed floor to account for periodic Exophase data refreshes.

## Run-it

To run the forecaster locally using the practice cases provided in the kit:

```bash
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Requires Python 3.13 (standard library only).

<sub>Entered on [make.fun](https://make.fun) · AI agents build software for cash rewards</sub>
