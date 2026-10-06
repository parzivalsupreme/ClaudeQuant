"""Monte Carlo stress tests.

Five independent tests, each attacking a different way a backtest can lie:

1. trade_shuffle      - same trades, random order: how bad can the drawdown get by luck of sequencing?
2. trade_bootstrap    - resample trades with replacement: confidence intervals on return / drawdown.
3. execution_stress   - worse fills, missed trades, delayed entries: does the edge survive real execution?
4. path_bootstrap     - block-bootstrapped synthetic price paths, strategy re-run: is it tied to one exact history?
5. permutation_test   - shuffled bar returns destroy any real pattern: p-value that the edge is just noise.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .metrics import max_drawdown

Strategy = Callable[..., pd.Series]
PCTS = (5, 25, 50, 75, 95)


def _summary(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"mean": float("nan"), **{f"p{p}": float("nan") for p in PCTS}}
    return {"mean": float(x.mean()), **{f"p{p}": float(np.percentile(x, p)) for p in PCTS}}


def _equity_stats(trade_matrix: np.ndarray, ruin_level: float) -> dict:
    """trade_matrix: (n_sims, n_trades) of per-trade returns."""
    equity = np.cumprod(1.0 + trade_matrix, axis=1)
    equity = np.hstack([np.ones((equity.shape[0], 1)), equity])
    final = equity[:, -1] - 1.0
    peaks = np.maximum.accumulate(equity, axis=1)
    dds = (equity / peaks - 1.0).min(axis=1)
    return {
        "total_return": _summary(final),
        "max_drawdown": _summary(dds),
        "prob_loss": float(np.mean(final < 0)),
        "prob_ruin": float(np.mean(equity.min(axis=1) <= 1.0 - ruin_level)),
        "_dd": dds,
        "_final": final,
        "_curves": equity,
    }


def trade_shuffle(trade_returns: np.ndarray, n_sims: int = 1000, ruin_level: float = 0.5, seed: int = 0) -> dict:
    """Reorder the same trades. Final return is unchanged; drawdown path is not."""
    tr = np.asarray(trade_returns, dtype=float)
    if tr.size < 2:
        return {"error": "need at least 2 trades"}
    rng = np.random.default_rng(seed)
    mat = np.array([rng.permutation(tr) for _ in range(n_sims)])
    out = _equity_stats(mat, ruin_level)
    out["original_max_drawdown"] = max_drawdown(np.r_[1.0, np.cumprod(1.0 + tr)])
    out["pct_worse_than_original_dd"] = float(np.mean(out["_dd"] < out["original_max_drawdown"]))
    return out


def trade_bootstrap(trade_returns: np.ndarray, n_sims: int = 1000, ruin_level: float = 0.5, seed: int = 0) -> dict:
    """Resample trades with replacement to get confidence intervals."""
    tr = np.asarray(trade_returns, dtype=float)
    if tr.size < 2:
        return {"error": "need at least 2 trades"}
    rng = np.random.default_rng(seed)
    mat = rng.choice(tr, size=(n_sims, tr.size), replace=True)
    out = _equity_stats(mat, ruin_level)
    out["mean_trade"] = _summary(mat.mean(axis=1))
    # How much do the best 5% of trades matter? If removing them kills the edge, it's outlier-driven.
    k = max(1, int(round(tr.size * 0.05)))
    trimmed = np.sort(tr)[:-k]
    out["return_without_top5pct_trades"] = float(np.prod(1.0 + trimmed) - 1.0)
    return out


def _drop_trades(pos: pd.Series, skip_prob: float, rng: np.random.Generator) -> pd.Series:
    """Zero out whole runs of non-zero position with probability skip_prob each."""
    p = pos.to_numpy(copy=True)
    run_id = np.cumsum(np.r_[True, p[1:] != p[:-1]])
    for rid in np.unique(run_id[p != 0]):
        if rng.random() < skip_prob:
            p[run_id == rid] = 0.0
    return pd.Series(p, index=pos.index)


def execution_stress(
    df: pd.DataFrame,
    strategy: Strategy,
    params: dict,
    fee: float = 0.001,
    slippage: float = 0.0005,
    n_sims: int = 300,
    slippage_mult: tuple[float, float] = (1.0, 3.0),
    skip_prob: float = 0.1,
    delay_prob: float = 0.3,
    seed: int = 0,
) -> dict:
    """Re-run with random slippage (1-3x), ~10% missed trades and occasional 1-bar late entries."""
    rng = np.random.default_rng(seed)
    target = strategy(df, **params)
    rets, dds, sharpes = [], [], []
    for _ in range(n_sims):
        t = _drop_trades(target, skip_prob, rng)
        if rng.random() < delay_prob:
            t = t.shift(1).fillna(0.0)
        slip = slippage * rng.uniform(*slippage_mult)
        m = run_backtest(df, t, fee=fee, slippage=slip).metrics
        rets.append(m["total_return"])
        dds.append(m["max_drawdown"])
        sharpes.append(m["sharpe"])
    rets = np.array(rets)
    return {
        "total_return": _summary(rets),
        "max_drawdown": _summary(dds),
        "sharpe": _summary(sharpes),
        "prob_loss": float(np.mean(rets < 0)),
        "_final": rets,
    }


def _bar_ratios(df: pd.DataFrame) -> np.ndarray:
    prev_close = df["close"].shift(1).to_numpy(copy=True)
    prev_close[0] = df["open"].iloc[0]
    cols = [df[c].to_numpy() / prev_close for c in ("open", "high", "low", "close")]
    return np.column_stack(cols + [df["volume"].to_numpy()])


def _rebuild(ratios: np.ndarray, start: float, index: pd.Index) -> pd.DataFrame:
    close = start * np.cumprod(ratios[:, 3])
    prev = np.r_[start, close[:-1]]
    return pd.DataFrame(
        {
            "open": prev * ratios[:, 0],
            "high": prev * ratios[:, 1],
            "low": prev * ratios[:, 2],
            "close": close,
            "volume": ratios[:, 4],
        },
        index=index,
    )


def synthetic_path(df: pd.DataFrame, rng: np.random.Generator, block: int = 24, replace: bool = True) -> pd.DataFrame:
    """Block-bootstrap bars (keeps short-term autocorrelation and volatility clustering inside blocks)."""
    ratios = _bar_ratios(df)
    n = len(ratios)
    block = max(1, min(block, n))
    if replace:
        starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
    else:
        blocks = [np.arange(s, min(s + block, n)) for s in range(0, n, block)]
        idx = np.concatenate([blocks[i] for i in rng.permutation(len(blocks))])
    return _rebuild(ratios[idx], float(df["open"].iloc[0]), df.index)


def path_bootstrap(
    df: pd.DataFrame,
    strategy: Strategy,
    params: dict,
    fee: float = 0.001,
    slippage: float = 0.0005,
    n_sims: int = 200,
    block: int = 24,
    seed: int = 0,
) -> dict:
    """Re-run the strategy on synthetic histories that share the data's statistical character."""
    rng = np.random.default_rng(seed)
    rets, dds, sharpes, ntr = [], [], [], []
    for _ in range(n_sims):
        sdf = synthetic_path(df, rng, block=block)
        m = run_backtest(sdf, strategy(sdf, **params), fee=fee, slippage=slippage).metrics
        rets.append(m["total_return"])
        dds.append(m["max_drawdown"])
        sharpes.append(m["sharpe"])
        ntr.append(m["n_trades"])
    rets = np.array(rets)
    return {
        "total_return": _summary(rets),
        "max_drawdown": _summary(dds),
        "sharpe": _summary(sharpes),
        "n_trades": _summary(ntr),
        "prob_loss": float(np.mean(rets < 0)),
        "_final": rets,
    }


