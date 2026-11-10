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
    factors = [_resolution_score(float(r), 0.25) for r in ratios]
    assert factors == pytest.approx(ratios ** -0.25)
    assert all(0 < b < a <= 1 for a, b in zip(factors, factors[1:]))
    # No discontinuity at either former width gate.
    for boundary in (1.15, 1.25):
        assert abs(_resolution_score(boundary - 1e-8, 0.25)
                   - _resolution_score(boundary + 1e-8, 0.25)) < 1e-7
    # A 5% quality gain compensates for 20% extra width.
    assert 1.05 * _resolution_score(1.2, 0.25) > 1.0
    assert _resolution_score(1.5, 0.0) == 1.0


def test_broader_window_keeps_scores_and_can_compensate_for_poor_narrow_quality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import workflow.window_optimize as windows

    # Control only measured quality to isolate the actual candidate selection.
    # Equal signal, better narrow width wins; sufficiently better signal/shape
    # allows the broader candidate to win, including beyond the former gate.
    candidates = [{"type": "none"}, {"type": "exp", "lb": 10.0}]
    for broad_raw, expected in ((10.0, 0), (12.0, 1)):
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
        assert broad["resolution_weight"] == 0.25
        assert broad["resolution_score"] == pytest.approx(1.5 ** -0.25)
        assert broad["score"] == pytest.approx(broad_raw * 1.5 ** -0.25)
        assert broad["score"] > 0 and broad["status"] == "scored"
        assert broad["reason"] == ""


@pytest.mark.parametrize("indirect", [False, True])
@pytest.mark.parametrize(
    ("unwindowed_score", "selected_type"), [(11.0, "exp"), (13.0, "exp"), (1000.0, "exp")],
)
def test_automatic_selection_keeps_window_despite_unwindowed_score(
    monkeypatch: pytest.MonkeyPatch, indirect: bool, unwindowed_score: float, selected_type: str,
) -> None:
    import workflow.window_optimize as windows

    pool = [{"type": "none"}, {"type": "exp", "lb": 5.0}]
    monkeypatch.setattr(windows, "DEFAULT_CANDIDATES", pool)
    monkeypatch.setattr(windows, "INDIRECT_CANDIDATES", pool)
    scores = iter((unwindowed_score, 10.0))
    monkeypatch.setattr(windows, "_aggregate", lambda *args: {
        "fwhm": 4.0, "snr": 20.0, "shape": 1.0, "score": next(scores),
        "det_mean": 20.0, "n_ref": 2.0, "resolved": 2.0,
        "separation_score": 1.0, "symmetry_score": 1.0, "sidelobe_score": 1.0,
    })
    fid = _synth_fid()
    if indirect:
        result = windows.optimize_indirect_windows(
            fid, {"F1": 1}, sw_map={"F1": 20000.0},
        ).per_axis["F1"]
    else:
        result = windows.optimize_direct_window(fid, sw=20000.0)

    if indirect:
        selected_type = "exp"
    assert result.choice["type"] == selected_type
    assert result.scores[0]["score"] == unwindowed_score
    assert result.scores[0]["reason"] == (
        "automatic_requires_window"
    )


@pytest.mark.parametrize(("unwindowed_valley", "windowed_valley", "selected_type"), [
    (0.35, 0.40, "sine_bell"),
    (0.74, 0.80, "sine_bell"),
    (0.15, 0.40, "sine_bell"),
])
def test_direct_valley_refinement_keeps_window_despite_unwindowed_valley(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    unwindowed_valley: float, windowed_valley: float, selected_type: str,
) -> None:
    import nmrglue as ng

    import workflow.window_optimize as windows

    header = {"FDDIMORDER": [2], "FDF2SW": 2000.0, "FDF2OBS": 600.0}
    monkeypatch.setattr(ng.pipe, "read", lambda path: (header, np.ones((1, 32), dtype=complex)))
    monkeypatch.setattr(windows, "robust_noise_sigma", lambda trace: 1.0)
    monkeypatch.setattr(windows, "_window_vector", lambda cfg, n, sw: np.ones(n))
    monkeypatch.setattr(windows, "_reference_peaks", lambda *args, **kwargs: [
        (10, 10.0, 4.0), (16, 10.0, 4.0),
    ])
    valleys = iter((0.5, unwindowed_valley, windowed_valley, *([windowed_valley] * 3)))
    monkeypatch.setattr(windows, "_valley_fraction", lambda *args: next(valleys))
    window = windows.DEFAULT_CANDIDATES[0]
    result = WindowOptimizeResult(choice=window, changed=True, scores=[
        {"cfg": {"type": "none"}, "status": "scored"}, {"cfg": window, "status": "scored"},
    ])

    refined = windows.refine_direct_window(
        result, tmp_path / "preview.ft2", phase=(0.0, 0.0), zf_size=32,
        ppm_range=None, current=None,
    )

    assert refined.choice["type"] == selected_type
    assert refined.sampling["score_profile"] == "direct_peak_valley"
    assert refined.scores[0]["reason"] == (
        "automatic_requires_window"
    )


