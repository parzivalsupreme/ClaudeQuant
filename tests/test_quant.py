import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quant import make_synthetic, run_backtest  # noqa: E402
from quant import montecarlo as mc  # noqa: E402
from quant.strategies.examples import rsi_reversion, sma_cross  # noqa: E402
from quant.validation import check_no_lookahead, parameter_sensitivity, walk_forward  # noqa: E402


@pytest.fixture(scope="module")
def df():
    return make_synthetic(n=3000, seed=1)


def test_fill_on_next_open_and_costs():
    idx = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame({"open": [100, 110, 121, 121], "high": 0, "low": 0, "close": [105, 115, 120, 121], "volume": 1},
                      index=idx, dtype=float)
    target = pd.Series([1, 1, 0, 0], index=idx, dtype=float)  # buy at bar0 close -> filled bar1 open (110)
    res = run_backtest(df, target, fee=0.0, slippage=0.0)
    assert res.position.tolist() == [0, 1, 1, 0]
    assert res.metrics["total_return"] == pytest.approx(121 / 110 - 1)
    costly = run_backtest(df, target, fee=0.001, slippage=0.0005)
    assert costly.metrics["total_return"] < res.metrics["total_return"]
    assert len(res.trades) == 1


def test_examples_have_no_lookahead(df):
    assert check_no_lookahead(df, sma_cross, {"fast": 10, "slow": 50}) == []
    assert check_no_lookahead(df, rsi_reversion, {}) == []


def test_lookahead_detector_catches_cheater(df):
    cheat = lambda d: (d["close"].shift(-1) > d["close"]).astype(float)  # noqa: E731
    assert check_no_lookahead(df, cheat, {}) != []


def test_trade_shuffle_preserves_final_return():
    tr = np.array([0.05, -0.02, 0.03, -0.04, 0.01] * 10)
    out = mc.trade_shuffle(tr, n_sims=200)
    assert out["total_return"]["p5"] == pytest.approx(out["total_return"]["p95"])
    assert out["max_drawdown"]["p5"] <= out["max_drawdown"]["p95"] <= 0


def test_bootstrap_detects_outlier_driven_edge():
    tr = np.r_[np.full(95, -0.003), np.full(5, 0.2)]
    out = mc.trade_bootstrap(tr, n_sims=200)
    assert out["return_without_top5pct_trades"] < 0


def test_synthetic_path_is_valid_ohlc(df):
    s = mc.synthetic_path(df, np.random.default_rng(0), block=24)
    assert len(s) == len(df)
    assert (s["high"] >= s[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (s["low"] <= s[["open", "close"]].min(axis=1) + 1e-9).all()
    perm = mc.synthetic_path(df, np.random.default_rng(0), block=1, replace=False)
    assert perm["close"].iloc[-1] == pytest.approx(df["close"].iloc[-1], rel=1e-6)  # same bars, new order


def test_permutation_test_finds_planted_edge():
    # Momentum is planted: returns are positively autocorrelated, so a trend rule should beat shuffled data.
    rng = np.random.default_rng(3)
    n = 3000
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = 0.3 * r[i - 1] + rng.normal(0, 0.005)
    close = 100 * np.exp(np.cumsum(r))
    idx = pd.date_range("2020", periods=n, freq="1h", tz="UTC")
    d = pd.DataFrame({"open": np.r_[100, close[:-1]], "close": close, "volume": 1.0}, index=idx)
    d["high"], d["low"] = d[["open", "close"]].max(axis=1), d[["open", "close"]].min(axis=1)
    strat = lambda x: np.sign(x["close"] - x["open"])  # noqa: E731
    out = mc.permutation_test(d, strat, {}, fee=0, slippage=0, n_sims=50)
    assert out["p_value"] < 0.05


def test_run_all_and_verdict_on_noise(df):
    res = mc.run_all(df, sma_cross, {"fast": 10, "slow": 50}, n_sims=200, n_path_sims=20)
    status, reasons = mc.verdict(res)
    assert status in {"REJECT", "NEEDS WORK", "PASS MONTE CARLO"} and reasons
    import json
    json.dumps(mc.strip_private(res), default=float)


def test_sensitivity_and_walk_forward(df):
    sens = parameter_sensitivity(df, sma_cross, {"fast": 10, "slow": 50})
    assert len(sens) == 6
    wf = walk_forward(df, sma_cross, {"fast": [10, 20], "slow": [50, 100]}, n_splits=3)
    assert len(wf["folds"]) == 3
