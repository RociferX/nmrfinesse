"""Physical-coordinate sampling and translation fitting for displayed spectra."""
from __future__ import annotations

import numpy as np

from ui_support.i18n import tr
from viewer.spectrum import _parse_nmrpipe_label


def spectrum_axes(spectrum):
    return [spectrum.axis] if spectrum.data.ndim == 1 else list(spectrum.axes)


def _axis_identity(label):
    """Separate the nucleus from a display role such as Nx/Ny, preserving unknown labels."""
    text = str(label).strip()
    if text[-1:].lower() in ('x', 'y', 'z'):
        nucleus = _parse_nmrpipe_label(text[:-1])
        if nucleus:
            return nucleus, text[-1].lower()
    return _parse_nmrpipe_label(text) or text, ''


def validate_spectra(spectra):
    if not 2 <= len(spectra) <= 3:
        raise ValueError(tr('Choose two or three spectra.'))
    first = spectra[0]
    axes = spectrum_axes(first)
    identities = [_axis_identity(a.label) for a in axes]
    nuclei = [nucleus for nucleus, _role in identities]
    for spectrum in spectra:
        other = spectrum_axes(spectrum)
        if spectrum.data.ndim not in (1, 2) or len(other) != len(axes):
            raise ValueError(tr('Compare matching 1D spectra or matching 2D planes.'))
        other_identities = [_axis_identity(a.label) for a in other]
        if nuclei != [nucleus for nucleus, _role in other_identities]:
            raise ValueError(tr('Choose the same nuclei and plane orientation for all spectra.'))
        if len(set(nuclei)) == 1 and len(axes) > 1:
            dims = getattr(first, 'dim_indices', None)
            other_dims = getattr(spectrum, 'dim_indices', None)
            roles_differ = any(a and b and a != b for (_n, a), (_m, b)
                               in zip(identities, other_identities))
            if roles_differ or (dims and other_dims and tuple(dims) != tuple(other_dims)):
                raise ValueError(tr('Homonuclear planes must have matching logical axes.'))
        for axis in other:
            ppm = axis.ppm
            if (len(ppm) < 2 or not np.all(np.isfinite(ppm))
                    or np.any(np.diff(ppm) == 0)):
                raise ValueError(tr(
                    'Comparison needs valid ppm coordinates with at least two points.'
                ))


def sample_spectrum(spectrum, ppm_axes, shift=None, *, data=None):
    """Linear interpolation on the requested ppm grid; uncovered cells remain NaN."""
    from scipy.ndimage import map_coordinates

    axes = spectrum_axes(spectrum)
    shift = tuple(shift) if shift is not None else (0.0,) * len(axes)
    coordinates = []
    for axis, grid, offset in zip(axes, ppm_axes, shift):
        p = axis.ppm
        coordinates.append((np.asarray(grid) - offset - p[0]) / (p[1] - p[0]))
    mesh = np.meshgrid(*coordinates, indexing='ij')
    data = np.asarray(spectrum.data if data is None else data, dtype=float)
    return map_coordinates(data, mesh, order=1, mode='constant', cval=np.nan, prefilter=False)


def temporary_peak_table(spectrum, max_peaks=512):
    """Detect signed, sub-point peak positions without writing or changing a peak table."""
    from core.qc.peak_detection import PeakDetectionParams, detect

    peaks = detect(spectrum.data, PeakDetectionParams(
        sigma_multiplier=6.0, min_snr=6.0, sign_mode='both',
    ))[:max_peaks]
    if not peaks:
        raise ValueError(tr('The displayed plane has no signal for translation fitting.'))
    axes = spectrum_axes(spectrum)
    positions = np.array([[axis.ppm[0] + point * (axis.ppm[1] - axis.ppm[0])
                           for axis, point in zip(axes, peak.position)] for peak in peaks])
    return positions, np.array([peak.sign for peak in peaks]), np.array([p.snr for p in peaks])


