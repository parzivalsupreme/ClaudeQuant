#!/usr/bin/env python3
"""Monte Carlo stress test for a strategy.

Example:
    python scripts/stress_test.py --data data/sample_btc_1h.csv \
        --strategy quant.strategies.examples:sma_cross --params '{"fast": 20, "slow": 100}' \
        --out research/demo

    # an agent-written strategy file works too:
    python scripts/stress_test.py --data data/x.csv --strategy research/run/strategy_1.py:signal ...

Writes montecarlo.json, montecarlo.md and montecarlo.png into --out.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from quant import load_ohlcv  # noqa: E402
from quant.backtest import split_in_out  # noqa: E402
from quant.montecarlo import run_all, strip_private, verdict  # noqa: E402
from quant.validation import check_no_lookahead  # noqa: E402


def load_strategy(spec: str):
    target, _, func = spec.rpartition(":")
    if not target or not func:
        raise SystemExit("--strategy must look like module.path:func or path/to/file.py:func")
    if target.endswith(".py"):
        s = importlib.util.spec_from_file_location(Path(target).stem, target)
        mod = importlib.util.module_from_spec(s)
        sys.modules[s.name] = mod  # so PARAMS/GRID can be looked up from the function later
        s.loader.exec_module(mod)
    else:
        mod = importlib.import_module(target)
    return getattr(mod, func)


def fmt_pct(x: float) -> str:
    return f"{x:.1%}" if np.isfinite(x) else "n/a"


def write_report(results: dict, label: str, path: Path, sample: str) -> None:
    status, reasons = verdict(results)
    b = results["baseline"]
    L = [f"# Monte Carlo stress test: {label}", "", f"Data: {sample}", "", f"## Verdict: **{status}**", ""]
    L += [f"- {r}" for r in reasons]
    L += ["", "## Baseline", "", "| metric | value |", "|---|---|"]
    for k, v in b.items():
        L.append(f"| {k} | {v:.4f} |" if isinstance(v, float) else f"| {k} | {v} |")

    def dist_table(title: str, sec: dict, keys: list[str]) -> None:
        nonlocal L
        L += ["", f"## {title}", ""]
        if "error" in sec:
            L.append(f"_skipped: {sec['error']}_")
            return
        L += ["| metric | p5 | p25 | median | p75 | p95 |", "|---|---|---|---|---|---|"]
        for k in keys:
            d = sec[k]
            f = (lambda x: f"{x:.2f}") if k in ("sharpe", "n_trades") else fmt_pct
            L.append(f"| {k} | " + " | ".join(f(d[p]) for p in ("p5", "p25", "p50", "p75", "p95")) + " |")

    ts = results["trade_shuffle"]
    dist_table("1. Trade-order shuffle (sequence risk)", ts, ["max_drawdown"])
    if "error" not in ts:
        L += ["", f"Original max DD {fmt_pct(ts['original_max_drawdown'])}; "
              f"{ts['pct_worse_than_original_dd']:.0%} of orderings were worse. Risk of ruin: {ts['prob_ruin']:.1%}."]
    tb = results["trade_bootstrap"]
    dist_table("2. Trade bootstrap (confidence intervals)", tb, ["total_return", "max_drawdown", "mean_trade"])
    if "error" not in tb:
        L += ["", f"P(loss) {tb['prob_loss']:.1%}; risk of ruin {tb['prob_ruin']:.1%}; "
              f"return without best 5% of trades: {fmt_pct(tb['return_without_top5pct_trades'])}."]
    ex = results["execution_stress"]
    dist_table("3. Execution stress (1-3x slippage, 10% missed trades, late entries)", ex,
               ["total_return", "max_drawdown", "sharpe"])
    L += ["", f"P(loss) {ex['prob_loss']:.1%}."]
    pb = results["path_bootstrap"]
    dist_table("4. Synthetic price paths (block bootstrap)", pb, ["total_return", "max_drawdown", "sharpe", "n_trades"])
    L += ["", f"P(loss) {pb['prob_loss']:.1%}."]
    pt = results["permutation_test"]
    L += ["", "## 5. Permutation test (is it just noise?)", "",
          f"Real Sharpe {pt['real_sharpe']:.2f} vs shuffled-data median {pt['null_sharpe']['p50']:.2f} "
          f"(p95 {pt['null_sharpe']['p95']:.2f}). **p-value = {pt['p_value']:.3f}** "
          "(fraction of noise runs that did at least as well)."]
    path.write_text("\n".join(L) + "\n")


def plot(results: dict, path: Path, label: str) -> None:
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle(f"Monte Carlo stress test - {label}")
    ts = results["trade_shuffle"]
    if "_curves" in ts:
        curves = ts["_curves"]
        for c in curves[:200]:
            ax[0, 0].plot(c, color="#4C78A8", alpha=0.05, lw=0.8)
        for p, style in ((5, "--"), (50, "-"), (95, "--")):
            ax[0, 0].plot(np.percentile(curves, p, axis=0), color="#222", ls=style, lw=1.2, label=f"p{p}")
        ax[0, 0].set(title="Trade-order shuffle: equity paths", xlabel="trade #", ylabel="equity")
        ax[0, 0].legend()
        ax[0, 1].hist(ts["_dd"] * 100, bins=50, color="#E45756", alpha=0.8)
        ax[0, 1].axvline(ts["original_max_drawdown"] * 100, color="#222", ls="--", label="backtest")
        ax[0, 1].set(title="Max drawdown distribution", xlabel="max drawdown %")
        ax[0, 1].legend()
    tb, ex, pb = results["trade_bootstrap"], results["execution_stress"], results["path_bootstrap"]
    for data, name, color in ((tb.get("_final"), "trade bootstrap", "#4C78A8"),
                              (ex["_final"], "execution stress", "#F58518"),
                              (pb["_final"], "synthetic paths", "#54A24B")):
        if data is not None:
            ax[1, 0].hist(np.asarray(data) * 100, bins=50, alpha=0.5, color=color, label=name, density=True)
    ax[1, 0].axvline(results["baseline"]["total_return"] * 100, color="#222", ls="--", label="backtest")
    ax[1, 0].set(title="Total return distributions (normalised)", xlabel="total return %")
    ax[1, 0].legend()
    pt = results["permutation_test"]
    ax[1, 1].hist(pt["_null"], bins=40, color="#BAB0AC")
    ax[1, 1].axvline(pt["real_sharpe"], color="#E45756", lw=2, label=f"real (p={pt['p_value']:.3f})")
    ax[1, 1].set(title="Permutation test: Sharpe on shuffled data", xlabel="Sharpe")
    ax[1, 1].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--strategy", required=True, help="module:func or file.py:func")
    ap.add_argument("--params", default=None, help="JSON dict of strategy params (default: the module's PARAMS)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample", choices=["all", "in", "out"], default="out",
                    help="which part of the 70/30 split to stress (default: out-of-sample)")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--slippage", type=float, default=0.0005)
    ap.add_argument("--sims", type=int, default=1000, help="trade-level simulations")
    ap.add_argument("--path-sims", type=int, default=200, help="full re-run simulations")
    ap.add_argument("--block", type=int, default=24, help="block length (bars) for path bootstrap")
    ap.add_argument("--ruin", type=float, default=0.5, help="drawdown counted as ruin (0.5 = -50%%)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    strategy = load_strategy(a.strategy)
    params = json.loads(a.params) if a.params else getattr(sys.modules.get(strategy.__module__), "PARAMS", {})
    df = load_ohlcv(a.data)
    leaks = check_no_lookahead(df, strategy, params)
    if leaks:
        raise SystemExit(f"LOOKAHEAD DETECTED at {leaks[:5]} - fix the strategy before stress testing.")
    ins, oos = split_in_out(df)
    df = {"all": df, "in": ins, "out": oos}[a.sample]

    results = run_all(df, strategy, params, a.fee, a.slippage, a.sims, a.path_sims, a.block, a.ruin, a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    label = f"{a.strategy} {params}"
    sample = f"{a.data} [{a.sample}-sample, {len(df)} bars, {df.index[0]} -> {df.index[-1]}]"
    status, reasons = verdict(results)
    clean = strip_private(results)
    clean["verdict"] = {"status": status, "reasons": reasons}
    (out / "montecarlo.json").write_text(json.dumps(clean, indent=2, default=float))
    write_report(results, label, out / "montecarlo.md", sample)
    plot(results, out / "montecarlo.png", label)
    print(f"{status}")
    for r in reasons:
        print(f"  - {r}")
    print(f"wrote {out}/montecarlo.{{json,md,png}}")


if __name__ == "__main__":
    main()
