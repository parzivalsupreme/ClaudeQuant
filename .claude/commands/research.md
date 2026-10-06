---
description: Run the full trading research pipeline (hypotheses -> critique -> spec -> backtest -> Monte Carlo -> verdict)
argument-hint: [optional focus, e.g. "mean reversion on 1H"]
---
Run the full trading research pipeline. Focus (optional): $ARGUMENTS

Data file: the first CSV in `data/` unless the focus names one. Tell every agent the run folder and data path.

1. Create `research/<today YYYY-MM-DD>-<short-slug>/`.
2. Use the **hypothesis-generator** agent to write `hypotheses.md`.
3. Use the **skeptic** agent to write `selection.md`; read the `SELECTED:` line to get the two picks.
4. For each pick `n` (run both picks in parallel): use the **strategy-spec** agent to write `spec_<n>.md`,
   then the **backtester** agent to write `strategy_<n>.py` and `results_<n>.json`.
5. For each pick, use the **monte-carlo** agent to stress-test it (writes `mc_<n>/`).
6. For each pick, use the **validator** agent to write `verdict_<n>.md`.
7. Write `SUMMARY.md` in the run folder: one row per strategy with in-sample and out-of-sample Sharpe,
   max drawdown, trade count, Monte Carlo verdict, permutation p-value, walk-forward Sharpe and final
   VERDICT. Copy the verdicts into `verdict.md` so future runs can learn from them. Show me the summary.

Never place orders or connect to an exchange. The best possible outcome of this pipeline is PAPER TRADE.
