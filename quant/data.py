"""Data loading and synthetic data generation."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED = ["open", "high", "low", "close", "volume"]


def load_ohlcv(path: str) -> pd.DataFrame:
    """Load a CSV with columns timestamp, open, high, low, close, volume."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts_col = next((c for c in ("timestamp", "date", "datetime", "time") if c in df.columns), None)
    if ts_col is None:
        raise ValueError(f"{path}: no timestamp/date column found")
    ts = df[ts_col]
    if pd.api.types.is_numeric_dtype(ts):
        # epoch seconds or milliseconds
        unit = "ms" if ts.max() > 1e11 else "s"
        df.index = pd.to_datetime(ts, unit=unit, utc=True)
    else:
        df.index = pd.to_datetime(ts, utc=True)
    df = df.drop(columns=[ts_col])
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")
    df = df[REQUIRED].astype(float)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df.dropna()


def make_synthetic(n: int = 8000, freq: str = "1h", seed: int = 0, start_price: float = 30000.0) -> pd.DataFrame:
    """Regime-switching random walk (bull / bear / sideways) for demos and tests.

    It contains no exploitable edge by construction, so a correct pipeline
    should usually REJECT strategies run on it.
    """
    rng = np.random.default_rng(seed)
    regimes = {"bull": (0.0004, 0.008), "bear": (-0.0004, 0.012), "side": (0.0, 0.006)}
    names = list(regimes)
    rets = np.empty(n)
    i = 0
    while i < n:
        name = names[rng.integers(len(names))]
        length = int(rng.integers(200, 1200))
        mu, sigma = regimes[name]
        k = min(length, n - i)
        rets[i : i + k] = rng.normal(mu, sigma, k)
        i += k
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.r_[start_price, close[:-1]] * np.exp(rng.normal(0, 0.0005, n))
    spread = np.abs(rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.lognormal(10, 0.5, n) * (1 + 20 * np.abs(rets))
    idx = pd.date_range("2020-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
