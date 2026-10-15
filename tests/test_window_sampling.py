"""Bounded signal sampling, shared targets, weak fallback and honest failures."""

from __future__ import annotations

import numpy as np
import pytest

from workflow import window_optimize as win
from workflow.optimization_candidates import CandidateSelectionError
from workflow.truth_benchmark import synthetic_fid


def test_energy_leaders_do_not_hide_lower_energy_signal() -> None:
    rng = np.random.default_rng(71)
    fid, _ = synthetic_fid([{"offset": 82.4, "lw": 4}], n_points=256, n_traces=512)
    # High-energy broadband artifacts have no distinct reference peaks.
    fid[:12] = 20 * (rng.normal(size=(12, 256)) + 1j * rng.normal(size=(12, 256)))
    result = win.optimize_direct_window(fid, sw=15000.0)
    again = win.optimize_direct_window(fid, sw=15000.0)
    assert result.status == "scored"
    assert result.sampling == again.sampling
    assert result.sampling["sampling_reason"] == "stratified_rescue"
    assert result.sampling["reference_sigma"] == 12
    assert 12 < result.sampling["scanned_traces"] <= 256
    assert 1 <= result.sampling["used_traces"] <= 12
    assert all(i >= 12 for i in result.sampling["trace_indices"])


def test_weak_signal_uses_six_only_when_twelve_has_no_reference() -> None:
    fid, _ = synthetic_fid(
        [{"offset": 128.4, "amp": 0.6, "lw": 6}], n_points=512,
        n_traces=64, noise=0.2, seed=57,
    )
    result = win.optimize_direct_window(fid, sw=20000.0)
    assert result.status == "scored"
    assert result.sampling["qualified_12"] == 0
    assert result.sampling["reference_sigma"] == 6
    assert 6 < result.sampling["max_height_sigma"] < 12
    assert result.sampling["used_traces"] >= 3
    assert len([s for s in result.scores if s["selected"]]) == 1
    # A candidate's response need not independently exceed the reference gate.
    assert any(0 < s["snr"] < 12 and s["score"] > 0 for s in result.scores)


@pytest.mark.parametrize("seed", [1, 7, 8, 11, 13, 22])
def test_six_sigma_does_not_promote_independent_noise(seed: int) -> None:
    rng = np.random.default_rng(seed)
    fid = rng.normal(size=(256, 512)) + 1j * rng.normal(size=(256, 512))
    result = win.optimize_direct_window(fid, zf_size=1024, sw=20000.0)
    assert result.status == "skipped"
    assert result.sampling["used_traces"] == 0
    assert not any(s["selected"] for s in result.scores)


def test_isolated_six_sigma_spikes_do_not_become_references() -> None:
    rng = np.random.default_rng(99)
    amp = 1 + rng.uniform(-0.5, 0.5, (20, 256))
    amp[:, 70] = 4.0  # Below 12 sigma, above 6; an isolated frequency-bin spike.
    fid = np.fft.ifft(amp, axis=-1)
    result = win.optimize_direct_window(fid)
    assert result.sampling["qualified_12"] == 0
    assert result.sampling["used_traces"] == 0


def test_reference_anchors_do_not_require_candidate_redetection() -> None:
    rng = np.random.default_rng(13)
    amp = rng.uniform(0.5, 1.5, 256)
    amp[78:83] = [1.5, 2.0, 2.5, 2.0, 1.5]
    measured = win._measure_trace(amp, [(80, 15.0, 4.0)], resolved_pairs=[])
    assert measured["n_ref"] == 1 and measured["score"] > 0
    assert measured["snr"] < 12
    assert win._measure_trace(amp, [], resolved_pairs=[])["score"] == 0


def test_degraded_trace_is_kept_in_candidate_aggregation() -> None:
    amp = np.zeros(64)
    amp[20:25] = [1, 3, 8, 3, 1]
    refs = [[(22, 8.0, 2.0)]] * 2
    good = win._aggregate(np.stack([amp, amp]), refs, [[], []])
    degraded = win._aggregate(np.stack([amp, np.zeros(64)]), refs, [[], []])
    assert degraded["score"] == pytest.approx(good["score"] / 2)
    assert degraded["n_ref"] == good["n_ref"]


def test_preexisting_overlap_is_not_counted_as_window_merging() -> None:
    amp = np.zeros(128)
    amp[40:51] = [5, 6, 8, 10, 9, 8, 9, 10, 8, 6, 5]
    refs = [(43, 10.0, 10.0), (47, 10.0, 10.0)]
    assert win._resolved_pairs(refs, amp) == []
    measured = win._measure_trace(amp, refs, resolved_pairs=[])
    assert measured["resolved"] == measured["n_ref"] == 2
    assert measured["score"] > 0


def test_all_zero_scores_have_no_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    fid, _ = synthetic_fid([{"offset": 50, "lw": 4}], n_points=256)
    monkeypatch.setattr(win, "_shape_components", lambda *args: (0.0, 1.0))
    result = win.optimize_direct_window(fid, current={"type": "none"})
    assert result.status == "skipped" and not result.changed
    assert not any(s["selected"] for s in result.scores)
    assert any(s["reason"] == "zero_score" for s in result.scores)
    with pytest.raises(CandidateSelectionError):
        win.optimize_direct_window(fid, candidates=[{"type": "none"}], strict_candidates=True)
