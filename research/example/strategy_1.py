"""Example agent-style strategy file: SMA trend filter. Delete once you have real runs."""

import pandas as pd

PARAMS = {"fast": 20, "slow": 100}
GRID = {"fast": [10, 20, 40], "slow": [50, 100, 200]}


def signal(df: pd.DataFrame, fast: int = 20, slow: int = 100) -> pd.Series:
    f = df["close"].rolling(fast).mean()
    s = df["close"].rolling(slow).mean()
    return (f > s).astype(float)
