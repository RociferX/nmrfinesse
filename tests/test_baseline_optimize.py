"""Dimension-by-dimension baseline optimisation test (G2B-007)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.data.bruker_reader import read_dataset
from workflow.baseline_optimize import optimize_baseline
from workflow.optimization_candidates import CandidateSelectionError
from workflow.optimization_scores import baseline_rows


def _write_ft2(path: Path, data: np.ndarray) -> None:
    from nmrglue.fileio import pipe

    dic = {k: "0" for k in pipe.fdata_dic}
    dic["FDMAGIC"] = 9.2330230000000007e14
    dic["FDDIMCOUNT"] = 2
    dic["FDSIZE"] = data.shape[1]
    dic["FDSPECNUM"] = data.shape[0]
    dic["FDQUADFLAG"] = 1
    dic["FDF1QUADFLAG"] = 1
    dic["FDF2QUADFLAG"] = 1
    for prefix in ("FDF1", "FDF2"):
        dic[prefix + "SW"] = "6000.0"
        dic[prefix + "OBS"] = "600.0"
        dic[prefix + "CAR"] = "4.7"
        dic[prefix + "ORIG"] = "1000.0"
    pipe.write(str(path), dic, data.astype(np.float32), overwrite=True)


def test_optimize_baseline_direct_axis_slope(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """Direct dimension (F2) linear drift: optimisation selects a correction (off score is below
    the best).
    """
    spec = np.zeros((32, 64))
    spec += np.linspace(-50.0, 50.0, 64)[np.newaxis, :]
    ft2 = tmp_path / "spec.ft2"
    _write_ft2(ft2, spec)
    experiment = read_dataset(bruker_dir / "hsqc_2d")

    result = optimize_baseline(experiment, ft2)
    assert "F2" in result.baseline and "F1" in result.baseline
    assert "off:0" in result.scores["F2"]

    assert result.baseline["F2"]["enabled"] is True
    assert result.scores["F2"]["off:0"] < max(result.scores["F2"].values())
    assert result.off_scores["F2"] == result.scores["F2"]["off:0"]
    joined = "\n".join(result.logs)
    assert "F2" in joined and "基线已优化" in joined
    assert "F1" in joined and "未优化" in joined


def test_optimize_baseline_grid_contains_off_and_orders(
    tmp_path: Path, bruker_dir: Path
) -> None:
    experiment = read_dataset(bruker_dir / "hsqc_2d")

    spec = np.full((32, 64), 100.0)
    spec += np.linspace(-1.0, 1.0, 64)[np.newaxis, :]
    ft2 = tmp_path / "mid.ft2"
    _write_ft2(ft2, spec)
    result = optimize_baseline(experiment, ft2)
    assert result.scores["F2"]["off:0"] < 95.0
    assert result.scores["F2"]["off:0"] >= max(result.scores["F2"].values()) - 1e-9
    assert "auto:1" in result.scores["F2"]
    assert "order:3" in result.scores["F2"]


def test_optimize_baseline_good_baseline_skips_grid(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """0.2.199-patch8: an axis with off score >= 95 skips the candidate grid and stays off."""
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spec = np.zeros((32, 64))
    ft2 = tmp_path / "flat.ft2"
    _write_ft2(ft2, spec)
    result = optimize_baseline(experiment, ft2)
    assert set(result.scores["F2"]) == {"off:0"}
    assert result.scores["F2"]["off:0"] == 100.0
    assert result.baseline["F2"]["enabled"] is False
    assert any("基线已良好" in line for line in result.logs)


def test_explicit_baseline_grid_ignores_early_skip_and_off_gain_rule(
    tmp_path: Path, bruker_dir: Path,
) -> None:
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spectrum = tmp_path / "explicit.ft2"
    _write_ft2(spectrum, np.zeros((32, 64)))
    result = optimize_baseline(
        experiment, spectrum, grid=[("order", 4), ("order", 2)],
        score_fn=lambda array, axis: 100.0, strict_candidates=True,
    )
    for axis in ("F1", "F2"):
        assert list(result.scores[axis]) == ["order:4", "order:2"]
        assert result.baseline[axis] == {"enabled": True, "mode": "order", "order": 4}
        assert result.selected_candidates[axis] == "order:4"
    assert all(row["candidate"] != "off:0" for row in baseline_rows(result))


def test_all_vetoed_explicit_baselines_fail_instead_of_adding_off(
    tmp_path: Path, bruker_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spectrum = tmp_path / "vetoed.ft2"
    _write_ft2(spectrum, np.zeros((32, 64)))
    monkeypatch.setattr("workflow.baseline_optimize._has_stripe_artifact", lambda *a, **k: True)
    with pytest.raises(CandidateSelectionError, match="No valid explicit baseline"):
        optimize_baseline(experiment, spectrum, grid=[("order", 4)], strict_candidates=True)


def test_non_finite_explicit_baseline_scores_fail(
    tmp_path: Path, bruker_dir: Path,
) -> None:
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spectrum = tmp_path / "nonfinite.ft2"
    _write_ft2(spectrum, np.zeros((32, 64)))
    with pytest.raises(CandidateSelectionError, match="No valid explicit baseline"):
        optimize_baseline(
            experiment, spectrum, grid=[("off", 0)], strict_candidates=True,
            score_fn=lambda array, axis: float("nan"),
        )


def test_valid_explicit_baseline_beats_non_finite_candidate(
    tmp_path: Path, bruker_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spectrum = tmp_path / "partly-valid.ft2"
    _write_ft2(spectrum, np.zeros((32, 64)))
    monkeypatch.setattr("workflow.baseline_optimize._has_stripe_artifact", lambda *a, **k: False)
    scores = iter([0.0, float("nan"), 50.0] * 2)
    result = optimize_baseline(
        experiment, spectrum, grid=[("off", 0), ("order", 1)], strict_candidates=True,
        score_fn=lambda array, axis: next(scores),
    )
    rows = baseline_rows(result)
    assert all(row["candidate"] == "order:1" for row in rows if row["selected"])
    rejected = [row for row in rows if row["candidate"] == "off:0"]
    assert all(row["score"] is None and row["reason"] == "non_finite_score" for row in rejected)


def test_optimize_baseline_reports_progress(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """0.2.199-patch7: baseline optimisation reports progress per axis/candidate (a candidate runs
    only when off score <95).
    """
    spec = np.full((32, 64), 100.0)
    spec += np.linspace(-1.0, 1.0, 64)[np.newaxis, :]
    ft2 = tmp_path / "spec.ft2"
    _write_ft2(ft2, spec)
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    messages: list[str] = []
    optimize_baseline(experiment, ft2, progress=messages.append)
    assert any("轴 F1" in m for m in messages)
    assert any("score=" in m for m in messages)


def test_optimize_baseline_cancelled_raises(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """0.2.199-patch7: with the cancel flag set, baseline optimisation raises an exception and
    exits at once (off score <95).
    """
    import pytest

    spec = np.full((32, 64), 100.0)
    spec += np.linspace(-1.0, 1.0, 64)[np.newaxis, :]
    ft2 = tmp_path / "spec.ft2"
    _write_ft2(ft2, spec)
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    with pytest.raises(RuntimeError, match="任务已取消"):
        optimize_baseline(experiment, ft2, cancel=lambda: True)


def test_decimated_reduces_traces() -> None:
    """0.2.199-patch8: trace subsampling keeps the number of scoring traces within the cap."""
    from workflow.baseline_optimize import _decimated

    arr = np.zeros((120, 80, 200))
    for axis in range(3):
        dec = _decimated(arr, axis, max_traces=4096)
        n = dec.shape[axis]
        assert dec.size // n <= 4096
        assert dec.ndim == 3


def test_optimize_baseline_small_max_traces_works(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """0.2.199-patch8: small max_traces still yields a valid baseline config."""
    spec = np.zeros((32, 64))
    ft2 = tmp_path / "spec.ft2"
    _write_ft2(ft2, spec)
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    result = optimize_baseline(experiment, ft2, max_traces=8)
    assert "F2" in result.baseline and "F1" in result.baseline
    assert "off:0" in result.scores["F2"]


def test_default_baseline_components_reuse_each_candidate_evaluation(
    tmp_path: Path, bruker_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that component measurement reuses each default candidate evaluation."""
    from core.qc import baseline_quality

    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spectrum = tmp_path / "components.ft2"
    spec = np.full((32, 64), 100.0)
    spec += np.linspace(-1.0, 1.0, 64)[np.newaxis, :]
    _write_ft2(spectrum, spec)
    evaluate = baseline_quality.evaluate
    calls = 0

    def counted_evaluate(data: np.ndarray, *args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return evaluate(data, *args, **kwargs)

    monkeypatch.setattr(baseline_quality, "evaluate", counted_evaluate)
    monkeypatch.setattr(
        "workflow.baseline_optimize._has_stripe_artifact", lambda *a, **k: False
    )
    result = optimize_baseline(
        experiment, spectrum, grid=[("off", 0), ("order", 1)]
    )

    expected_fields = {
        "baseline_slope", "baseline_offset", "baseline_curvature", "baseline_stripe",
        "baseline_slope_score", "baseline_offset_score",
        "baseline_curvature_score", "baseline_stripe_score",
    }
    assert calls == sum(len(axis_scores) for axis_scores in result.scores.values())
    for axis, axis_scores in result.scores.items():
        assert set(result.components[axis]) == set(axis_scores)
        for candidate, score in axis_scores.items():
            measured = result.components[axis][candidate]
            assert set(measured) == expected_fields
            assert measured["baseline_slope_score"] == pytest.approx(
                100.0 * (1.0 - min(1.0, 4.0 * abs(measured["baseline_slope"])))
            )
            assert measured["baseline_offset_score"] == pytest.approx(
                100.0 * (1.0 - min(1.0, 2.0 * abs(measured["baseline_offset"])))
            )
            assert measured["baseline_curvature_score"] == pytest.approx(
                100.0 * (1.0 - min(1.0, 6.0 * measured["baseline_curvature"]))
            )
            assert measured["baseline_stripe_score"] == pytest.approx(
                100.0 * (1.0 - min(1.0, measured["baseline_stripe"]))
            )
            expected_score = 100.0 * (
                1.0
                - min(
                    1.0,
                    4.0 * abs(measured["baseline_slope"])
                    + 2.0 * abs(measured["baseline_offset"])
                    + 6.0 * measured["baseline_curvature"]
                    + measured["baseline_stripe"],
                )
            )
            assert score == pytest.approx(expected_score)


def test_injected_scorer_and_stripe_veto_do_not_fabricate_components(
    tmp_path: Path, bruker_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment = read_dataset(bruker_dir / "hsqc_2d")
    spectrum = tmp_path / "injected-components.ft2"
    _write_ft2(spectrum, np.full((32, 64), 100.0))
    monkeypatch.setattr(
        "workflow.baseline_optimize._has_stripe_artifact", lambda *a, **k: False
    )
    calls: list[int] = []
    injected = optimize_baseline(
        experiment,
        spectrum,
        grid=[("off", 0), ("order", 1)],
        score_fn=lambda array, axis: calls.append(axis) or float(len(calls)),
    )
    assert len(calls) == 2 * (1 + 2)  # off baseline measurement and both grid candidates
    assert injected.components == {}

    monkeypatch.setattr(
        "workflow.baseline_optimize._has_stripe_artifact", lambda *a, **k: True
    )
    vetoed = optimize_baseline(
        experiment, spectrum, grid=[("order", 1)],
    )
    for axis, axis_scores in vetoed.scores.items():
        assert axis_scores["order:1"] == -1e9
        assert set(vetoed.components[axis]) == {"off:0"}
