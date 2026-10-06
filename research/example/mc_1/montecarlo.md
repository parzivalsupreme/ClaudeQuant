# Monte Carlo stress test: research/example/strategy_1.py:signal {'fast': 20, 'slow': 100}

Data: data/sample_btc_1h.csv [all-sample, 8000 bars, 2020-01-01 00:00:00+00:00 -> 2020-11-29 07:00:00+00:00]

## Verdict: **REJECT**

- removing best 5% of trades turns it negative (-47.9%) - outlier-driven
- risk of ruin 23.9% > 5%
- median return under execution stress is -4.6%
- loses money on 86% of synthetic paths
- only 47 trades (< 100)
- permutation p-value 0.075: weak evidence
- bootstrap 5th-pct return -66.2% < 0
- 5% of trade orderings see drawdown worse than -58.5%

## Baseline

| metric | value |
|---|---|
| total_return | -0.0208 |
| cagr | -0.0228 |
| max_drawdown | -0.4462 |
| sharpe | 0.2829 |
| win_rate | 0.2766 |
| profit_factor | 1.1322 |
| n_trades | 47 |
| avg_trade | 0.0040 |
| exposure | 0.4574 |

## 1. Trade-order shuffle (sequence risk)

| metric | p5 | p25 | median | p75 | p95 |
|---|---|---|---|---|---|
| max_drawdown | -58.5% | -50.3% | -44.4% | -38.9% | -32.3% |

Original max DD -38.8%; 75% of orderings were worse. Risk of ruin: 4.7%.

## 2. Trade bootstrap (confidence intervals)

| metric | p5 | p25 | median | p75 | p95 |
|---|---|---|---|---|---|
| total_return | -66.2% | -37.1% | -6.1% | 50.1% | 180.5% |
| max_drawdown | -70.5% | -56.7% | -45.9% | -36.7% | -25.8% |
| mean_trade | -2.0% | -0.6% | 0.3% | 1.4% | 2.9% |

P(loss) 53.4%; risk of ruin 23.9%; return without best 5% of trades: -47.9%.

## 3. Execution stress (1-3x slippage, 10% missed trades, late entries)

| metric | p5 | p25 | median | p75 | p95 |
|---|---|---|---|---|---|
| total_return | -37.8% | -16.9% | -4.6% | 3.9% | 19.5% |
| max_drawdown | -48.3% | -45.4% | -44.6% | -42.3% | -37.3% |
| sharpe | -0.61 | -0.03 | 0.21 | 0.38 | 0.62 |

P(loss) 65.5%.

## 4. Synthetic price paths (block bootstrap)

| metric | p5 | p25 | median | p75 | p95 |
|---|---|---|---|---|---|
| total_return | -78.0% | -63.6% | -45.9% | -18.3% | 43.7% |
| max_drawdown | -84.0% | -72.4% | -64.4% | -53.4% | -40.8% |
| sharpe | -2.34 | -1.43 | -0.75 | -0.01 | 0.94 |
| n_trades | 45.00 | 51.00 | 54.50 | 57.00 | 63.00 |

P(loss) 85.5%.

## 5. Permutation test (is it just noise?)

Real Sharpe 0.28 vs shuffled-data median -0.89 (p95 0.48). **p-value = 0.075** (fraction of noise runs that did at least as well).
