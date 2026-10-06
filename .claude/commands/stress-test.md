---
description: Monte Carlo stress test an existing strategy file
argument-hint: <path/to/strategy_<n>.py> [data.csv]
---
Stress-test this strategy: $ARGUMENTS

If no data file is given, use the first CSV in `data/`. Work in the strategy file's folder.
If there is no matching `backtest_<n>.py` / `results_<n>.json` next to it, use the **backtester** agent
first (skipping the spec step: the strategy file is the spec). Then use the **monte-carlo** agent and
show me its `montecarlo.md` verdict.
