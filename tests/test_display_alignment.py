"""Whole-table calibration for display and aligned peak-table export."""

from copy import deepcopy

import numpy as np
import pytest

from workflow.display_alignment import estimate_display_alignment


@pytest.mark.parametrize("shift", [(0.12, -0.75), (-0.095, 1.25), (0.0, 0.0)])
def test_hn_scan_recovers_known_translation_with_extra_peaks(shift):
    rng = np.random.default_rng(7)
    points = rng.uniform([6.5, 100.0], [10.0, 135.0], (30, 2))
    cur = [{"H_shift": h, "N_shift": n} for h, n in points]
    ref = [{"H_shift": h + shift[0], "N_shift": n + shift[1]} for h, n in points]
    cur.extend([{"H_shift": 6.0, "N_shift": 90.0}])
    before = deepcopy((cur, ref))
    result = estimate_display_alignment(cur, ref)
    assert result["shift"] == pytest.approx({"1H": shift[0], "15N": shift[1]}, abs=1e-8)
    assert result["matched"] == len(ref)
    assert (cur, ref) == before


def test_3d_same_nuclei_keep_independent_axis_offsets():
    rng = np.random.default_rng(11)
    points = rng.uniform([100, 100, 6], [130, 130, 10], (12, 3))
    delta = [0.45, -0.65, 0.085]
    cur = [{f"F{i+1}_shift": p[i] for i in range(3)} for p in points]
    ref = [{f"F{i+1}_shift": p[i] + delta[i] for i in range(3)} for p in points]
    result = estimate_display_alignment(cur, ref, cur_nuclei=["15N", "15N", "1H"],
                                        ref_nuclei=["15N", "15N", "1H"])
    assert result["axis_shifts"] == pytest.approx(dict(enumerate(delta)), abs=1e-8)


def test_2d_reference_leaves_unobserved_3d_axis_unchanged():
    cur = [{"F1_shift": n, "F2_shift": c, "F3_shift": h}
           for n, c, h in [(115., 45., 8.), (123., 55., 7.), (110., 60., 9.)]]
    ref = [{"N_shift": p["F1_shift"] + .5, "H_shift": p["F3_shift"] - .1} for p in cur]
    result = estimate_display_alignment(cur, ref, cur_nuclei=["15N", "13C", "1H"])
    assert result["axis_shifts"] == pytest.approx({0: .5, 1: 0., 2: -.1})


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_invalid_coordinates_are_rejected(bad):
    with pytest.raises(ValueError):
        estimate_display_alignment([{"H_shift": bad}], [{"H_shift": 8.}])


def test_no_overlap_is_rejected_instead_of_returning_a_display_shift():
    with pytest.raises(ValueError):
        estimate_display_alignment([{"H_shift": 1., "N_shift": 100.}],
                                   [{"H_shift": 8., "N_shift": 120.}])
