"""Lossless CSV snapshots of the viewer's picked peak table."""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path

from core.project.manager import atomic_write_text
from ui_support.i18n import tr


def save_peak_snapshot(path: Path, rows: list[dict]) -> Path:
    """Save all row fields, including assignments and unrounded metrics."""
    coordinates = (["F1_shift", "F2_shift", "F3_shift"]
                   if rows and "F1_shift" in rows[0] else ["H_shift", "N_shift"])
    columns = list(dict.fromkeys(
        ["Peak_ID", *coordinates, "Intensity", "SN", "label"]
        + [key for row in rows for key in row]
    ))
    content = io.StringIO(newline="")
    writer = csv.DictWriter(content, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, content.getvalue())
    return path


def load_peak_snapshot(path: Path) -> list[dict]:
    """Restore our 2D/3D CSV format, rejecting incomplete coordinate tables."""
    with path.open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(tr("The CSV peak table is empty"))
    coordinates = (["F1_shift", "F2_shift", "F3_shift"]
                   if "F1_shift" in rows[0] else ["H_shift", "N_shift"])
    for index, row in enumerate(rows, 1):
        for key in coordinates:
            try:
                value = float(row[key])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(tr("The CSV must use the NMRFinesse peak table format")) from exc
            if not math.isfinite(value):
                raise ValueError(tr("The CSV contains non-finite peak coordinates"))
            row[key] = value
        for key in ("Intensity", "SN", "SNR", "Data", "Height", "Volume"):
            if row.get(key) not in (None, ""):
                row[key] = float(row[key])
        row["Peak_ID"] = int(row.get("Peak_ID") or index)
    return rows
