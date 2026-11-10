"""Estimate residual first-order phase from isolated peaks across the spectrum."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.optimize import minimize_scalar
from scipy.signal import resample


def direct_p1_prior(acqus: dict, spectral_width_hz: float) -> float | None:
    """Estimate receiver-delay phase in the NMRPipe PS convention.

    DE is in microseconds. Bruker baseopt aligns acquisition to its declared
    time origin. GRPDLY is a separate correction performed during conversion.
    """
    try:
        digitizer = int(acqus["DIGMOD"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not np.isfinite(spectral_width_hz) or spectral_width_hz <= 0:
        return None
    if digitizer == 3:  # Bruker baseopt
        return 0.0
    try:
        dwell_fraction = float(acqus["DE"]) * 1e-6 * spectral_width_hz
    except (KeyError, TypeError, ValueError):
        return None
    if digitizer in (0, 1) and 0 <= dwell_fraction <= 1:
        return 360.0 * dwell_fraction
    return None


def fit_phase_slope(
    spectrum: np.ndarray, axis: int, *, p1_prior: float | None = None,
) -> tuple[float, float, int, float] | None:
    """Fit peak-centre phases modulo 180°, with equal weight per frequency band.

    Take isolated local maxima from each band of the complex preview. Peak
    curvature cancels a locally linear complex background. The fit can use
    peaks on different traces, so each trace need not contain both end peaks.
    """
    moved = np.moveaxis(spectrum, axis, -1)
    n = moved.shape[-1]
    if n < 16 or not np.iscomplexobj(moved):
        return None
    bands = []
    margin = max(2, n // 64)
    for indices in np.array_split(np.arange(margin, n - margin), 8):
        magnitude = np.abs(moved[..., indices[0]:indices[-1] + 1])
        profile = magnitude.max(axis=-1)
        region = np.flatnonzero((profile == maximum_filter(profile, size=5)) & (profile > 0))
        leaders = region[np.argsort(profile.flat[region])[-12:]]
        anchors = []
        for location in leaders:
            spatial = np.unravel_index(location, profile.shape)
            row = moved[spatial]
            k = int(indices[np.argmax(magnitude[spatial])])
            left, center, right = row[k - 1:k + 2]
            a, b, c = abs(left), abs(center), abs(right)
            if not (b > a and b > c and b > 0):
                continue
            noise = np.median(np.abs(np.diff(row, n=2)))
            curvature = 2 * center - left - right
            if abs(curvature) <= max(8 * noise, .05 * b):
                continue
            # Estimate the centre within the sampled bin. Pair the symmetric
            # parts of the line and reject jagged/ringing dominated maxima.
            offset = .5 * (a - c) / (a + c - 2 * b)
            if abs(offset) > .4 or min(a, c) < .15 * b:
                continue
            if abs(np.angle(left / center)) + abs(np.angle(right / center)) > 2.6:
                continue
            oversampled = resample(row, 8 * n)
            probe = np.arange(8 * k - 4, 8 * k + 5)
            apex = int(probe[np.argmax(abs(oversampled[probe]))])
            curvature = (2 * oversampled[apex]
                         - oversampled[apex - 8] - oversampled[apex + 8])
            anchors.append((apex / (8 * n), float(np.angle(curvature, deg=True))))
        if anchors:
            bands.append(np.asarray(anchors))
    if len(bands) < 3:
        return None
    positions, phases = np.concatenate(bands).T
    span = float(np.ptp([np.median(band[:, 0]) for band in bands]))
    if span < .20 or len(positions) < 4:
        return None
    weights = np.repeat([1 / len(band) for band in bands], [len(band) for band in bands])
    seed = 0.0 if p1_prior is None else p1_prior

    def evaluate(p1: float) -> tuple[float, float]:
        corrected = phases + p1 * positions
        mean = np.sum(weights * np.exp(2j * np.deg2rad(corrected)))
        pivot = np.angle(mean, deg=True) / 2
        residuals = np.abs((corrected - pivot + 90) % 180 - 90)
        # A clipped loss prevents an overlapping line from setting the slope.
        loss = np.average(np.minimum(residuals, 25.0) ** 2, weights=weights)
        return float(loss), float(-pivot)

    grid = seed + np.arange(-180., 181., 5.)
    best = int(np.argmin([evaluate(p)[0] for p in grid]))
    if best in (0, len(grid) - 1):
        return None
    fit = minimize_scalar(lambda p: evaluate(p)[0], method="bounded",
                          bounds=(grid[best - 1], grid[best + 1]))
    p1 = float(fit.x)
    loss, p0 = evaluate(p1)
    rms = loss ** .5
    if rms > 10 or evaluate(0.0)[0] ** .5 - rms < 1.5:
        return None
    return p0, p1, len(positions), span
