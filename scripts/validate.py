#!/usr/bin/env python3
"""Parameter sensitivity (+/-20%) and anchored walk-forward.

    python scripts/validate.py --data data/sample_btc_1h.csv \
        --strategy research/run/strategy_1.py:signal --out research/run --tag 1

Uses the module's PARAMS and GRID. Writes validation_<tag>.json and sensitivity_<tag>.csv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backtest import module_attr  # noqa: E402
from quant import load_ohlcv  # noqa: E402
from quant.validation import parameter_sensitivity, walk_forward  # noqa: E402
from stress_test import load_strategy  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="1")
    ap.add_argument("--splits", type=int, default=5)
    a = ap.parse_args()

    strategy = load_strategy(a.strategy)
    params = module_attr(strategy, "PARAMS", {})
    grid = module_attr(strategy, "GRID", {k: [v] for k, v in params.items()})
    df = load_ohlcv(a.data)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    sens = parameter_sensitivity(df, strategy, params)
    sens.to_csv(out / f"sensitivity_{a.tag}.csv", index=False)
    wf = walk_forward(df, strategy, grid, n_splits=a.splits)
    base_sharpe = sens.loc[sens["mult"] == 1.0, "sharpe"].iloc[0] if len(sens) else float("nan")
    result = {
        "sensitivity": {
            "base_sharpe": float(base_sharpe),
            "min_sharpe": float(sens["sharpe"].min()) if len(sens) else float("nan"),
            "max_sharpe": float(sens["sharpe"].max()) if len(sens) else float("nan"),
            "table": f"sensitivity_{a.tag}.csv",
        },
        "walk_forward": {"folds": wf["folds"], "oos_metrics": wf["oos_metrics"]},
    }
    (out / f"validation_{a.tag}.json").write_text(json.dumps(result, indent=2, default=float))
    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