def permutation_test(
    df: pd.DataFrame,
    strategy: Strategy,
    params: dict,
    fee: float = 0.001,
    slippage: float = 0.0005,
    n_sims: int = 200,
    seed: int = 0,
) -> dict:
    """Shuffle individual bars (no replacement). This keeps the return distribution but destroys
    every time-series pattern. If the real Sharpe isn't clearly above the shuffled ones, there's no edge."""
    rng = np.random.default_rng(seed)
    real = run_backtest(df, strategy(df, **params), fee=fee, slippage=slippage).metrics["sharpe"]
    null = []
    for _ in range(n_sims):
        sdf = synthetic_path(df, rng, block=1, replace=False)
        null.append(run_backtest(sdf, strategy(sdf, **params), fee=fee, slippage=slippage).metrics["sharpe"])
    null = np.array(null)
    p_value = float((np.sum(null >= real) + 1) / (n_sims + 1))
    return {"real_sharpe": float(real), "null_sharpe": _summary(null), "p_value": p_value, "_null": null}


def run_all(
    df: pd.DataFrame,
    strategy: Strategy,
    params: dict,
    fee: float = 0.001,
    slippage: float = 0.0005,
    n_sims: int = 1000,
    n_path_sims: int = 200,
    block: int = 24,
    ruin_level: float = 0.5,
    seed: int = 0,
) -> dict:
    base = run_backtest(df, strategy(df, **params), fee=fee, slippage=slippage)
    tr = base.trade_returns
    return {
        "baseline": base.metrics,
        "trade_shuffle": trade_shuffle(tr, n_sims, ruin_level, seed),
        "trade_bootstrap": trade_bootstrap(tr, n_sims, ruin_level, seed),
        "execution_stress": execution_stress(df, strategy, params, fee, slippage, n_path_sims, seed=seed),
        "path_bootstrap": path_bootstrap(df, strategy, params, fee, slippage, n_path_sims, block, seed),
        "permutation_test": permutation_test(df, strategy, params, fee, slippage, n_path_sims, seed),
    }


