"""CSV attachments for the scores observed while building a reference."""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any

from core.project.manager import atomic_write_text, sha256_file
from workflow.optimization_scores import unscored_rows

SCORE_SCHEMA = "nmrfinesse_api.reference_optimization_scores.v1"
SCORE_COLUMNS = (
    "condition",
    "dataset_key",
    "run_id",
    "stage",
    "axis",
    "source",
    "candidate",
    "score",
    "score_metric",
    "selected",
    "applied",
    "status",
    "reason",
    "type",
    "off",
    "end",
    "pow",
    "c",
    "g1",
    "g2",
    "g3",
    "lb",
    "enabled",
    "mode",
    "order",
    "fwhm_points",
    "snr",
    "shape",
    "merged",
    "n_ref",
    "parameters_json",
    "reference_sigma",
    "scanned_traces",
    "used_traces",
    "total_traces",
    "sampling_json",
    "raw_score",
    "detection_score",
    "separation_score",
    "symmetry_score",
    "sidelobe_score",
    "resolution_score",
    "width_ratio",
    "resolution_reference_fwhm",
    "resolution_weight",
    "baseline_slope",
    "baseline_offset",
    "baseline_curvature",
    "baseline_stripe",
    "baseline_slope_score",
    "baseline_offset_score",
    "baseline_curvature_score",
    "baseline_stripe_score",
)


def _clean(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _context_rows(reference: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "condition": reference.condition,
            "dataset_key": reference.dataset_key,
            "run_id": reference.run_id,
        }
        for row in rows
    ]


def _write_table(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=SCORE_COLUMNS)
    writer.writeheader()
    for row in rows:
        params = row.get("parameters") or {}
        flat = {key: row.get(key) for key in SCORE_COLUMNS}
        flat.update(
            {
                key: params.get(key)
                for key in (
                    "type",
                    "off",
                    "end",
                    "pow",
                    "c",
                    "g1",
                    "g2",
                    "g3",
                    "lb",
                    "enabled",
                    "mode",
                    "order",
                )
            }
        )
        flat["fwhm_points"] = row.get("fwhm")
        flat["parameters_json"] = json.dumps(params, ensure_ascii=False, sort_keys=True)
        sampling = row.get("sampling") or {}
        flat.update({key: sampling.get(key) for key in
                     ("reference_sigma", "scanned_traces", "used_traces", "total_traces")})
        flat["sampling_json"] = json.dumps(sampling, ensure_ascii=False, sort_keys=True)
        writer.writerow(flat)
    atomic_write_text(path, buffer.getvalue())
    return {
        "schema": SCORE_SCHEMA,
        "path": str(path),
        "sha256": sha256_file(path),
        "n_rows": len(rows),
    }


def reference_score_rows(reference: Any) -> list[dict[str, Any]]:
    block = reference.optimization_scores or {}
    rows = block.get("rows")
    if rows:
        return list(rows)
    axes = [f"F{i}" for i in range(1, reference.ndim + 1)]
    return [
        row
        for stage in ("baseline", "window")
        for row in unscored_rows(
            stage,
            axes,
            source="",
            status="not_recorded",
            reason="rebuild_reference_for_scores",
        )
    ]


def write_reference_scores(reference: Any, directory: Path, rows: list[dict[str, Any]]) -> None:
    rows = _clean(rows)
    metadata = _write_table(directory / "optimization_scores.csv", _context_rows(reference, rows))
    reference.optimization_scores = {**metadata, "rows": rows}


def ensure_reference_scores(reference: Any, directory: Path) -> bool:
    block = reference.optimization_scores or {}
    path = directory / "optimization_scores.csv"
    if (
        block.get("rows")
        and block.get("schema") == SCORE_SCHEMA
        and block.get("path") == str(path)
        and path.is_file()
        and sha256_file(path) == block.get("sha256")
    ):
        return False
    write_reference_scores(reference, directory, reference_score_rows(reference))
    return True
