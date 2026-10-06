# Trading research project

Multi-agent pipeline that generates trading hypotheses, turns them into strategies,
backtests them and tries hard to kill them. Run it with `/research [focus]`.

## Market & constraints (edit these to yours)
- Market: BTC/USDT, timeframe 1H
- Data: `data/*.csv` with columns timestamp, open, high, low, close, volume
  (`python scripts/make_sample_data.py` writes a SYNTHETIC demo file - use real exchange data for real results)
- Capital: 10,000 USDT; max risk per trade 1%
- Fees 0.1% per side, slippage 0.05% per side

## Hard rules for every agent
- Never use future data. Strategies output a position from bars up to and including the current
  close; the engine (`quant/backtest.py`) fills it on the NEXT bar's open. Do not shift signals yourself.
- Max 4 tunable parameters per strategy.
- 70/30 in-sample / out-of-sample split (`quant.backtest.split_in_out`). Out-of-sample decides everything.
  Never tune parameters on out-of-sample data.
- Use the `quant` library; do not write a new backtest engine.
- Every run writes to `research/<YYYY-MM-DD>-<slug>/`. Read `research/*/verdict.md` from earlier runs
  so failed ideas are not re-proposed.
- The pipeline ends at PAPER TRADE at most. Never place live orders.

## Strategy contract
`research/<run>/strategy_<n>.py` must define:
```python
PARAMS = {"lookback": 20, ...}          # chosen defaults, <= 4 keys
GRID = {"lookback": [10, 20, 40], ...}  # for walk-forward
def signal(df: pd.DataFrame, **params) -> pd.Series:  # position in [-1, 1] per bar
```

## Tools
- `python -m pytest -q tests` - library tests
- `python scripts/backtest.py --data ... --strategy research/<run>/strategy_<n>.py:signal --out research/<run>`
  - in-sample / out-of-sample metrics, lookahead check, equity chart
- `python scripts/stress_test.py --data ... --strategy ... --params '<json>' --out research/<run>/mc_<n>`
  - Monte Carlo: trade shuffle, trade bootstrap, execution stress, synthetic price paths, permutation test
- `python scripts/validate.py --data ... --strategy ... --out research/<run>`
  - parameter sensitivity (+/-20%), anchored walk-forward and bull/bear/sideways regime breakdown
