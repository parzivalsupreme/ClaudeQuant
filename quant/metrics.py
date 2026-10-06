"""Performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def bars_per_year(index: pd.Index) -> float:
    if len(index) < 2 or not isinstance(index, pd.DatetimeIndex):
        return 252.0
    step = pd.Series(index).diff().median().total_seconds()
    return 365.25 * 24 * 3600 / step if step > 0 else 252.0


def max_drawdown(equity: np.ndarray) -> float:
    """Most negative peak-to-trough decline, as a negative fraction."""
    equity = np.asarray(equity, dtype=float)
    if equity.size == 0:
        return 0.0
    peak = np.maximum.accumulate(np.maximum(equity, 1e-300))
    return float(np.min(equity / peak - 1.0))


def compute_metrics(returns: pd.Series, trade_returns: np.ndarray, index: pd.Index) -> dict:
    r = returns.to_numpy()
    equity = np.cumprod(1.0 + r)
    bpy = bars_per_year(index)
    years = len(r) / bpy if bpy else 0
    total = float(equity[-1] - 1.0) if len(equity) else 0.0
    cagr = float(equity[-1] ** (1 / years) - 1.0) if years > 0 and equity[-1] > 0 else -1.0
    std = r.std(ddof=1) if len(r) > 1 else 0.0
    sharpe = float(r.mean() / std * np.sqrt(bpy)) if std > 0 else 0.0
    tr = np.asarray(trade_returns, dtype=float)
    wins, losses = tr[tr > 0], tr[tr <= 0]
    pf = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else (float("inf") if wins.size else 0.0)
    return {
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": max_drawdown(np.r_[1.0, equity]),
        "sharpe": sharpe,
        "win_rate": float(wins.size / tr.size) if tr.size else 0.0,
        "profit_factor": pf,
        "n_trades": int(tr.size),
        "avg_trade": float(tr.mean()) if tr.size else 0.0,
        "exposure": float(np.mean(r != 0)) if len(r) else 0.0,
    }
