#!/usr/bin/env python3
"""Write a synthetic 1H OHLCV CSV to data/sample_btc_1h.csv so the pipeline runs out of the box.

Replace it with real data (e.g. exported from your exchange) before drawing any conclusions.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.data import make_synthetic  # noqa: E402

if __name__ == "__main__":
    out = ROOT / "data" / "sample_btc_1h.csv"
    out.parent.mkdir(exist_ok=True)
    df = make_synthetic(n=8000, seed=42)
    df.index.name = "timestamp"
    df.to_csv(out)
    print(f"wrote {out} ({len(df)} bars)")