def test_real_fid_exports_nonwinning_broad_candidate_components() -> None:
    result = optimize_direct_window(
        _synth_fid(), candidates=[{"type": "none"}, {"type": "exp", "lb": 80.0}],
        sw=20000.0,
    )
    broad = result.scores[1]
    assert broad["width_ratio"] > 1.25
    assert broad["raw_score"] > 0 and broad["score"] > 0
    assert broad["status"] == "scored" and not broad["selected"]
    assert max(row["detection_score"] for row in result.scores) > 60
    for row in result.scores:
        assert row["score"] == pytest.approx(row["raw_score"] * row["resolution_score"])
        assert 0 < row["detection_score"] <= row["snr"]
        for field in ("separation_score", "symmetry_score", "sidelobe_score"):
            assert 0 <= row[field] <= 1


def test_auto_window_rewards_snr_gains_above_the_previous_cap() -> None:
    rng = np.random.default_rng(23)
    t = np.arange(64)
    fid = rng.uniform(0.5, 2.0, (16, 1)) * np.exp(-t / 12.8 + 2j * np.pi * 0.137 * t)
    fid += 0.025 * (rng.normal(size=fid.shape) + 1j * rng.normal(size=fid.shape))

    result = optimize_direct_window(fid, sw=2000.0)
    unwindowed = next(row for row in result.scores if row["cfg"]["type"] == "none")
    selected = next(row for row in result.scores if row["selected"])
    assert selected["cfg"]["type"] != "none"
    assert selected["detection_score"] > unwindowed["detection_score"] > 60
    assert selected["score"] > unwindowed["score"]


@pytest.mark.parametrize(("n", "sw", "decay", "expected"), [
    (128, 4000.0, 6.4, {"type": "sine_bell", "off": 0.65, "end": 1.0, "pow": 2, "c": 0.5}),
    (512, 10000.0, 25.6, {"type": "exp", "lb": 20.0, "c": 1.0}),
])
def test_auto_window_can_select_stronger_default_candidates(n, sw, decay, expected) -> None:
    rng = np.random.default_rng(19)
    t = np.arange(n)
    fid = rng.uniform(0.5, 2.0, (16, 1)) * np.exp(-t / decay + 2j * np.pi * 0.11 * t)
    fid += 0.15 * (rng.normal(size=fid.shape) + 1j * rng.normal(size=fid.shape))
    assert optimize_direct_window(fid, sw=sw).choice == expected


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


def test_indirect_windows_keeps_window_for_small_unwindowed_gain() -> None:
    rng = np.random.default_rng(3)
    rng = np.random.default_rng(3)
    n_f1, n_f2 = 64, 256
    k0 = np.arange(n_f2, dtype=float)
    t1 = np.arange(n_f1, dtype=float)
    direct = 1.0 / (1.0 + 1j * (k0 - n_f2 * 0.35) / 1.5)
    fid1 = np.exp(-t1 / 25.0) * np.exp(2j * np.pi * 0.13 * t1)
    planes = np.outer(direct, fid1)
    planes += rng.normal(0.0, 0.002, planes.shape)
    planes += 1j * rng.normal(0.0, 0.002, planes.shape)
    res = optimize_indirect_windows(planes, {"F1": 1})
    axis = res.per_axis["F1"]
    unwindowed = next(row for row in axis.scores if row["cfg"]["type"] == "none")
    selected = next(row for row in axis.scores if row["selected"])
    assert axis.choice["type"] == "sine_bell"
    assert 1.0 <= unwindowed["score"] / selected["score"] < 1.25
    assert unwindowed["reason"] == "automatic_requires_window"
    assert res.changed is True


def test_indirect_3d_default_windows_and_explicit_none() -> None:
    t = np.arange(32)
    signal = np.exp(-t / 20) * np.exp(2j * np.pi * .2 * t)
    fid = signal[:, None, None] * signal[None, :, None] * np.ones((1, 1, 8))
    automatic = optimize_indirect_windows(fid, {"F1": 0, "F2": 1})
    assert set(automatic.per_axis) == {"F1", "F2"}
    assert all(axis.choice["type"] != "none" for axis in automatic.per_axis.values())
    explicit = optimize_indirect_windows(
        fid, {"F1": 0, "F2": 1}, candidates=[{"type": "none"}], strict_candidates=True,
    )
    assert all(axis.choice == {"type": "none"} for axis in explicit.per_axis.values())


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