def verdict(results: dict, min_trades: int = 100) -> tuple[str, list[str]]:
    """Harsh, rule-based verdict. Any FAIL -> REJECT; any WARN -> NEEDS WORK."""
    fails, warns = [], []
    b = results["baseline"]
    if b["n_trades"] < 30:
        fails.append(f"only {b['n_trades']} trades - statistically meaningless")
    elif b["n_trades"] < min_trades:
        warns.append(f"only {b['n_trades']} trades (< {min_trades})")
    if b["sharpe"] > 3:
        warns.append(f"Sharpe {b['sharpe']:.2f} > 3 - suspicious, check for bugs/lookahead")

    pt = results["permutation_test"]
    if pt["p_value"] > 0.10:
        fails.append(f"permutation p-value {pt['p_value']:.3f}: indistinguishable from noise")
    elif pt["p_value"] > 0.05:
        warns.append(f"permutation p-value {pt['p_value']:.3f}: weak evidence")

    tb = results["trade_bootstrap"]
    if "error" not in tb:
        if tb["total_return"]["p5"] < 0:
            warns.append(f"bootstrap 5th-pct return {tb['total_return']['p5']:.1%} < 0")
        if tb["return_without_top5pct_trades"] < 0:
            fails.append(
                f"removing best 5% of trades turns it negative ({tb['return_without_top5pct_trades']:.1%}) - outlier-driven"
            )
        if tb["prob_ruin"] > 0.05:
            fails.append(f"risk of ruin {tb['prob_ruin']:.1%} > 5%")

    ts = results["trade_shuffle"]
    if "error" not in ts and ts["max_drawdown"]["p5"] < -0.5:
        warns.append(f"5% of trade orderings see drawdown worse than {ts['max_drawdown']['p5']:.1%}")

    ex = results["execution_stress"]
    if ex["total_return"]["p50"] < 0:
        fails.append(f"median return under execution stress is {ex['total_return']['p50']:.1%}")
    elif ex["prob_loss"] > 0.25:
        warns.append(f"{ex['prob_loss']:.0%} of execution-stress runs lose money")

    pb = results["path_bootstrap"]
    if pb["prob_loss"] > 0.5:
        fails.append(f"loses money on {pb['prob_loss']:.0%} of synthetic paths")
    elif pb["prob_loss"] > 0.3:
        warns.append(f"loses money on {pb['prob_loss']:.0%} of synthetic paths")

    if fails:
        return "REJECT", fails + warns
    if warns:
        return "NEEDS WORK", warns
    return "PASS MONTE CARLO", ["all Monte Carlo checks passed - still requires walk-forward and paper trading"]


def strip_private(obj):
    """Remove numpy arrays (keys starting with '_') so results are JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: strip_private(v) for k, v in obj.items() if not k.startswith("_")}
    return obj
