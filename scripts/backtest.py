#!/usr/bin/env python3
"""In-sample / out-of-sample backtest with lookahead check and equity chart.

    python scripts/backtest.py --data data/sample_btc_1h.csv \
        --strategy research/run/strategy_1.py:signal --out research/run --tag 1

Uses the module's PARAMS dict unless --params is given. Writes results_<tag>.json and equity_<tag>.png.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from quant import load_ohlcv, run_backtest  # noqa: E402
from quant.backtest import split_in_out  # noqa: E402
from quant.validation import check_no_lookahead  # noqa: E402
from stress_test import load_strategy  # noqa: E402


def module_attr(strategy, name: str, default):
    return getattr(inspect.getmodule(strategy), name, default)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--params", default=None, help="JSON; defaults to the module's PARAMS")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="1")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--slippage", type=float, default=0.0005)
    a = ap.parse_args()

    strategy = load_strategy(a.strategy)
    params = json.loads(a.params) if a.params else module_attr(strategy, "PARAMS", {})
    df = load_ohlcv(a.data)
    leaks = check_no_lookahead(df, strategy, params)
    ins, oos = split_in_out(df)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    results = {"params": params, "lookahead_violations": leaks}
    fig, ax = plt.subplots(figsize=(12, 5))
    for name, part in (("in_sample", ins), ("out_of_sample", oos)):
        res = run_backtest(part, strategy(part, **params), fee=a.fee, slippage=a.slippage)
        results[name] = res.metrics
        ax.plot(res.equity.index, res.equity.values, label=name.replace("_", "-"))
    ax.set(title=f"Equity - {a.strategy} {params}", ylabel="equity (start = 1)")
    ax.axvline(oos.index[0], color="#888", ls="--")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / f"equity_{a.tag}.png", dpi=110)

    (out / f"results_{a.tag}.json").write_text(json.dumps(results, indent=2, default=float))
    print(json.dumps(results, indent=2, default=float))
    if leaks:
        raise SystemExit(f"LOOKAHEAD DETECTED at {leaks[:5]}")


if __name__ == "__main__":
    main()
