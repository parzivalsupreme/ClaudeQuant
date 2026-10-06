"""Reference strategies showing the signal(df, **params) -> position contract."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 100) -> pd.Series:
    """Trend: long when fast SMA > slow SMA, flat otherwise."""
    f = df["close"].rolling(fast).mean()
    s = df["close"].rolling(slow).mean()
    return (f > s).astype(float)


def rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))


def rsi_reversion(df: pd.DataFrame, period: int = 14, entry: float = 30.0, exit: float = 55.0, max_bars: int = 48) -> pd.Series:
    """Mean reversion: buy when RSI < entry, exit when RSI > exit or after max_bars."""
    r = rsi(df["close"], period).to_numpy()
    pos = np.zeros(len(df))
    held, age = 0.0, 0
    for i in range(len(df)):
        if held:
            age += 1
            if r[i] > exit or age >= max_bars:
                held, age = 0.0, 0
        elif r[i] < entry:
            held, age = 1.0, 0
        pos[i] = held
    return pd.Series(pos, index=df.index)
