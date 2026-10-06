---
description: Monte Carlo stress test an existing strategy file
argument-hint: <path/to/strategy.py[:func]> [data.csv]
---
Stress-test this strategy: $ARGUMENTS

If no function name is given use `signal`; if no data file is given use the first CSV in `data/`.
Output folder: next to the strategy file, `mc_<strategy file stem>/`.
Use the **monte-carlo** agent, then show me its `interpretation.md` and the verdict.
