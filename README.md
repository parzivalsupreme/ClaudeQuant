# claudeQuant

A purely agentic trading research pipeline for Claude Code. There is no shared code library:
agents propose trading hypotheses, a skeptic picks the best, they get turned into exact rules,
and the agents **write and run their own backtests, Monte Carlo stress tests and walk-forward
tests**. The best possible outcome is "PAPER TRADE". It never places orders.

```
/research mean reversion on 1H

hypothesis-generator -> skeptic -> strategy-spec -> backtester -> monte-carlo -> validator -> SUMMARY.md
   (10 ideas)          (top 2)     (exact rules)   (writes +     (writes + runs  (code review,
                                                    runs backtest) 5 MC tests)     walk-forward, verdict)
```

Consistency comes from `CLAUDE.md`, not from code: it pins down fill timing, costs, what counts as a
trade, how metrics are computed and a lookahead self-check, so every agent-written backtest follows
the same rules and runs stay comparable.

## Setup

1. `pip install -r requirements.txt` (the agents' generated code uses pandas, numpy, matplotlib).
2. Put OHLCV data in `data/` (columns `timestamp, open, high, low, close, volume`).
   `data/sample_btc_1h.csv` is **synthetic** - results on it mean nothing.
3. Edit the market / constraints at the top of `CLAUDE.md`.

## Run it

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

Every run leaves an audit trail in `research/<date>-<slug>/` - the ideas, the critique, the specs,
all generated code, results, charts and verdicts. Past verdicts are fed back to the hypothesis
generator so it stops re-proposing dead ideas.

## Agents

| Agent | Writes code? | Job |
|---|---|---|
| hypothesis-generator | no | 10 hypotheses with economic rationale and exact signals |
| skeptic | no | scores them, picks top 2, names the likely false discovery |
| strategy-spec | no | unambiguous rules, <= 4 parameters |
| backtester | yes | `strategy_<n>.py` + `backtest_<n>.py`, in-sample / out-of-sample results |
| monte-carlo | yes | `mc_<n>/montecarlo.py`: the five stress tests below + verdict |
| validator | yes | code review, `validate_<n>.py` (sensitivity, walk-forward, regimes), final verdict |

## Monte Carlo stress test

| # | Test | What it answers |
|---|------|-----------------|
| 1 | Trade-order shuffle | Same trades, random order: how bad could the drawdown have been from sequencing alone? |
| 2 | Trade bootstrap | Confidence intervals, P(loss), risk of ruin, return without the best 5% of trades. |
| 3 | Execution stress | 1-3x slippage, 10% missed trades, late entries. Does the edge survive real execution? |
| 4 | Synthetic price paths | Block-bootstrapped histories with the same volatility character. Tied to one history? |
| 5 | Permutation test | Shuffled bars destroy all patterns. p-value that the edge is noise. |

Verdict: `REJECT` (any hard failure), `NEEDS WORK` (warnings) or `PASS MONTE CARLO`.

## Trade-offs of going fully agentic

- Each run regenerates its backtest code, so it costs more tokens and time than calling a fixed script.
- Agent-written code can contain bugs. Mitigations built in: the backtester tests its engine on a
  hand-computed example, the monte-carlo agent sanity-checks its simulations, and the validator
  reviews all code and auto-rejects on any bug.

## Disclaimer

Research tool, not financial advice. Most strategies fail after costs; passing Monte Carlo is
necessary, not sufficient. Paper trade before risking money.
