"""Display-only calibration using a coarse/fine minimum-median-distance search.

The offset is reference minus detected. GUI import and aligned export share
this estimator; peak picking keeps its existing calculations. Hydrogen and
heavy-nucleus coordinates use distinct weights and search grids, retaining
repeated-nucleus axis identities.
"""

from __future__ import annotations

from itertools import product

import numpy as np
from scipy.spatial import cKDTree

from ui_support.i18n import tr
from workflow.peak_align import (
    _coord_matrix,
    common_nuclei,
    coordinate_key,
    coordinate_nucleus,
    row_coords,
)


def estimate_display_alignment(
    detected: list[dict], reference: list[dict], *,
    cur_nuclei: list[str] | None = None, ref_nuclei: list[str] | None = None,
) -> dict:
    """Find the additive ppm offset without changing either input peak table."""
    cur = [row_coords(row, cur_nuclei) for row in detected]
    ref = [row_coords(row, ref_nuclei) for row in reference]
    nuclei = common_nuclei(cur, ref)
    if not nuclei:
        raise ValueError(tr("The peak tables have no common coordinate axes"))
    current, expected = _coord_matrix(cur, nuclei), _coord_matrix(ref, nuclei)
    if not len(current) or not len(expected):
        raise ValueError(tr("The peak tables have no complete coordinates for alignment"))
    hydrogen = np.array([coordinate_nucleus(n) == "1H" for n in nuclei])
    weights = np.where(hydrogen, 1.0, 0.2)
    ranges = np.where(hydrogen, 0.3, 3.0)
    coarse = np.where(hydrogen, 0.02, 0.2)
    fine = np.where(hydrogen, 0.005, 0.05)
    tolerance = np.where(hydrogen, 0.05, 0.5)
    tree = cKDTree(current * weights)

    def score(shift):
        distances = tree.query((expected - shift) * weights)[0]
        median = float(np.median(distances))
        # This is the source project's secondary criterion, not a one-to-one
        # assignment count. Only candidates tying the best median need it.
        delta = np.abs(expected[:, None, :] - (current + shift)[None, :, :])
        matched = int(np.all(delta <= tolerance, axis=2).any(axis=1).sum())
        return median, -matched

    def scan(grids):
        best_shift, best_score = None, (float("inf"), 0)
        for values in product(*grids):
            shift = np.asarray(values)
            # KDTree avoids allocating all pairwise distances for each grid point.
            median = float(np.median(tree.query((expected - shift) * weights)[0]))
            if median <= best_score[0]:
                candidate = score(shift)
                if candidate < best_score:
                    best_shift, best_score = shift, candidate
        return best_shift, best_score

    rough, _ = scan([
        np.round(np.arange(-r, r + step / 2, step), 6)
        for r, step in zip(ranges, coarse)
    ])
    shift, result = scan([
        np.round(np.arange(center - 2 * step, center + 2 * step + small / 2, small), 6)
        for center, step, small in zip(rough, coarse, fine)
    ])
    if -result[1] == 0:
        raise ValueError(tr("No peaks match after alignment; check the imported peak table"))
    offsets = dict(zip(nuclei, map(float, shift)))
    axes = cur_nuclei or ["15N", "1H"]
    return {"shift": offsets,
            "axis_shifts": {i: offsets.get(coordinate_key(axes, i), 0.0)
                            for i in range(len(axes))},
            "median_distance": result[0], "matched": -result[1],
            "n_detected": len(current), "n_reference": len(expected)}
