"""Structured observations of existing baseline and window choices; no rescoring."""

from __future__ import annotations

import math
from typing import Any


def unscored_rows(
    stage: str,
    axes: list[str],
    *,
    source: str,
    status: str,
    reason: str,
) -> list[dict[str, Any]]:
    return [
        {
            "stage": stage,
            "axis": axis,
            "source": source,
            "status": status,
            "reason": reason,
            "selected": False,
            "applied": False,
        }
        for axis in axes
    ]


def baseline_rows(result: Any) -> list[dict[str, Any]]:
    rows = []
    for axis, values in result.scores.items():
        values = dict(values)
        off_score = result.off_scores.get(axis, values.get("off:0"))
        if off_score is not None and not result.strict_candidates:
            values.setdefault("off:0", off_score)
        cfg = result.baseline.get(axis) or {}
        inferred_key = (
            "off:0"
            if not cfg.get("enabled", True)
            else "auto:1"
            if cfg.get("mode", "auto") == "auto"
            else f"order:{cfg.get('order', 0)}"
        )
        selected_key = result.selected_candidates.get(axis, inferred_key)
        component_scores = getattr(result, "components", {}).get(axis, {})
        for key, score in values.items():
            mode, order = key.split(":", 1)
            non_finite = not math.isfinite(score)
            vetoed = score == -1e9 or non_finite
            selected = key == selected_key and not vetoed
            reason = "non_finite_score" if non_finite else "stripe_veto" if vetoed else ""
            if selected and key == "off:0":
                reason = ("best_explicit_candidate" if result.strict_candidates else
                          "baseline_good" if score >= 95 else "gain_not_above_0.5")
            row = {
                "stage": "baseline",
                "axis": axis,
                "source": "joint_spectrum",
                "candidate": key,
                "parameters": {"enabled": mode != "off", "mode": mode, "order": int(order)},
                "score": None if vetoed else score,
                "score_metric": "baseline_quality",
                "selected": selected,
                "applied": selected,
                "status": "vetoed" if vetoed else "scored",
                "reason": reason,
                # Baseline candidates have one joint quality score. Window-only
                # metrics do not apply; keep the observed score explicit.
                "raw_score": None if vetoed else score,
            }
            # Components are optional and may be absent for custom scorers or
            # candidates that were not evaluated. Preserve measured zero values.
            row.update(component_scores.get(key, {}))
            rows.append(row)
    return rows


def window_rows(result: Any, axis: str, *, source: str, apply: bool = True) -> list[dict[str, Any]]:
    rows = []
    for value in result.scores:
        selected = bool(value.get("selected"))
        rows.append(
            {
                "stage": "window",
                "axis": axis,
                "source": source,
                "candidate": value["label"],
                "parameters": dict(value.get("cfg") or {}),
                "score": value["score"],
                "score_metric": "window_detection",
                "selected": selected,
                "applied": selected and apply,
                "status": value.get("status", "scored"),
                "reason": "nus_direct_window_fixed"
                if selected and not apply
                else value.get("reason", ""),
                **{key: value.get(key) for key in ("fwhm", "snr", "shape", "merged", "n_ref")},
                "sampling": dict(result.sampling),
                **{
                    key: value[key]
                    for key in (
                        "raw_score",
                        "detection_score",
                        "separation_score",
                        "symmetry_score",
                        "sidelobe_score",
                        "resolution_score",
                        "width_ratio",
                        "resolution_reference_fwhm",
                        "resolution_weight",
                    )
                    if key in value
                },
            }
        )
    for cfg in result.skipped_candidates:
        rows.append(
            {
                "stage": "window",
                "axis": axis,
                "source": source,
                "parameters": dict(cfg),
                "status": "skipped",
                "reason": "missing_sweep_width",
                "selected": False,
                "applied": False,
            }
        )
    rows = rows or unscored_rows(
        "window",
        [axis],
        source=source,
        status=result.status,
        reason=result.reason or "not_scored",
    )
    for row in rows:
        row["sampling"] = dict(result.sampling)
    return rows


def indirect_window_rows(result: Any, axes: list[str], *, source: str) -> list[dict[str, Any]]:
    rows = []
    for axis in axes:
        if axis in result.per_axis:
            rows.extend(window_rows(result.per_axis[axis], axis, source=source))
        else:
            rows.extend(
                unscored_rows(
                    "window",
                    [axis],
                    source=source,
                    status=result.status,
                    reason=result.reason or "not_scored",
                )
            )
    return rows
