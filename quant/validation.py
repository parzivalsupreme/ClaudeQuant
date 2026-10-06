"""Lookahead check, parameter sensitivity and walk-forward analysis."""

from __future__ import annotations

import itertools
from typing import Callable

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .metrics import compute_metrics

Strategy = Callable[..., pd.Series]


def check_no_lookahead(df: pd.DataFrame, strategy: Strategy, params: dict, n_checks: int = 20, seed: int = 0) -> list:
    """Signal at bar k must be identical whether or not later bars exist. Returns offending timestamps."""
    full = strategy(df, **params).reindex(df.index).fillna(0.0)
    rng = np.random.default_rng(seed)
    cuts = rng.integers(len(df) // 4, len(df), size=n_checks)
    bad = []
    for k in cuts:
        part = strategy(df.iloc[: k + 1], **params).reindex(df.index[: k + 1]).fillna(0.0)
        if not np.isclose(part.iloc[-1], full.iloc[k]):
            bad.append(str(df.index[k]))
    return bad


def parameter_sensitivity(
    df: pd.DataFrame, strategy: Strategy, params: dict, pct: float = 0.2, fee: float = 0.001, slippage: float = 0.0005
) -> pd.DataFrame:
    """Nudge each numeric parameter by -pct, 0, +pct (one at a time). A real edge degrades gracefully."""
    rows = []
    for name, value in params.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        for mult in (1 - pct, 1.0, 1 + pct):
            v = value * mult
            v = max(1, int(round(v))) if isinstance(value, int) else v
            p = {**params, name: v}
            m = run_backtest(df, strategy(df, **p), fee=fee, slippage=slippage).metrics
            rows.append({"param": name, "value": v, "mult": mult, **m})
    return pd.DataFrame(rows)


def walk_forward(
    df: pd.DataFrame,
    strategy: Strategy,
    grid: dict,
    n_splits: int = 5,
    train_frac: float = 0.7,
    fee: float = 0.001,
    slippage: float = 0.0005,
) -> dict:
    """Anchored walk-forward: optimise Sharpe on all data so far, trade the next unseen chunk."""
    names = list(grid)
    combos = [dict(zip(names, vals)) for vals in itertools.product(*grid.values())]
    n = len(df)
    first_test = int(n * train_frac)
    edges = np.linspace(first_test, n, n_splits + 1).astype(int)
    oos_returns, folds = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        train = df.iloc[:a]
        best = max(combos, key=lambda p: run_backtest(train, strategy(train, **p), fee, slippage).metrics["sharpe"])
        # compute signals with history so indicators are warmed up, but only score bars a..b
        window = df.iloc[:b]
        res = run_backtest(window, strategy(window, **best), fee, slippage)
        seg = res.returns.iloc[a:b]
        oos_returns.append(seg)
        folds.append({"start": str(df.index[a]), "end": str(df.index[b - 1]), "params": best,
                      "oos_return": float(np.prod(1 + seg) - 1)})
    oos = pd.concat(oos_returns)
    metrics = compute_metrics(oos, np.array([]), oos.index)
    for k in ("win_rate", "profit_factor", "n_trades", "avg_trade"):  # trades are not stitched across folds
        metrics.pop(k)
    return {"folds": folds, "oos_metrics": metrics, "oos_returns": oos}


def regime_breakdown(df: pd.DataFrame, returns: pd.Series, trend: int = 200, band: float = 0.02) -> dict:
    """Split strategy returns by market regime: close vs its SMA(trend), +/-band counts as sideways.
    ``returns`` may cover a subset of ``df`` (e.g. out-of-sample); the SMA is computed on all of ``df``."""
    sma = df["close"].rolling(trend).mean()
    dev = df["close"] / sma - 1
    regime = pd.Series("sideways", index=df.index).where(dev.abs() <= band)
    regime = regime.fillna(pd.Series(np.where(dev > 0, "bull", "bear"), index=df.index))
    regime[sma.isna()] = "warmup"
    regime = regime.reindex(returns.index)
    out = {}
    for name in ("bull", "bear", "sideways"):
        r = returns[regime == name]
        out[name] = {"bars": int(len(r)), **({k: v for k, v in compute_metrics(r, np.array([]), r.index).items()
                                               if k in ("total_return", "sharpe", "max_drawdown")} if len(r) > 1 else {})}
    return out
