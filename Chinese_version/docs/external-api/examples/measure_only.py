"""示例 3：在已有谱上按参考峰表测量峰位。

使用三点抛物线定位，直接输出统一峰表。

用法::

    python Chinese_version/docs/external-api/examples/measure_only.py --spectrum cand.ft2 \
        --peaks reference.list --out ./tables
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nmrfinesse_api import (
    measure_peak_positions,
    peak_table_rows,
    read_peak_table,
    read_reference_peaks,
    write_peak_table,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="nmrfinesse_api 只测量示例")
    parser.add_argument("--spectrum", required=True, help="NMRPipe 谱(ft2)")
    parser.add_argument("--peaks", required=True, help="参考峰表(.list/CSV)")
    parser.add_argument("--out", default="tables", help="输出目录")
    parser.add_argument("--window-ppm", type=float, default=None)
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = read_reference_peaks(args.peaks)
    measurements = measure_peak_positions(
        args.spectrum, rows, window_ppm=args.window_ppm, refine="parabolic"
    )
    table_rows = peak_table_rows(
        measurements,
        workflow_id="reference",
        condition="A",
        dataset=Path(args.spectrum).stem,
        method="parabolic",
    )
    table = write_peak_table(out / "peak_table_parabolic.csv", table_rows)
    detected = sum(1 for row in table_rows if row["detected"])
    print(f"检出 {detected}/{len(table_rows)} → {table}")

    sample = read_peak_table(table)[:1]
    print("列:", list(sample[0]) if sample else [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