def _match_peaks(fixed, moving, signs_a, signs_b, tolerance, shift):
    """Nearest signed pairs, with each peak used at most once."""
    from scipy.spatial import cKDTree

    candidates = []
    for sign in (1, -1):
        ia, ib = np.flatnonzero(signs_a == sign), np.flatnonzero(signs_b == sign)
        if not len(ia) or not len(ib):
            continue
        tree = cKDTree(fixed[ia] / tolerance)
        queries = (moving[ib] + shift) / tolerance
        neighbors = tree.query_ball_point(queries, np.sqrt(fixed.shape[1]))
        for j, indices in enumerate(neighbors):
            for i in indices:
                error = (fixed[ia[i]] - moving[ib[j]] - shift) / tolerance
                if np.max(np.abs(error)) <= 1.0:
                    candidates.append((float(error @ error), int(ia[i]), int(ib[j])))
    used_a, used_b, pairs = set(), set(), []
    for _distance, i, j in sorted(candidates):
        if i not in used_a and j not in used_b:
            pairs.append((i, j))
            used_a.add(i)
            used_b.add(j)
    return np.asarray(pairs, dtype=int).reshape(-1, 2)


def fit_translation(reference, moving):
    """Fit a constant ppm shift from consensus among temporary signed peak tables."""
    validate_spectra([reference, moving])
    fixed, signs_a, snr_a = temporary_peak_table(reference)
    mobile, signs_b, snr_b = temporary_peak_table(moving)
    tolerance = np.array([max(abs(a.ppm[1] - a.ppm[0]), abs(b.ppm[1] - b.ppm[0])) * 2
                          for a, b in zip(spectrum_axes(reference), spectrum_axes(moving))])
    offsets = fixed[:, None, :] - mobile[None, :, :]
    offsets = offsets[signs_a[:, None] == signs_b[None, :]]
    if not len(offsets):
        raise ValueError(tr('No same-sign peak pairs were found for fitting.'))
    # Repeated displacements vote for a shared translation. Refinement uses actual
    # sub-point ppm positions, so narrow peaks and intensity changes cannot bias an image grid.
    bins = np.floor(offsets / (2 * tolerance)).astype(np.int64)
    cells, counts = np.unique(bins, axis=0, return_counts=True)
    seeds = cells[np.argsort(counts, kind='stable')[-32:]]
    weights_a = np.clip(np.log1p(snr_a) / np.median(np.log1p(snr_a)), .5, 2)
    weights_b = np.clip(np.log1p(snr_b) / np.median(np.log1p(snr_b)), .5, 2)
    best = None
    for cell in seeds:
        center = (cell + .5) * 2 * tolerance
        cluster = offsets[np.all(np.abs(offsets - center) <= 2 * tolerance, axis=1)]
        shift = np.median(cluster, axis=0)
        for _ in range(3):
            pairs = _match_peaks(fixed, mobile, signs_a, signs_b, tolerance, shift)
            if not len(pairs):
                break
            shift = np.median(fixed[pairs[:, 0]] - mobile[pairs[:, 1]], axis=0)
        if not len(pairs):
            continue
        residual = (fixed[pairs[:, 0]] - mobile[pairs[:, 1]] - shift) / tolerance
        support = float(np.sqrt(weights_a[pairs[:, 0]] * weights_b[pairs[:, 1]]).sum())
        quality = support - .1 * float(np.sum(residual * residual))
        # Smallest translation resolves an exact tie in repeated peak patterns.
        key = (quality, len(pairs), -float(np.linalg.norm(shift / tolerance)))
        if best is None or key > best[0]:
            best = (key, shift, pairs)
    minimum = min(3, len(fixed), len(mobile))
    if best is None or len(best[2]) < minimum:
        raise ValueError(tr('Too few consistent peak pairs were found for fitting.'))
    return tuple(float(v) for v in best[1]), len(best[2]) / len(fixed)