def test_indirect_scoring_rewards_lower_sidelobes_and_deeper_valleys() -> None:
    from workflow.window_optimize import _measure_trace

    refs = [(35, 24.0, 4.0), (45, 20.0, 4.0)]
    pairs = [(35, 45)]
    connected = np.ones(96)
    connected[[35, 45]] = (24, 20)
    connected[36:45] = 8
    connected[25] = 8
    clean = connected.copy()
    clean[36:45] = 2
    clean[25] = 2
    before = _measure_trace(connected, refs, resolved_pairs=pairs, indirect=True)
    after = _measure_trace(clean, refs, resolved_pairs=pairs, indirect=True)
    assert after["sidelobe_score"] > before["sidelobe_score"]
    assert after["separation_score"] > before["separation_score"]
    assert after["score"] > before["score"]
    clean[36:45] = 14
    merged = _measure_trace(clean, refs, resolved_pairs=pairs, indirect=True)
    assert merged["score"] == 0.0


def test_uniform_f1_uses_complex_points_after_direct_projection(bruker_dir: Path) -> None:
    from core.data.bruker_reader import read_dataset
    from workflow.window_optimize import _uniform_2d_indirect_traces

    experiment = read_dataset(bruker_dir / "hsqc_2d")
    f1 = np.exp(2j * np.pi * 0.13 * np.arange(24))
    fid = np.zeros((50, 32), dtype=np.complex64)
    fid[:48:2] = f1.real[:, None]
    fid[1:48:2] = f1.imag[:, None]
    header = {"FDF1QUADFLAG": 0, "FDF1TDSIZE": 24}
    traces = _uniform_2d_indirect_traces(
        fid, header, experiment, direct_window=None, direct_phase=(0.0, 0.0), direct_range=None,
    )
    assert traces.shape[0] == 24
    center = traces.shape[1] // 2
    np.testing.assert_allclose(traces[:, center] / traces[0, center], f1, atol=1e-6)


@pytest.mark.parametrize("ndim", [2, 3])
def test_indirect_phased_preview_preserves_a_pair_off_the_strongest_trace(ndim: int) -> None:
    from workflow.window_optimize import WindowOptimizeResult, refine_indirect_window

    t = np.arange(90)
    positions = np.arange(80)[:, None]
    strongest = 10 * np.exp(-((positions - 10) / 2) ** 2)
    crowded = np.exp(-((positions - 57) / 2) ** 2)

    def tone(k: int) -> np.ndarray:
        return np.exp(2j * np.pi * k * t / len(t) - .02 * t)

    def preview(fid: np.ndarray) -> np.ndarray:
        spectrum = np.fft.fftshift(np.fft.ifft(fid, axis=-1), axes=-1)
        return spectrum.T[:, :, None] if ndim == 3 else spectrum

    sp = {"type": "sine_bell", "off": .65, "end": 1., "pow": 2, "c": .5}
    gm = {"type": "gaussian", "g1": 4., "g2": 8., "c": 1.}
    em = {"type": "exp", "lb": 3., "c": 1.}
    initial = WindowOptimizeResult(choice=sp, changed=True, status="scored", scores=[
        {"cfg": cfg, "label": label, "status": "scored", "score": score}
        for cfg, label, score in [(sp, "SP", .71), (gm, "GM", .55), (em, "EM", .48)]
    ])
    options = {"axis": 0 if ndim == 3 else 1, "phase": (0., 0.), "sw": 2187., "current": None}
    separated = refine_indirect_window(
        initial, preview(strongest * tone(18) + crowded * (tone(8) + .75 * tone(9))), **options,
    )
    assert separated.choice == gm
    assert separated.sampling["pair_count"] == 1
    single = refine_indirect_window(initial, preview(strongest * tone(18)), **options)
    assert single is initial


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
    'Two GM and two EM choices per axis, with real SW and width scoring.'
    gm = {"type": "gaussian", "g1": 8.0, "g2": 15.0, "g3": 0.0, "c": 1.0}
    assert gm in DEFAULT_CANDIDATES
    for pool in (DEFAULT_CANDIDATES, INDIRECT_CANDIDATES):
        assert len(pool) == 13
        assert {"type": "sine_bell", "off": 0.65, "end": 1.0, "pow": 2, "c": 0.5} in pool
        assert [(c["g1"], c["g2"]) for c in pool if c["type"] == "gaussian"] == [
            (8.0, 15.0), (4.0, 8.0),
        ]
        assert [c["lb"] for c in pool if c["type"] == "exp"] == [3.0, 5.0, 10.0, 20.0]

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
    assert len([s for s in with_sw.scores if "EM" in s["label"]]) == 4
    indirect = optimize_indirect_windows(fid.T, {"F1": 0}, sw_map={"F1": 20000.0})
    assert len(indirect.per_axis["F1"].scores) == 13
