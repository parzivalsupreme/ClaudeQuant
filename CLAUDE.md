# Trading research project

Purely agentic pipeline: agents generate trading hypotheses, turn them into strategies, write and run
their own backtests, then stress-test them with Monte Carlo and try hard to kill them.
Run it with `/research [focus]`. There is no shared code library: every agent writes the code it needs
into the run folder, following the conventions below exactly so results are comparable across runs.

## Market & constraints (edit these to yours)
- Market: BTC/USDT, timeframe 1H
- Data: `data/*.csv` with columns timestamp, open, high, low, close, volume (real exchange data)
- Capital: 10,000 USDT; max risk per trade 1%
- Fees 0.1% per side, slippage 0.05% per side
- Python with pandas, numpy, matplotlib (install with pip if missing)

## Hard rules for every agent
- Never use future data. No negative `shift`, no `center=True`, no normalising with full-series stats,
  no deciding on bar t and filling at bar t's own price.
- Max 4 tunable parameters per strategy.
- 70/30 in-sample / out-of-sample split by time. Out-of-sample decides everything.
  Never tune parameters on out-of-sample data.
- Every run writes to `research/<YYYY-MM-DD>-<slug>/`. Read `research/*/verdict.md` from earlier runs
  so failed ideas are not re-proposed.
- Agents that build things never grade their own work; the skeptic, monte-carlo and validator agents do.
- The pipeline ends at PAPER TRADE at most. Never connect to an exchange or place orders.

## Backtest conventions (every agent-written backtest must follow these)
- **Strategy contract** - `research/<run>/strategy_<n>.py` defines:
  ```python
  PARAMS = {"lookback": 20, ...}          # chosen defaults, <= 4 keys
  GRID = {"lookback": [10, 20, 40], ...}  # 3 values each, for walk-forward
  def signal(df: pd.DataFrame, **params) -> pd.Series:  # target position in [-1, 1] per bar
  ```
  The value at bar t uses only bars <= t (through t's close).
- **Timing** - position decided at bar t's close is filled at bar t+1's open:
  `held = target.shift(1)`; per-bar gross return = `held[t] * (open[t+1] / open[t] - 1)`.
- **Costs** - `(fee + slippage) * |held[t] - held[t-1]|` deducted every bar, plus closing any position
  on the last bar.
- **Trade** - a maximal run of bars holding the same non-zero position.
  Trade return = compounded gross over the run, times `(1 - |size| * (fee + slippage))^2`, minus 1.
- **Metrics** - total return, CAGR, max drawdown (negative fraction), annualised Sharpe from per-bar
  returns (bars per year from the median bar spacing), win rate, profit factor, trade count, exposure.
- **Lookahead self-check** - for 20 random cut points k, `signal(df[:k+1]).iloc[-1]` must equal
  `signal(df).iloc[k]`. Any mismatch means the strategy is invalid until fixed.

## Run folder layout
```
hypotheses.md  selection.md  spec_<n>.md  strategy_<n>.py  backtest_<n>.py  results_<n>.json  equity_<n>.png
mc_<n>/montecarlo.py  mc_<n>/montecarlo.json  mc_<n>/montecarlo.md  mc_<n>/montecarlo.png
validate_<n>.py  validation_<n>.json  verdict_<n>.md  SUMMARY.md  verdict.md
```
