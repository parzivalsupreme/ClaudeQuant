"""Vectorised, lookahead-safe backtest engine.

Timing: the position a strategy outputs at bar t (using bar t's close) is
filled at bar t+1's open and earns the open-to-open return from t+1 to t+2.
Fees and slippage are charged per side on every change in position.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .metrics import compute_metrics


@dataclass
class BacktestResult:
    returns: pd.Series  # net per-bar strategy returns
    equity: pd.Series  # equity curve, starts at initial_capital
    position: pd.Series  # position actually held during each bar
    trades: pd.DataFrame  # one row per trade
    metrics: dict = field(default_factory=dict)

    @property
    def trade_returns(self) -> np.ndarray:
        return self.trades["return"].to_numpy() if len(self.trades) else np.array([])


def run_backtest(
    df: pd.DataFrame,
    target: pd.Series,
    fee: float = 0.001,
    slippage: float = 0.0005,
    initial_capital: float = 1.0,
) -> BacktestResult:
    """Simulate ``target`` positions (decided at each bar's close) on ``df``."""
    target = target.reindex(df.index).astype(float).fillna(0.0).clip(-1, 1)
    held = target.shift(1).fillna(0.0)  # filled at this bar's open
    open_ = df["open"].to_numpy()
    oo = np.zeros(len(df))
    oo[:-1] = open_[1:] / open_[:-1] - 1.0  # open(t) -> open(t+1); last bar earns nothing
    cost_rate = fee + slippage

    turnover = held.diff().abs().to_numpy(copy=True)
    turnover[0] = abs(held.iloc[0])
    turnover[-1] += abs(held.iloc[-1])  # close any open position at the end
    net = held.to_numpy(copy=True) * oo - turnover * cost_rate
    returns = pd.Series(net, index=df.index, name="returns")
    equity = initial_capital * (1.0 + returns).cumprod()

    trades = _extract_trades(df, held, oo, cost_rate)
    res = BacktestResult(returns=returns, equity=equity, position=held, trades=trades)
    res.metrics = compute_metrics(returns, res.trade_returns, df.index)
    return res


def _extract_trades(df: pd.DataFrame, held: pd.Series, oo: np.ndarray, cost_rate: float) -> pd.DataFrame:
    """A trade is a maximal run of bars holding the same non-zero position."""
    h = held.to_numpy(copy=True)
    rows = []
    i, n = 0, len(h)
    while i < n:
        if h[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and h[j + 1] == h[i]:
            j += 1
        size = h[i]
        gross = np.prod(1.0 + size * oo[i : j + 1]) - 1.0
        net = (1.0 + gross) * (1.0 - abs(size) * cost_rate) ** 2 - 1.0
        rows.append(
            {
                "entry_time": df.index[i],
                "exit_time": df.index[min(j + 1, n - 1)],
                "side": "long" if size > 0 else "short",
                "size": size,
                "bars": j - i + 1,
                "return": net,
            }
        )
        i = j + 1
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "side", "size", "bars", "return"])


def split_in_out(df: pd.DataFrame, in_sample: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * in_sample)
    return df.iloc[:cut], df.iloc[cut:]
