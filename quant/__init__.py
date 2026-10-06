"""claudeQuant: a small, lookahead-safe research toolkit used by the agent pipeline.

Strategy contract
-----------------
A strategy is a function ``signal(df, **params) -> pd.Series`` that returns the
desired position (-1..1, fraction of equity) for every bar, computed only from
data up to and including that bar's close. The engine fills it on the NEXT
bar's open, so strategies never need to shift anything themselves.
"""

from .backtest import BacktestResult, run_backtest
from .data import load_ohlcv, make_synthetic
from .metrics import compute_metrics

__all__ = ["BacktestResult", "run_backtest", "load_ohlcv", "make_synthetic", "compute_metrics"]
