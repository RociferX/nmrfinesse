"""Direct-dimension window function optimisation tests: synthetic FID in-memory scoring and
explicit no-window support on the rendering side.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from workflow.window_optimize import (
    DEFAULT_CANDIDATES,
    INDIRECT_CANDIDATES,
    WindowOptimizeResult,
    optimize_direct_window,
    optimize_direct_window_from_work,
    optimize_indirect_windows,
    optimize_indirect_windows_from_recon,
    optimize_indirect_windows_from_work,
)


def _synth_fid(n_traces: int = 16, n: int = 512) -> np.ndarray:
    """Synthetic direct-dimension FID: an exponentially decaying single peak plus slight noise
    (different traces, different amplitudes).
    """
    rng = np.random.default_rng(7)
    t = np.arange(n, dtype=float)
    sig = np.exp(-t / 120.0) * np.exp(2j * np.pi * 0.11 * t)
    fid = np.tile(sig, (n_traces, 1))
    fid *= rng.uniform(0.5, 2.0, (n_traces, 1))
    fid += rng.normal(0.0, 0.02, (n_traces, n))
    fid += 1j * rng.normal(0.0, 0.02, (n_traces, n))
    return fid


def test_optimize_direct_window_picks_best_candidate() -> None:
    """Every candidate is scored, the best one is the highest score; the returned structure matches
    the configuration.
    """
    res = optimize_direct_window(_synth_fid(), sw=20000.0)
    assert isinstance(res, WindowOptimizeResult)
    assert res.choice in DEFAULT_CANDIDATES
    assert len(res.scores) == len(DEFAULT_CANDIDATES)
    assert res.optimal_label
    selected = [s for s in res.scores if s["selected"]]
    assert len(selected) == 1
    max_score = max(s["score"] for s in res.scores)
    assert selected[0]["score"] == max_score
    assert selected[0]["cfg"] == res.choice
    assert all(s["cfg"] in DEFAULT_CANDIDATES for s in res.scores)
    assert any(res.logs)


def test_optimize_direct_window_changed_flag() -> None:
    """changed=False when the optimum matches the current configuration, which avoids a pointless
    write-back.
    """
    fid = _synth_fid()
    res = optimize_direct_window(fid)
    again = optimize_direct_window(fid, current=res.choice)
    assert again.changed is False
    assert again.choice == res.choice

    assert optimize_direct_window(fid, current={}).changed is True


def test_resolution_factor_is_continuous_and_has_an_explicit_tradeoff() -> None:
    from workflow.window_optimize import _resolution_score

    ratios = np.linspace(1.0, 3.0, 101)
    factors = [_resolution_score(float(r), 2.0) for r in ratios]
    assert factors == pytest.approx(ratios ** -2)
    assert all(0 < b < a <= 1 for a, b in zip(factors, factors[1:]))
    # No discontinuity at either former width gate.
    for boundary in (1.15, 1.25):
        assert abs(_resolution_score(boundary - 1e-8, 2.0)
                   - _resolution_score(boundary + 1e-8, 2.0)) < 1e-7
    # 20% extra width requires 44% better non-resolution quality to break even.
    assert 1.44 * _resolution_score(1.2, 2.0) == pytest.approx(1.0)
    assert _resolution_score(1.5, 0.0) == 1.0


def test_broader_window_keeps_scores_and_can_compensate_for_poor_narrow_quality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import workflow.window_optimize as windows

    # Control only measured quality to isolate the actual candidate selection.
    # Equal signal, better narrow width wins; sufficiently better signal/shape
    # allows the broader candidate to win, including beyond the former gate.
    candidates = [{"type": "none"}, {"type": "exp", "lb": 10.0}]
    for broad_raw, expected in ((10.0, 0), (25.0, 1)):
        observations = iter((
            {"fwhm": 4.0, "snr": 20.0, "shape": .5, "score": 10.0,
             "det_mean": 20.0, "n_ref": 2.0, "resolved": 2.0,
             "separation_score": 1.0, "symmetry_score": 1.0, "sidelobe_score": .5},
            {"fwhm": 6.0, "snr": 25.0, "shape": broad_raw / 25, "score": broad_raw,
             "det_mean": 25.0, "n_ref": 2.0, "resolved": 2.0,
             "separation_score": 1.0, "symmetry_score": 1.0,
             "sidelobe_score": broad_raw / 25},
        ))
        monkeypatch.setattr(windows, "_aggregate", lambda *a: next(observations))
        result = windows.optimize_direct_window(_synth_fid(), candidates=candidates, sw=20000)
        assert result.choice == candidates[expected]
        broad = result.scores[1]
        assert broad["width_ratio"] == 1.5
        assert broad["resolution_reference_fwhm"] == 4.0
        assert broad["resolution_weight"] == 2.0
        assert broad["resolution_score"] == pytest.approx(4 / 9)
        assert broad["score"] == pytest.approx(broad_raw * 4 / 9)
        assert broad["score"] > 0 and broad["status"] == "scored"
        assert broad["reason"] == ""


def test_real_fid_exports_nonwinning_broad_candidate_components() -> None:
    result = optimize_direct_window(
        _synth_fid(), candidates=[{"type": "none"}, {"type": "exp", "lb": 80.0}],
        sw=20000.0,
    )
    broad = result.scores[1]
    assert broad["width_ratio"] > 1.25
    assert broad["raw_score"] > 0 and broad["score"] > 0
    assert broad["status"] == "scored" and not broad["selected"]
    for row in result.scores:
        assert row["score"] == pytest.approx(row["raw_score"] * row["resolution_score"])
        assert 0 < row["detection_score"] <= 30
        for field in ("separation_score", "symmetry_score", "sidelobe_score"):
            assert 0 <= row[field] <= 1


@pytest.mark.parametrize("weight", [-1, float("nan"), float("inf")])
def test_invalid_resolution_weight_is_rejected(weight: float) -> None:
    from workflow.window_optimize import optimize_axis_window

    with pytest.raises(ValueError, match="resolution_penalty"):
        optimize_axis_window(_synth_fid(), -1, resolution_penalty=weight)


def test_optimize_direct_window_no_signal_skips_gracefully() -> None:
    'A signal-free FID raises nothing and returns keep-current.'
    res = optimize_direct_window(np.zeros((8, 256), dtype=complex))
    assert res.changed is False
    assert any("跳过" in log for log in res.logs)
    assert res.scores and all(s["reason"] == "no_valid_signal" for s in res.scores)
    assert not any(s["selected"] for s in res.scores)


def test_optimize_direct_window_noise_resolution_trend() -> None:
    """Resolution trend: no window (rectangular) has the narrowest main lobe, so FWHM must not
    exceed 1.5x that of the SP candidates.
    """
    res = optimize_direct_window(_synth_fid())
    fwhm_by_label = {s["label"]: s["fwhm"] for s in res.scores}
    none_fwhm = fwhm_by_label["无窗(线性)"]
    sp_fwhms = [
        v for k, v in fwhm_by_label.items() if k.startswith("SP ")
    ]
    assert sp_fwhms
    assert none_fwhm <= max(sp_fwhms) * 1.5


def test_optimize_direct_window_from_work_missing_fid(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """Skipped when the work directory has no converted .fid, without blocking the automatic
    path.
    """
    from core.data.bruker_reader import read_dataset

    exp = read_dataset(bruker_dir / "nus_3d")
    res = optimize_direct_window_from_work(tmp_path, exp)
    assert res.changed is False
    assert any("跳过" in log for log in res.logs)


def test_window_line_explicit_none_and_render(
    bruker_dir: Path,
) -> None:
    """With type=none the direct dimension still gets a fixed SP (a SMILE requirement); an explicit
    SP parameter takes effect.
    """
    from backend.script_generator import (
        _window_line,
        generate_3d_nus_script,
    )
    from core.data.bruker_reader import read_dataset

    assert _window_line({"type": "none"}) is None
    exp = read_dataset(bruker_dir / "nus_3d")
    base = dict(in_file="e.fid", nuslist="nuslist", out_file="e.ft3",
                nuslist_count=4)
    default = generate_3d_nus_script(exp, **base)
    assert "| nmrPipe -fn SP -off 0.45 -end 0.98 -pow 2 -c 0.5" in default
    none_script = generate_3d_nus_script(
        exp, window={"F3": {"type": "none"}}, **base
    )

    assert "| nmrPipe -fn SP -off 0.45 -end 0.98 -pow 2 -c 0.5" in none_script
    custom = generate_3d_nus_script(
        exp,
        window={"F3": {"type": "sine_bell", "off": 0.30, "end": 0.98,
                       "pow": 2, "c": 0.5}},
        **base,
    )
    assert "| nmrPipe -fn SP -off 0.3 -end 0.98 -pow 2 -c 0.5" in custom


def test_window_candidates_include_none() -> None:
    """Both the direct and indirect candidate pools must contain no window (no window is a correctly
    optimisable target, 0.2.190).
    """
    assert {"type": "none"} in DEFAULT_CANDIDATES
    assert {"type": "none"} in INDIRECT_CANDIDATES

    assert (
        {"type": "sine_bell", "off": 0.50, "end": 0.98, "pow": 2, "c": 0.5}
        in DEFAULT_CANDIDATES
    )


def test_indirect_windows_selects_none_for_decayed_fid() -> None:
    """Indirect-dimension naturally decaying FID: the optimiser must correctly select no window
    (0.2.190).

    The resolution-limited indirect-dimension score carries a resolution-retention factor -- when
    apodisation only broadens the peak, no window wins; when the truncation artefact is obvious, a
    mild window is still chosen.
    """
    rng = np.random.default_rng(3)
    n_f1, n_f2 = 64, 256
    k0 = np.arange(n_f2, dtype=float)
    t1 = np.arange(n_f1, dtype=float)
    direct = 1.0 / (1.0 + 1j * (k0 - n_f2 * 0.35) / 1.5)
    fid1 = np.exp(-t1 / 25.0) * np.exp(2j * np.pi * 0.13 * t1)
    planes = np.outer(direct, fid1)
    planes += rng.normal(0.0, 0.02, planes.shape)
    planes += 1j * rng.normal(0.0, 0.02, planes.shape)
    res = optimize_indirect_windows(planes, {"F1": 1})
    assert res.per_axis["F1"].choice.get("type") == "none"
    assert res.changed is True


def test_indirect_windows_picks_window_for_truncated_fid() -> None:
    """Indirect-dimension truncated FID: no window has the narrowest main lobe but rings, so the
    score should pick a mild window instead of no window.
    """
    rng = np.random.default_rng(4)
    n_f1, n_f2 = 64, 256
    k0 = np.arange(n_f2, dtype=float)
    t1 = np.arange(n_f1, dtype=float)
    direct = 1.0 / (1.0 + 1j * (k0 - n_f2 * 0.35) / 1.5)
    fid1 = np.exp(-t1 / 1000.0) * np.exp(2j * np.pi * 0.13 * t1)
    planes = np.outer(direct, fid1)
    planes += rng.normal(0.0, 0.02, planes.shape)
    planes += 1j * rng.normal(0.0, 0.02, planes.shape)
    res = optimize_indirect_windows(planes, {"F1": 1})
    assert res.per_axis["F1"].choice.get("type") != "none"


def test_indirect_windows_missing_recon_skips(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """Indirect-dimension window optimisation is skipped when the work directory has no SMILE
    reconstructed plane, without blocking.
    """
    from core.data.bruker_reader import read_dataset

    exp = read_dataset(bruker_dir / "nus_3d")
    res = optimize_indirect_windows_from_recon(tmp_path, exp)
    assert res.changed is False
    assert any("跳过" in log for log in res.logs)


def test_indirect_windows_missing_fid_skips(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """Uniform indirect-dimension window optimisation is skipped when the work directory has no
    converted fid, without blocking.
    """
    from core.data.bruker_reader import read_dataset

    exp = read_dataset(bruker_dir / "hsqc_2d")
    res = optimize_indirect_windows_from_work(tmp_path, exp)
    assert res.changed is False
    assert any("跳过" in log for log in res.logs)


def test_gm_em_default_pools_require_sw() -> None:
    """Two GM and two EM choices per axis, with real SW and width scoring."""
    gm = {"type": "gaussian", "g1": 8.0, "g2": 15.0, "g3": 0.0, "c": 1.0}
    assert gm in DEFAULT_CANDIDATES
    for pool in (DEFAULT_CANDIDATES, INDIRECT_CANDIDATES):
        assert len(pool) == 10
        assert [(c["g1"], c["g2"]) for c in pool if c["type"] == "gaussian"] == [
            (8.0, 15.0), (4.0, 8.0),
        ]
        assert [c["lb"] for c in pool if c["type"] == "exp"] == [3.0, 5.0]

    fid = _synth_fid()
    no_sw = optimize_direct_window(fid)
    assert not any("GM" in s["label"] for s in no_sw.scores)
    assert {"type": "gaussian", "g1": 8.0, "g2": 15.0, "g3": 0.0, "c": 1.0} in (
        no_sw.skipped_candidates
    )
    with_sw = optimize_direct_window(fid, sw=20000.0)
    gm_scores = [s for s in with_sw.scores if "GM" in s["label"]]
    assert len(gm_scores) == 2
    assert all(s["fwhm"] < 200.0 for s in gm_scores)
    assert len([s for s in with_sw.scores if "EM" in s["label"]]) == 2
    indirect = optimize_indirect_windows(fid.T, {"F1": 0}, sw_map={"F1": 20000.0})
    assert len(indirect.per_axis["F1"].scores) == 10
