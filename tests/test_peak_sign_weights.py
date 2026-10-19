"""Regression coverage for sign selection in peak detection."""

from __future__ import annotations

import numpy as np
import pytest

from core.qc.peak_detection import (
    Peak,
    PeakDetectionParams,
    detect,
    keep_dominant,
)


@pytest.mark.parametrize("shape", [(72, 80), (28, 36, 40)])
def test_dominant_uses_squared_snr_instead_of_candidate_count(shape: tuple[int, ...]) -> None:
    """A few strong positives outweigh numerous weak negative candidates."""
    rng = np.random.default_rng(218)
    spectrum = rng.normal(0.0, 1.0, shape)
    positions = [tuple(6 + (i * 7 + axis * 11) % (shape[axis] - 12)
                       for axis in range(len(shape))) for i in range(24)]
    for position in positions:
        spectrum[position] = -5.0
    spectrum[tuple(3 + axis * 2 for axis in range(len(shape)))] = 35.0
    spectrum[tuple(shape[axis] - 4 - axis for axis in range(len(shape)))] = 30.0

    peaks = detect(
        spectrum,
        PeakDetectionParams(sigma_multiplier=0.5, min_snr=2.0, sign_mode="dominant"),
    )

    assert sum(peak.height > 25.0 for peak in peaks) == 2
    assert all(peak.height > 0 for peak in peaks)


@pytest.mark.parametrize("shape", [(72, 80), (28, 36, 40)])
def test_dominant_detects_global_sign_inversion(shape: tuple[int, ...]) -> None:
    spectrum = np.zeros(shape, dtype=float)
    spectrum[tuple(5 + axis * 2 for axis in range(len(shape)))] = 35.0
    spectrum[tuple(shape[axis] - 5 - axis for axis in range(len(shape)))] = 30.0
    spectrum = -spectrum

    peaks = detect(spectrum, PeakDetectionParams(sign_mode="dominant"))

    assert len(peaks) == 2
    assert all(peak.height < 0 for peak in peaks)


def test_keep_dominant_prefers_positive_on_exact_weight_tie() -> None:
    peaks = [
        Peak(height=8.0, snr=8.0),
        Peak(height=-8.0, snr=8.0),
    ]
    assert keep_dominant(peaks) == [peaks[0]]


@pytest.mark.parametrize(
    "mode,expected", [("both", {-1, 1}), ("positive", {1}), ("negative", {-1})]
)
def test_explicit_sign_modes_keep_their_requested_behavior(
    mode: str, expected: set[int]
) -> None:
    spectrum = np.zeros((40, 48), dtype=float)
    spectrum[8, 9] = 20.0
    spectrum[30, 37] = -18.0

    peaks = detect(spectrum, PeakDetectionParams(sign_mode=mode))

    assert {1 if peak.height > 0 else -1 for peak in peaks} == expected


def test_dominant_result_is_invariant_to_candidate_order() -> None:
    peaks = [Peak(height=7.0, snr=7.0), Peak(height=-12.0, snr=12.0)]
    shuffled = [peaks[1], peaks[0]]
    assert keep_dominant(peaks) == keep_dominant(shuffled) == [peaks[1]]


def test_weak_many_negative_candidates_do_not_imply_mixed() -> None:
    from workflow.pick_peaks import strong_two_sign_evidence

    peaks = [Peak(height=value, snr=value) for value in (30.0, 25.0, 20.0)]
    peaks.extend(Peak(height=-2.0, snr=2.0) for _ in range(12))
    assert not strong_two_sign_evidence(peaks)


def test_balanced_repeated_sign_evidence_still_implies_mixed() -> None:
    from workflow.pick_peaks import strong_two_sign_evidence

    peaks = [Peak(height=value, snr=value) for value in (14.0, 12.0, 10.0)]
    peaks.extend(Peak(height=-value, snr=value) for value in (13.0, 11.0, 9.0))
    assert strong_two_sign_evidence(peaks)


def test_snr_is_used_even_when_heights_suggest_the_opposite_sign() -> None:
    peaks = [Peak(height=2.0, snr=40.0), Peak(height=-20.0, snr=4.0)]
    assert keep_dominant(peaks) == [peaks[0]]


@pytest.mark.parametrize("invalid_snr", [0.0, float("nan"), float("inf")])
def test_missing_legacy_snr_uses_common_height_scale(invalid_snr: float) -> None:
    peaks = [Peak(height=20.0, snr=invalid_snr), Peak(height=-4.0, snr=1000.0)]
    assert keep_dominant(peaks) == [peaks[0]]


def test_extreme_finite_snr_does_not_overflow() -> None:
    peaks = [Peak(height=10.0, snr=1e300), Peak(height=-5.0, snr=5e299)]
    assert keep_dominant(peaks) == [peaks[0]]
