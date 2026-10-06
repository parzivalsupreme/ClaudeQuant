# claudeQuant

A multi-agent trading research pipeline for Claude Code. Agents propose trading hypotheses,
a skeptic picks the best, they get turned into exact rules and backtested, and then a
**Monte Carlo stress test** and a validator try to kill them. The best possible outcome is
"PAPER TRADE". It never places orders.

```
/research mean reversion on 1H

hypothesis-generator -> skeptic -> strategy-spec -> backtester -> monte-carlo -> validator -> SUMMARY.md
   (10 ideas)          (top 2)     (exact rules)   (IS / OOS)   (5 MC tests)   (verdict)
```

## Setup

```bash
pip install -r requirements.txt
python scripts/make_sample_data.py      # synthetic demo data -> data/sample_btc_1h.csv
python -m pytest -q tests
```

Then put real OHLCV data in `data/` (columns `timestamp, open, high, low, close, volume`) and edit the
market / constraints at the top of `CLAUDE.md`. **The sample data is synthetic: results on it mean nothing.**

## Run it

Interactive:
```
claude
> /research                          # full pipeline
> /research volatility breakout      # with a focus
> /stress-test research/2026-10-06-x/strategy_1.py
```

Headless (cron / Task Scheduler):
```bash
claude -p "/research" --allowedTools "Read,Write,Edit,Bash,Glob,Grep,WebSearch,Task"
```

Every run writes an audit trail to `research/<date>-<slug>/`: `hypotheses.md`, `selection.md`,
`spec_<n>.md`, `strategy_<n>.py`, `results_<n>.json`, `equity_<n>.png`, `mc_<n>/`,
`validation_<n>.json`, `verdict_<n>.md`, `SUMMARY.md`. Past verdicts are fed back to the
hypothesis generator so it stops re-proposing dead ideas.

## Monte Carlo stress test

```bash
python scripts/stress_test.py --data data/sample_btc_1h.csv \
    --strategy research/example/strategy_1.py:signal --sample out --out research/example/mc_1
```

| # | Test | What it answers |
|---|------|-----------------|
| 1 | **Trade-order shuffle** | Same trades, random order. How bad could the drawdown have been just from the sequence? |
| 2 | **Trade bootstrap** | Resample trades with replacement: confidence intervals for return / drawdown, probability of loss, risk of ruin, and return with the best 5% of trades removed (outlier dependence). |
| 3 | **Execution stress** | Re-run with 1-3x slippage, 10% of trades randomly missed, and random 1-bar late entries. |
| 4 | **Synthetic price paths** | Block-bootstrap the bars into new histories with the same volatility character and re-run the strategy. Is the result tied to one exact history? |
| 5 | **Permutation test** | Shuffle bars to destroy every real pattern and re-run. p-value = share of noise runs that matched the real Sharpe. |

Output: `montecarlo.md` (report + verdict), `montecarlo.json`, `montecarlo.png` (charts).
The rule-based verdict is `REJECT` (any hard failure), `NEEDS WORK` (warnings) or `PASS MONTE CARLO`.

The stress test aborts if the strategy's signals change when future bars are removed (lookahead).

## Layout

```
.claude/agents/      hypothesis-generator, skeptic, strategy-spec, backtester, monte-carlo, validator
.claude/commands/    /research, /stress-test
CLAUDE.md            market, costs and rules every agent follows
quant/               backtest engine, metrics, montecarlo, validation (walk-forward, sensitivity, lookahead)
scripts/             backtest.py, stress_test.py, validate.py, make_sample_data.py
research/example/    a worked example (SMA cross on synthetic data -> REJECT)
```

## Writing a strategy

```python
PARAMS = {"fast": 20, "slow": 100}                     # <= 4 params
GRID = {"fast": [10, 20, 40], "slow": [50, 100, 200]}  # used by walk-forward

def signal(df, fast=20, slow=100):
    # position in [-1, 1] per bar, from data up to this bar's close.
    # Don't shift it: the engine fills on the next bar's open.
    return (df.close.rolling(fast).mean() > df.close.rolling(slow).mean()).astype(float)
```

Costs default to 0.1% fee + 0.05% slippage per side.

## Disclaimer

Research tool, not financial advice. Most strategies fail after costs; a passing Monte Carlo test
is necessary, not sufficient. Paper trade before risking money.
