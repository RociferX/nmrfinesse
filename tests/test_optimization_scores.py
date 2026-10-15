"""Reference score observations preserve choices, rejected candidates and missing data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.data.bruker_reader import read_dataset
from workflow.baseline_optimize import BaselineOptimizeResult
from workflow.optimization_scores import baseline_rows, window_rows
from workflow.window_optimize import WindowOptimizeResult


def test_baseline_scores_record_actual_off_and_veto() -> None:
    result = BaselineOptimizeResult(
        baseline={"F1": {"enabled": False}},
        scores={"F1": {"auto:1": 90.4, "order:2": -1e9}},
        spectrum_path="",
        off_scores={"F1": 90.0},
    )
    rows = {row["candidate"]: row for row in baseline_rows(result)}
    assert rows["off:0"]["selected"] and rows["off:0"]["applied"]
    assert rows["off:0"]["score"] == 90.0
    assert rows["off:0"]["reason"] == "gain_not_above_0.5"
    assert rows["auto:1"]["score"] == 90.4
    assert not rows["auto:1"]["selected"]
    assert rows["order:2"]["status"] == "vetoed"
    assert rows["order:2"]["score"] is None


def test_baseline_component_scores_keep_zero_and_raw_score_separate() -> None:
    result = BaselineOptimizeResult(
        baseline={"F1": {"enabled": False}},
        scores={"F1": {"off:0": 91.0, "auto:1": 90.0}},
        spectrum_path="",
        selected_candidates={"F1": "off:0"},
        components={
            "F1": {
                "off:0": {"baseline_slope": 0.0, "baseline_slope_score": 0.0},
                "auto:1": {"baseline_offset": 0.4},
            }
        },
    )
    rows = {row["candidate"]: row for row in baseline_rows(result)}
    assert rows["off:0"]["raw_score"] == rows["off:0"]["score"] == 91.0
    assert rows["off:0"]["selected"] and rows["off:0"]["applied"]
    assert rows["off:0"]["baseline_slope"] == 0.0
    assert rows["off:0"]["baseline_slope_score"] == 0.0
    assert "baseline_offset" not in rows["off:0"]
    assert rows["auto:1"]["baseline_offset"] == 0.4
    assert "baseline_slope" not in rows["auto:1"]


def test_window_score_components_are_transmitted_without_rescoring() -> None:
    result = WindowOptimizeResult(
        choice={"type": "none"},
        changed=False,
        scores=[
            {
                "cfg": {"type": "none"},
                "label": "none",
                "score": 0.73,
                "selected": True,
                "raw_score": 0.81,
                "detection_score": 0.7,
                "separation_score": 0.6,
                "symmetry_score": 0.5,
                "sidelobe_score": 0.4,
                "resolution_score": 0.3,
                "width_ratio": 1.25,
                "resolution_reference_fwhm": 2.5,
                "resolution_weight": 0.2,
            }
        ],
    )
    row = window_rows(result, "F2", source="fid")[0]
    assert row["score"] == 0.73 and row["raw_score"] == 0.81
    assert row["resolution_score"] == 0.3
    assert row["width_ratio"] == 1.25
    assert row["resolution_reference_fwhm"] == 2.5
    assert row["resolution_weight"] == 0.2
    assert row["selected"] and row["applied"]


@pytest.mark.parametrize("sampling", ["uniform", "nus"])
def test_processing_score_rows_distinguish_selected_and_applied(
    tmp_path: Path,
    bruker_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    sampling: str,
) -> None:
    from types import SimpleNamespace

    import workflow.phase_routes as routes
    from workflow.window_optimize import MultiWindowOptimizeResult

    experiment = read_dataset(bruker_dir / ("hsqc_2d" if sampling == "uniform" else "nus_2d"))
    work = tmp_path / "work"
    work.mkdir()
    joint = work / "joint.ft2"
    joint.write_bytes(b"joint")
    response = {"success": True, "spectrum_path": str(joint)}
    backend = SimpleNamespace(
        process=lambda *a, **k: response, finalize_nus=lambda *a, **k: response
    )
    baseline = BaselineOptimizeResult(
        baseline={"F1": {"enabled": False}},
        scores={"F1": {"off:0": 99.0}},
        spectrum_path=str(joint),
        off_scores={"F1": 99.0},
    )
    monkeypatch.setattr("workflow.baseline_optimize.optimize_baseline", lambda *a, **k: baseline)
    window = WindowOptimizeResult(
        choice={"type": "none"},
        changed=True,
        scores=[
            {
                "cfg": {"type": "none"},
                "label": "none",
                "score": 0.7,
                "selected": True,
                "fwhm": 2.0,
                "snr": 15.0,
                "shape": 0.8,
            }
        ],
    )
    monkeypatch.setattr(
        "workflow.window_optimize.optimize_direct_window_from_work", lambda *a, **k: window
    )
    indirect = MultiWindowOptimizeResult(
        choice={"F1": window.choice}, changed=True, per_axis={"F1": window}
    )
    for name in ("optimize_indirect_windows_from_work", "optimize_indirect_windows_from_recon"):
        monkeypatch.setattr(f"workflow.window_optimize.{name}", lambda *a, **k: indirect)
    optimize = (
        routes._optimize_uniform_processing
        if sampling == "uniform"
        else routes._optimize_nus_processing
    )
    output = optimize(experiment, backend, work, {}, {})
    rows = output["optimization_scores"]
    direct = next(row for row in rows if row["stage"] == "window" and row["axis"] == "F2")
    assert direct["score"] == 0.7 and direct["selected"]
    assert direct["applied"] is (sampling == "uniform")
    if sampling == "nus":
        assert direct["reason"] == "nus_direct_window_fixed"
        assert "F2" not in (output["window"] or {})
    else:
        assert output["window"]["F2"] == {"type": "none"}
    indirect_row = next(row for row in rows if row["stage"] == "window" and row["axis"] == "F1")
    assert indirect_row["applied"]
    assert indirect_row["source"] == ("fid" if sampling == "uniform" else "reconstruction")


def test_no_signal_and_skipped_windows_keep_missing_scores_explicit() -> None:
    from workflow.window_optimize import optimize_direct_window

    result = optimize_direct_window(np.zeros((4, 64), dtype=complex))
    rows = window_rows(result, "F2", source="fid")
    assert all(not row["selected"] and not row["applied"] for row in rows)
    assert any(row["reason"] == "no_valid_signal" for row in rows)
    skipped = [row for row in rows if row["reason"] == "missing_sweep_width"]
    assert skipped and all("score" not in row for row in skipped)
