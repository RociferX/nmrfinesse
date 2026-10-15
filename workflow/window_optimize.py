"""Per-axis window selection from FID/reconstructed traces, without candidate engine reruns.

Score one-axis Fourier magnitudes on up to 12 shared, signal-bearing traces. If the
energy leaders lack references, probe at most 256 traces stratified by energy and position.
Unwindowed references use 12 sigma, falling back to 6 only when no 12-sigma trace qualifies;
weak references also require continuous profiles and repeated frequency support.
Only peaks at least 25% of the strongest
reference peak in each trace enter the detection/near-neighbour criteria. Noise excludes all
detected peaks where sufficient background remains.

Each trace scores mean capped detection strength (height/noise, cap 30) times a near-pair
separation factor times the strongest-peak shape factor (symmetry and side-wing penalty).
Near pairs are within 1.5 times the smaller reference FWHM; a valley above 0.6 times the
smaller candidate height counts as merged, provided the reference valley was resolved.
Aggregate the same traces for every candidate, including degraded responses.

Score candidate broadening continuously relative to the narrowest valid FWHM, with
a squared inverse-width factor on every axis. Better signal and shape can compensate
for modest broadening. Keep raw scores and all component observations. GM/EM require SW.
The highest-scoring eligible candidate wins; ties keep
input order. This proxy does not certify all weak peaks or final phased-spectrum quality.

Default pools allow graceful fallback. Explicit pools use strict_candidates=True and fail
when no valid choice is available, so they cannot silently use a default configuration.
NUS direct-window application is coordinated by phase_routes because SMILE requires SP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from core.data.internal_data_model import Experiment
from ui_support.i18n import tr
from workflow.optimization_candidates import CandidateSelectionError
from workflow.truth_benchmark import detect_peaks, robust_noise_sigma


@dataclass
class WindowChoice:
    'Candidate window evaluation results.'

    cfg: dict[str, Any]
    label: str
    fwhm: float
    snr: float
    shape: float
    score: float
    selected: bool = False

    merged: float = 0.0

    n_ref: float = 0.0
    status: str = "scored"
    reason: str = ""
    raw_score: float = 0.0
    detection_score: float = 0.0
    separation_score: float = 0.0
    symmetry_score: float = 0.0
    sidelobe_score: float = 0.0
    resolution_score: float | None = None
    width_ratio: float | None = None
    resolution_reference_fwhm: float | None = None
    resolution_weight: float | None = None


@dataclass
class WindowOptimizeResult:
    'Single-axis window optimisation result.'

    choice: dict[str, Any]
    changed: bool
    scores: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    optimal_label: str = ""
    skipped_candidates: list[dict[str, Any]] = field(default_factory=list)
    status: str = "skipped"
    reason: str = ""
    sampling: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiWindowOptimizeResult:
    """Multi-indirect dimension window optimisation results: choice = {logical axis:
    configuration}.
    """

    choice: dict[str, dict[str, Any]]
    changed: bool
    per_axis: dict[str, WindowOptimizeResult] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    status: str = "skipped"
    reason: str = ""


# GM/EM parameters are Hz, using the sweep width of the scored axis. Both axes
# compare two mild configurations per family; broadening reduces the score.
_HZ_CANDIDATES: list[dict[str, Any]] = [
    {"type": "gaussian", "g1": 8.0, "g2": 15.0, "g3": 0.0, "c": 1.0},
    {"type": "gaussian", "g1": 4.0, "g2": 8.0, "g3": 0.0, "c": 1.0},
    {"type": "exp", "lb": 3.0, "c": 1.0},
    {"type": "exp", "lb": 5.0, "c": 1.0},
]

# Preserve the preferred direct SP and indirect no-window tie order.
DEFAULT_CANDIDATES: list[dict[str, Any]] = [
    {"type": "sine_bell", "off": 0.50, "end": 0.98, "pow": 2, "c": 0.5},
    {"type": "none"},
    {"type": "sine_bell", "off": 0.30, "end": 0.98, "pow": 1, "c": 0.5},
    {"type": "sine_bell", "off": 0.45, "end": 0.98, "pow": 1, "c": 0.5},
    {"type": "sine_bell", "off": 0.45, "end": 0.90, "pow": 1, "c": 0.5},
    {"type": "sine_bell", "off": 0.45, "end": 0.98, "pow": 2, "c": 0.5},
    *[dict(cfg) for cfg in _HZ_CANDIDATES],
]


INDIRECT_CANDIDATES: list[dict[str, Any]] = [
    {"type": "none"},
    {"type": "sine_bell", "off": 0.30, "end": 0.98, "pow": 1, "c": 0.5},
    {"type": "sine_bell", "off": 0.45, "end": 0.98, "pow": 1, "c": 0.5},
    {"type": "sine_bell", "off": 0.45, "end": 0.90, "pow": 1, "c": 0.5},
    {"type": "sine_bell", "off": 0.45, "end": 0.98, "pow": 2, "c": 0.5},
    {"type": "sine_bell", "off": 0.50, "end": 0.98, "pow": 2, "c": 0.5},
    *[dict(cfg) for cfg in _HZ_CANDIDATES],
]

# Broadening by r requires an r**2 gain in detection/separation/shape to win.
# This is a selection policy, rather than a universal physical quality metric.
_RESOLUTION_WEIGHT = 2.0




#




_PEAK_SIGMA_MULT = 12.0
_FALLBACK_SIGMA_MULT = 6.0
_MAX_PROBE_TRACES = 256
_MAX_SCORE_TRACES = 12
_PEAK_MIN_SEP = 2
_DETECTION_CAP = 30.0

_REFERENCE_MIN_FRACTION = 0.25

_MERGE_PAIR_SPAN = 1.5

_MERGE_VALLEY_FRACTION = 0.6


def _label(cfg: dict[str, Any]) -> str:
    wtype = str(cfg.get("type", "sine_bell"))
    if wtype == "none":
        return tr("No window (linear)")
    if wtype == "gaussian":
        return f"GM g1={cfg.get('g1', 8.0):g} g2={cfg.get('g2', 15.0):g}"
    if wtype == "exp":
        return f"EM lb={cfg.get('lb', 5.0):g}"
    return (
        f"SP off={cfg.get('off', 0.45):g} end={cfg.get('end', 0.95):g} "
        f"pow={cfg.get('pow', 1):g} c={cfg.get('c', 0.5):g}"
    )


def _window_vector(
    cfg: dict[str, Any], n: int, sw: float = 0.0
) -> np.ndarray:
    """NMRPipe-semantic window vector (0.2.191, aligned point by point with measured nmrPipe and
    its source).

    Formula source: measured on a VM nmrPipe all-ones FID + nmrglue pipe_proc/proc_base (same
    semantics as NMRPipe); the first point is multiplied by -c everywhere (SP scripts pass
    -c 0.5 explicitly, GM/EM scripts omit -c and take the NMRPipe default 1.0):
    - SP/sine_bell: w[i] = sin(pi*off + pi*(end-off)*i/(n-1))^pow;
    - GM (Lorentz-to-Gauss): w[i] = exp(pi*g1p*i - (k*pi*g2p*(g3*(n-1)-i))^2),
      k=1/(2*sqrt(ln2))=0.6005612... (measured on the VM, not nmrglue's 0.6 approximation),
      g1p=g1/SW, g2p=g2/SW (SW is that axis's spectral width in Hz, taken from FDFxSW in the fid
      header);
    - EM: w[i] = exp(-pi*(lb/SW)*i);
    none/off = all ones.
    """
    wtype = str(cfg.get("type", "sine_bell"))
    if wtype in ("none", "off"):
        return np.ones(n, dtype=float)
    i = np.arange(n, dtype=float)
    sw_eff = sw if sw > 0.0 else 1.0
    if wtype == "gaussian":
        g1 = float(cfg.get("g1", 0.0))
        g2 = float(cfg.get("g2", 0.0))
        g3 = float(cfg.get("g3", 0.0))
        g1p = g1 / sw_eff
        g2p = g2 / sw_eff
        e = np.pi * i * g1p
        g = (1.0 / (2.0 * np.sqrt(np.log(2.0)))) * np.pi * g2p * (g3 * (n - 1) - i)
        w = np.exp(e - g * g)
        c = float(cfg.get("c", 1.0))
    elif wtype == "exp":
        lb = float(cfg.get("lb", 5.0))
        w = np.exp(-np.pi * (lb / sw_eff) * i)
        c = float(cfg.get("c", 1.0))
    else:
        off = float(cfg.get("off", 0.45))
        end = float(cfg.get("end", 0.95))
        powv = 2 if wtype == "sine_bell_squared" else float(cfg.get("pow", 1))
        w = np.sin(np.pi * off + np.pi * (end - off) * i / max(n - 1, 1)) ** powv
        c = float(cfg.get("c", 0.5))
    w[0] *= c
    return w



def _peak_fwhm(amp: np.ndarray, index: int) -> float:
    'Half-height full width of the peak at ``index`` (points, linearly interpolated).'
    peak = float(amp[index])
    if peak <= 0.0:
        return 1.0
    half = peak * 0.5
    n = amp.size
    left = index
    while left > 0 and amp[left] > half:
        left -= 1
    if left > 0:
        frac = (half - amp[left]) / max(amp[left + 1] - amp[left], 1e-12)
        left = left + max(min(frac, 1.0), 0.0)
    right = index
    while right < n - 1 and amp[right] > half:
        right += 1
    if right < n - 1:
        frac = (half - amp[right]) / max(amp[right - 1] - amp[right], 1e-12)
        right = right - max(min(frac, 1.0), 0.0)
    return max(float(right - left), 1.0)


def _noise_sigma_without_peaks(amp: np.ndarray, peaks: list[tuple[int, float]]) -> float:
    """Robust noise sigma after excluding **all** detected peaks (each +-3 FWHM).

    The old convention carved out only the strongest peak's neighbourhood, so a neighbouring
    peak
    in a crowded region counted as noise (sigma overestimated, candidate differences flattened);
    too few leftover points falls back to the spectrum-wide MAD, a consistent conservative
    estimate.
    """
    n = amp.size
    mask = np.ones(n, dtype=bool)
    for index, _height in peaks:
        radius = max(int(round(3.0 * _peak_fwhm(amp, index))), 3)
        mask[max(index - radius, 0) : min(index + radius + 1, n)] = False
    selected = amp[mask]
    if selected.size < max(8, n // 5):
        return robust_noise_sigma(amp)
    return robust_noise_sigma(selected)


def _shape_components(amp: np.ndarray, index: int, fwhm: float) -> tuple[float, float]:
    """Measure peak symmetry and sidelobe suppression factors."""
    peak = float(amp[index])
    if peak <= 0.0:
        return 0.0, 0.0
    half = peak * 0.5
    n = amp.size
    left = index
    while left > 0 and amp[left] > half:
        left -= 1
    right = index
    while right < n - 1 and amp[right] > half:
        right += 1
    half_l = float(index - left)
    half_r = float(right - index)
    sym = min(half_l, half_r) / max(max(half_l, half_r), 1e-9)
    span = max(int(fwhm), 2)
    left_sw = amp[max(index - 6 * span, 0) : max(index - 2 * span, 0)]
    right_sw = amp[min(index + 2 * span, n) : min(index + 6 * span, n)]
    swell = 0.0
    if left_sw.size and right_sw.size:
        swell = float(max(np.max(left_sw), np.max(right_sw))) / peak
    return sym, 1.0 / (1.0 + 5.0 * max(swell, 0.0))


def _shape_factor(amp: np.ndarray, index: int, fwhm: float) -> float:
    symmetry, sidelobe = _shape_components(amp, index, fwhm)
    return symmetry * sidelobe


def _reference_peaks(
    amp: np.ndarray, sigma_mult: float = _PEAK_SIGMA_MULT, *, noise_sigma: float | None = None,
) -> list[tuple[int, float, float]]:
    """The expected peaks on the un-windowed reference spectrum: ``[(position, height, FWHM)]``,
    sorted by position.
    """
    return [
        (index, height, _peak_fwhm(amp, index))
        for index, height in detect_peaks(
            amp, sigma_mult=sigma_mult, min_sep=_PEAK_MIN_SEP, noise_sigma=noise_sigma,
        )
    ]


def _significant_reference(
    reference: list[tuple[int, float, float]],
) -> list[tuple[int, float, float]]:
    """The **significant** peaks of the reference spectrum (height >= ``_REFERENCE_MIN_FRACTION``
    of the strongest one).

    Far weaker local maxima are truncation side lobes or noise spikes: they must neither be
    required to be found again nor take part in the "closest peak spacing" -- otherwise adding a
    window to truncated data (which suppresses side lobes) would be scored as losing real peaks,
    and a naturally decaying axis would have its resolution threshold tightened by side-lobe
    spacing.
    """
    strongest = max((float(item[1]) for item in reference), default=0.0)
    if strongest <= 0.0:
        return []
    return [
        item
        for item in reference
        if float(item[1]) >= _REFERENCE_MIN_FRACTION * strongest
    ]


def _resolved_pairs(
    reference: list[tuple[int, float, float]], amp: np.ndarray,
) -> list[tuple[int, int]]:
    """Only penalize loss of valleys already resolved in the unwindowed reference."""
    targets = _significant_reference(reference)
    pairs = []
    for left, right in zip(targets, targets[1:]):
        a, b = int(left[0]), int(right[0])
        if not 0 < b - a <= _MERGE_PAIR_SPAN * max(min(left[2], right[2]), 1.0):
            continue
        if np.min(amp[a:b + 1]) <= _MERGE_VALLEY_FRACTION * min(left[1], right[1]):
            pairs.append((a, b))
    return pairs


def _mask_edges(amp: np.ndarray) -> None:
    amp[..., :max(2, amp.shape[-1] // 80)] = 0.0
    amp[..., -3:] = 0.0


def _sample_references(
    flat: np.ndarray, n_zf: int,
) -> tuple[np.ndarray, list[list[tuple[int, float, float]]], np.ndarray, dict[str, Any]]:
    """Bounded, deterministic rescue; candidate-independent references and trace IDs."""
    total = len(flat)
    energy = np.sum(np.abs(flat) ** 2, axis=-1)
    order = np.argsort(-energy, kind="stable")
    keep = min(total, max(int(np.ceil(total * 0.1)), 4), _MAX_SCORE_TRACES)
    # Bound cached FFT magnitudes as well as trace count (large direct axes).
    budget = min(total, _MAX_PROBE_TRACES, max(1, (64 * 1024**2) // (8 * n_zf)))
    keep = min(keep, budget)
    cache: dict[int, tuple[np.ndarray, float, list[tuple[int, float, float]]]] = {}

    def probe(indices: list[int]) -> None:
        fresh = [int(i) for i in indices if int(i) not in cache][:budget - len(cache)]
        block = max(1, min(32, (8 * 1024**2) // (16 * n_zf)))
        for start in range(0, len(fresh), block):
            ids = fresh[start:start + block]
            amps = np.abs(np.fft.fft(flat[ids], n_zf, axis=-1))
            _mask_edges(amps)
            med = np.median(amps, axis=1)
            sigma = np.maximum(
                1.4826 * np.median(np.abs(amps - med[:, None]), axis=1), np.finfo(float).eps,
            )
            for i, row, noise in zip(ids, amps, sigma):
                refs = (_reference_peaks(row, noise_sigma=float(noise))
                        if np.max(row) > _PEAK_SIGMA_MULT * noise else [])
                cache[i] = (row, float(noise), refs)

    probe(order[:keep].tolist())
    qualified = [i for i, (_row, _noise, refs) in cache.items() if refs]
    rescued = len(qualified) < min(4, keep)
    if rescued:
        for size in (64, 256):
            ranks = np.linspace(0, total - 1, min(total, size // 2), dtype=int)
            # Interleave energy quantiles and acquisition positions, deduplicating
            # before truncation so the hard budget contains distinct traces.
            ids = list(dict.fromkeys(int(i) for pair in zip(order[ranks], ranks) for i in pair))
            probe(ids)
            qualified = [i for i, (_row, _noise, refs) in cache.items() if refs]
            if len(qualified) >= min(4, keep) or len(cache) >= budget:
                break
    threshold = _PEAK_SIGMA_MULT
    strong_count = len(qualified)
    reason = "stratified_rescue" if rescued else "energy_fast_path"
    if not qualified:
        threshold = _FALLBACK_SIGMA_MULT
        weak: dict[int, list[tuple[int, float, float]]] = {}
        support = np.zeros(n_zf, dtype=int)
        for i, (amp, noise, _refs) in cache.items():
            refs = _reference_peaks(amp, threshold, noise_sigma=noise)
            refs = [p for p in refs if p[2] >= 2.0
                    and max(amp[p[0] - 1], amp[p[0] + 1]) >= 0.5 * p[1]]
            weak[i] = refs
            bins = {j for p in refs for j in range(max(0, p[0] - 1), min(n_zf, p[0] + 2))}
            if bins:
                support[list(bins)] += 1
        required = min(5, len(cache))
        for i, refs in weak.items():
            amp, noise, _old = cache[i]
            cache[i] = (amp, noise, [p for p in refs if support[p[0]] >= required])
        qualified = [i for i, (_row, _noise, refs) in cache.items() if refs]
        reason = "six_sigma_fallback" if qualified else "no_supported_reference"
    # A bounded diversity pass avoids spending all candidate FFTs on one frequency
    # band when rescue found several. Within a band prefer stronger references.
    ranked = sorted(qualified, key=lambda i: (-max(p[1] for p in cache[i][2]) / cache[i][1], i))
    selected: list[int] = []
    bands: set[int] = set()
    for i in ranked:
        strongest = max(cache[i][2], key=lambda p: p[1])[0]
        band = min(15, 16 * strongest // n_zf)
        if band not in bands:
            selected.append(i)
            bands.add(band)
        if len(selected) >= keep:
            break
    selected.extend(i for i in ranked if i not in selected)
    selected = selected[:keep]
    diagnostic = {
        "reference_sigma": threshold if selected else None,
        "total_traces": total, "scanned_traces": len(cache), "used_traces": len(selected),
        "trace_indices": selected, "probe_budget": budget,
        "qualified_12": strong_count, "qualified_6": len(qualified) if threshold == 6 else 0,
        "sampling_reason": reason, "budget_exhausted": len(cache) >= budget and budget < total,
        "max_height_sigma": max((float(np.max(row)) / noise for row, noise, _ in cache.values()),
                                default=0.0),
    }
    amps = np.stack([cache[i][0] for i in selected]) if selected else np.empty((0, n_zf))
    return flat[selected], [cache[i][2] for i in selected], amps, diagnostic


def _measure_trace(
    amp: np.ndarray,
    reference_peaks: list[tuple[int, float, float]] | None = None,
    *, resolved_pairs: list[tuple[int, int]] | None = None,
) -> dict[str, float]:
    """Detection statistics of a single trace (the candidate spectrum is already apodised).

    ``reference_peaks`` are the peaks of the un-windowed reference spectrum (position / height /
    FWHM). Only the **significant** ones (>= ``_REFERENCE_MIN_FRACTION`` of the strongest peak)
    count as expected peaks:

    * detection term ``det``: the height at the same position in the candidate spectrum divided
    by
      the noise sigma (sigma is a robust MAD after excluding **all** detected peaks). Using the
      height at that position instead of looking for a local maximum again keeps a noise spike
      from pretending that the peak is still there;
    * merging term ``merge``: when two expected peaks are already resolved in the reference
      spectrum (spacing <= 1.5 x the smaller FWHM), the valley between them in the candidate
      spectrum must drop below ``_MERGE_VALLEY_FRACTION`` of the smaller peak -- a valley that
      does
      not drop means this window merged the two peaks into one, which in the ground-truth
      benchmark
      is one real peak lost;
    * line-shape factor ``shape``: symmetry + side lobes (suppresses truncation ringing and
      artefacts, same convention as 0.2.139).

    ``score = det_mean x merge_factor x shape``: the three factors are detection strength,
    resolution loss and artefacts.
    """
    n = amp.size
    empty = {
        "fwhm": float(n), "snr": 0.0, "shape": 0.0, "score": 0.0,
        "det_mean": 0.0, "n_ref": 0.0, "resolved": 0.0, "ok": False,
        "separation_score": 0.0, "symmetry_score": 0.0, "sidelobe_score": 0.0,
    }
    if n < 16:
        return empty
    # Shared references supply targets even when a candidate suppresses them below
    # the detection threshold. Never replace an explicitly empty reference.
    if reference_peaks is None:
        reference_peaks = _reference_peaks(amp)
    if not reference_peaks:
        return empty
    peaks = [(int(p[0]), float(amp[int(p[0])])) for p in reference_peaks]
    sigma = _noise_sigma_without_peaks(amp, peaks)
    strongest_index, strongest_height = max(peaks, key=lambda item: item[1])
    fwhm = _peak_fwhm(amp, strongest_index)
    snr = float(strongest_height) / max(sigma, np.finfo(float).eps)
    symmetry, sidelobe = _shape_components(amp, strongest_index, fwhm)
    shape = symmetry * sidelobe
    targets = _significant_reference(reference_peaks)
    if not targets:
        return {**empty, "fwhm": fwhm, "snr": snr, "shape": shape,
                "score": snr * shape, "det_mean": snr, "separation_score": 1.0,
                "symmetry_score": symmetry, "sidelobe_score": sidelobe, "ok": True}
    det_sum = 0.0
    for index, _height, _ref_fwhm in targets:
        det_sum += min(
            float(amp[int(index)]) / max(sigma, np.finfo(float).eps), _DETECTION_CAP
        )
    det_mean = det_sum / len(targets)

    merged = 0
    pairs = 0
    for left_index, right_index in resolved_pairs or []:
        pairs += 1
        valley = float(np.min(amp[left_index : right_index + 1]))
        smaller = min(float(amp[left_index]), float(amp[right_index]))
        if smaller <= 0.0:
            merged += 1
            continue
        if valley > _MERGE_VALLEY_FRACTION * smaller:
            merged += 1
    n_targets = len(targets)
    merge_factor = 1.0 if pairs == 0 else max(1.0 - merged / pairs, 0.0)
    score = det_mean * merge_factor * shape
    return {
        "fwhm": fwhm,
        "snr": snr,
        "shape": shape,
        "score": score,
        "det_mean": det_mean,
        "n_ref": float(n_targets),
        "resolved": float(n_targets - merged),
        "separation_score": merge_factor,
        "symmetry_score": symmetry,
        "sidelobe_score": sidelobe,
        "ok": True,
    }


def _aggregate(
    amp_traces: np.ndarray,
    reference: list[list[tuple[int, float, float]]],
    resolved_pairs: list[list[tuple[int, int]]],
) -> dict[str, float]:
    'Detection statistics per trace, then the median (robust against individual noisy traces).'
    per = [_measure_trace(row, refs, resolved_pairs=pairs)
           for row, refs, pairs in zip(amp_traces, reference, resolved_pairs)]
    ok = per  # Every candidate is measured on exactly the same traces.
    if not ok:
        return {"fwhm": float(amp_traces.shape[-1]), "snr": 0.0, "shape": 0.0,
                "score": 0.0, "det_mean": 0.0, "n_ref": 0.0, "resolved": 0.0,
                "separation_score": 0.0, "symmetry_score": 0.0, "sidelobe_score": 0.0}
    return {
        "fwhm": float(np.median([m["fwhm"] for m in ok])),
        "snr": float(np.median([m["snr"] for m in ok])),
        "shape": float(np.median([m["shape"] for m in ok])),
        "score": float(np.median([m["score"] for m in ok])),
        "det_mean": float(np.median([m["det_mean"] for m in ok])),
        "n_ref": float(np.median([m["n_ref"] for m in ok])),
        "resolved": float(np.median([m["resolved"] for m in ok])),
        **{key: float(np.median([m[key] for m in ok])) for key in
           ("separation_score", "symmetry_score", "sidelobe_score")},
    }


def _resolution_score(width_ratio: float, weight: float) -> float:
    """Continuous preference for narrower peaks, without rejecting broader candidates."""
    ratio = max(width_ratio, 1.0)
    return float(ratio ** -weight)


def _score_axis(
    arr: np.ndarray,
    axis: int,
    candidates: list[dict[str, Any]],
    *,
    zf_size: int | None = None,
    resolution_penalty: float = _RESOLUTION_WEIGHT,
    sw: float = 0.0,
) -> tuple[list[WindowChoice], WindowChoice | None, str, dict[str, Any]]:
    """Score the candidate windows along the given time axis; returns (choices, best, log rows).

    With resolution_penalty>0 an exponential penalty is applied to FWHM broadening relative to
    the best in the qualifying pool (score *= exp(-k*max(fwhm/min_fwhm-1,0))): the
    resolution-limited indirect dimension uses it to make a naturally decaying axis land on no
    window while a truncated axis still keeps a mild window (0.2.190).
    """
    n = arr.shape[axis]
    if not np.isfinite(resolution_penalty) or resolution_penalty < 0:
        raise ValueError("resolution_penalty must be finite and nonnegative")
    moved = np.moveaxis(arr, axis, -1)
    flat = moved.reshape(-1, n)
    n_zf = zf_size or n
    picked, reference, ref_amp, sampling = _sample_references(flat, n_zf)


    sw_dependent = {"gaussian", "exp"}
    skipped_sw = 0
    scorable: list[dict[str, Any]] = []
    for cfg in candidates:
        if str(cfg.get("type", "sine_bell")) in sw_dependent and sw <= 0.0:
            skipped_sw += 1
            continue
        scorable.append(cfg)

    resolved_pairs = [_resolved_pairs(refs, row) for refs, row in zip(reference, ref_amp)]
    measured: list[WindowChoice] = []
    for cfg in scorable:
        win = _window_vector(cfg, n, sw=sw)
        amp = np.abs(np.fft.fft(picked * win, n_zf, axis=-1))

        _mask_edges(amp)
        agg = _aggregate(amp, reference, resolved_pairs)
        measured.append(
            WindowChoice(
                cfg=cfg,
                label=_label(cfg),
                fwhm=agg["fwhm"],
                snr=agg["snr"],
                shape=agg["shape"],
                score=agg["score"],
                merged=float(agg["n_ref"] - agg["resolved"]),
                n_ref=float(agg["n_ref"]),
                raw_score=agg["score"],
                detection_score=agg["det_mean"],
                separation_score=agg["separation_score"],
                symmetry_score=agg["symmetry_score"],
                sidelobe_score=agg["sidelobe_score"],
            )
        )
    valid = [m for m in measured if m.snr > 0.0]
    if not valid:
        return measured, None, tr("trace no valid signal"), sampling
    min_fwhm = min(m.fwhm for m in valid)
    pool = valid
    pool_ids = {id(m) for m in pool}
    for m in measured:
        if id(m) not in pool_ids:
            m.status = "rejected"
            m.reason = "no_valid_signal"
            continue
        m.width_ratio = m.fwhm / min_fwhm
        m.resolution_reference_fwhm = min_fwhm
        m.resolution_weight = resolution_penalty
        m.resolution_score = _resolution_score(m.width_ratio, resolution_penalty)
        m.score = m.raw_score * m.resolution_score
    positive = [m for m in pool if np.isfinite(m.score) and m.score > 0.0]
    if not positive:
        for m in pool:
            m.status, m.reason = "rejected", "zero_score"
        return measured, None, tr("trace no valid signal"), sampling
    best = max(positive, key=lambda m: m.score)
    for m in measured:
        m.selected = m is best
    log = (
        tr(
            "optimal {p0} (FWHM {p1:.2f}point, SNR {p2:.1f}, shape {p3:.3f}, score {p4:.3f}); "
            "scored {p5}/{p6} candidate(s); resolution factor {p7:.3f} "
            "(width {p8:.3f}x, exponent {p9:.3f})",
            p0=best.label,
            p1=best.fwhm,
            p2=best.snr,
            p3=best.shape,
            p4=best.score,
            p5=len(pool),
            p6=len(measured),
            p7=best.resolution_score,
            p8=best.width_ratio,
            p9=best.resolution_weight,
        )
    )
    if best.merged > 0.0:
        log += tr(
            "; {p0}/{p1} expected peak(s) were merged into one detection by this "
            "window",
            p0=int(round(best.merged)),
            p1=int(round(best.n_ref)),
        )
    if skipped_sw:
        log += tr(
            "; {p0} spectral width dependent candidates (GM/EM) not provided SW "
            "skip",
            p0=skipped_sw,
        )
    return measured, best, log, sampling


def optimize_axis_window(
    arr: np.ndarray,
    axis: int,
    candidates: list[dict[str, Any]] | None = None,
    *,
    zf_size: int | None = None,
    current: dict[str, Any] | None = None,
    axis_label: str = "",
    resolution_penalty: float = _RESOLUTION_WEIGHT,
    sw: float = 0.0,
    strict_candidates: bool = False,
) -> WindowOptimizeResult:
    """Score candidate windows along arr's axis timeline (shared engine, used by the direct and
    indirect dimensions).
    """
    data = np.asarray(arr)
    if data.ndim < 1 or data.shape[axis] < 16:
        if strict_candidates:
            raise CandidateSelectionError(
                f"Insufficient points for explicit window candidates: {axis_label}"
            )
        return WindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            reason="insufficient_points",
            logs=[tr(
                "{p0}: window optimisation skip: insufficient points in this "
                "axis",
                p0=axis_label,
            )],
        )
    cands = candidates if candidates is not None else DEFAULT_CANDIDATES
    measured, best, message, sampling = _score_axis(
        data, axis, cands, zf_size=zf_size,
        resolution_penalty=resolution_penalty,
        sw=sw,
    )
    scores = [
        {"cfg": dict(m.cfg), "label": m.label, "fwhm": m.fwhm, "snr": m.snr,
         "shape": m.shape, "score": m.score, "selected": m.selected,
         "merged": m.merged, "n_ref": m.n_ref,
         "status": m.status if best is not None else "rejected",
         "reason": m.reason or ("" if best is not None else "no_valid_signal")}
        for m in measured
    ]
    for row, measured_choice in zip(scores, measured):
        row.update({key: getattr(measured_choice, key) for key in (
            "raw_score", "detection_score", "separation_score", "symmetry_score",
            "sidelobe_score", "resolution_score", "width_ratio", "resolution_reference_fwhm",
            "resolution_weight",
        )})
    skipped = [dict(cfg) for cfg in cands
               if cfg.get("type") in {"gaussian", "exp"} and sw <= 0.0]
    if best is None:
        if strict_candidates:
            raise CandidateSelectionError(f"No valid explicit window candidate for {axis_label}")
        return WindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            scores=scores,
            skipped_candidates=skipped,
            reason="zero_score" if any(m.reason == "zero_score" for m in measured)
            else "no_valid_signal",
            sampling=sampling,
            logs=[tr("{p0}: window optimisation skip:{p1}", p0=axis_label, p1=message)],
        )
    changed = best.cfg != (current or {})
    logs = [tr("{p0}: window(memory score): {p1}", p0=axis_label, p1=message)]
    if not changed:
        logs.append(tr(
            "{p0}: Window: The optimal configuration is consistent with the existing configuration "
            "and remains",
            p0=axis_label,
        ))
    return WindowOptimizeResult(
        choice=dict(best.cfg),
        changed=changed,
        scores=scores,
        skipped_candidates=skipped,
        status="scored",
        logs=logs,
        optimal_label=best.label,
        sampling=sampling,
    )


def optimize_direct_window(
    fid: np.ndarray,
    *,
    zf_size: int | None = None,
    candidates: list[dict[str, Any]] | None = None,
    current: dict[str, Any] | None = None,
    sw: float = 0.0,
    strict_candidates: bool = False,
) -> WindowOptimizeResult:
    """Score candidate windows on the original fid direct dimension trace (last axis), returning
    the optimal configuration.
    """
    return optimize_axis_window(
        fid,
        -1,
        candidates=candidates,
        zf_size=zf_size,
        current=current,
        axis_label=tr("direct dimension"),
        sw=sw,
        strict_candidates=strict_candidates,
    )


def optimize_indirect_windows(
    arr: np.ndarray,
    axis_map: dict[str, int],
    *,
    candidates: list[dict[str, Any]] | None = None,
    current: dict[str, dict[str, Any]] | None = None,
    zf_mult: float = 2.0,
    sw_map: dict[str, float] | None = None,
    strict_candidates: bool = False,
) -> MultiWindowOptimizeResult:
    """Score the candidate windows of every indirect-dimension timeline (no window included) and
    write the best one back per axis.

    axis_map: logical axis -> time axis index in the array (the other axes of the array may be
    time or frequency, which does not affect the per-axis scoring). zf_mult: zero-fill factor
    used
    for scoring (indirect dimensions have few points, and 2x improves the FWHM resolution).
    """
    data = np.asarray(arr)
    cands = candidates if candidates is not None else INDIRECT_CANDIDATES
    current = dict(current or {})
    choice: dict[str, dict[str, Any]] = dict(current)
    per_axis: dict[str, WindowOptimizeResult] = {}
    logs: list[str] = []
    changed = False
    for axis_name, axis in axis_map.items():
        if axis >= data.ndim or data.shape[axis] < 16:
            if strict_candidates:
                raise CandidateSelectionError(
                    f"Insufficient points for explicit window candidates: {axis_name}"
                )
            logs.append(tr(
                "{p0}: indirect dimension window optimisation skip: insufficient "
                "points",
                p0=axis_name,
            ))
            per_axis[axis_name] = WindowOptimizeResult(
                choice=dict(current.get(axis_name) or {}), changed=False,
                reason="insufficient_points",
            )
            continue
        n = int(data.shape[axis])
        zf_size = max(int(round(n * max(zf_mult, 1.0))), n)
        res = optimize_axis_window(
            data,
            axis,
            cands,
            zf_size=zf_size,
            current=current.get(axis_name),
            axis_label=tr("{p0}(indirect dimension)", p0=axis_name),
            resolution_penalty=_RESOLUTION_WEIGHT,
            sw=(sw_map or {}).get(axis_name, 0.0),
            strict_candidates=strict_candidates,
        )
        per_axis[axis_name] = res
        logs += res.logs
        if res.changed:
            choice[axis_name] = dict(res.choice)
            changed = True
    if not per_axis:
        if strict_candidates:
            raise CandidateSelectionError("No indirect time axis for explicit window candidates")
        logs.append(tr("indirect dimension window optimisation skip: no timeline available"))
    return MultiWindowOptimizeResult(
        choice=choice, changed=changed, per_axis=per_axis, logs=logs
    )

def _fid_paths(work: Path, experiment: Experiment) -> list[Path]:
    """Converted fid path: slice stream (fid/test*.fid), single file (dataset.fid) or the merged
    single file of multi-part data (merged/dataset.fid).

    2026-09-23: no second copy is kept any more -- this follows
    ``workflow.direct_diagnostics.collect_fid_paths`` directly. Both implementations used to
    miss ``merged/{dataset_id}.fid`` together, which silently skipped the FID-layer window
    optimisation of multi-part datasets.
    """
    from workflow.direct_diagnostics import collect_fid_paths

    return collect_fid_paths(work, experiment)


def _load_fid(work: Path, experiment: Experiment) -> tuple[np.ndarray, dict] | None:
    """Load the converted fid (single file or 3D slice stream stack) + header (take the first file
    dic).
    """
    paths = _fid_paths(work, experiment)
    if not paths:
        return None
    import nmrglue as ng

    arrays: list[np.ndarray] = []
    dic: dict = {}
    for index, path in enumerate(paths):
        d, fid = ng.pipe.read(str(path))
        if index == 0:
            dic = d
        arrays.append(fid)
    fid = arrays[0] if len(arrays) == 1 else np.concatenate(arrays, axis=0)
    return fid, dic



def _load_recon_planes(
    work: Path, experiment: Experiment
) -> tuple[np.ndarray, dict] | None:
    """Load the SMILE reconstruction planes (indirect-dimension time domain) + header.

    0.2.199-patch29 (measured with manually sliced sampleB + sampleJ):
    for 3D, nus3d_rc/test%04d.ft1 has one file per direct-dimension (F3 frequency) point and the
    plane array is (F1 time, F2 time): the 13C axis is hypercomplex 4xTD (300 real) and the 15N
    axis is States real (TD). The window scoring has to act on the original real axis exactly as
    the backend does (SP acts directly on that axis), so it must **not** naively unpack axis 0
    interleaved (that would unpack hypercomplex data incorrectly); after stacking the layout is
    (F1 time, F2 time, F3). Only the first FDFILECOUNT planes of the first header are read, so
    stale test*.ft1 files cannot mix in (patch29).
    For 2D, nus2d/recon.ft1 is a single file (F2 frequency, F1 time) with the F1 complex part on
    the last axis -- nmrglue already reads it as complex (F2, F1), so read_pipe_complex must not
    be used to split axis 0 (it would halve the direct dimension; evidenced by the 2D recon
    produced by sampleF in 0.2.199-patch29b).
    """
    import nmrglue as ng

    from core.data.pipe_io import read_pipe_complex

    if experiment.ndim >= 3:
        plane_dir = work / "nus3d_rc"
        paths = sorted(plane_dir.glob("test*.ft1"))
        if not paths:
            return None
        dic: dict = {}
        arrays: list[np.ndarray] = []
        count: int | None = None
        for index, path in enumerate(paths):
            d, raw = ng.pipe.read(str(path))
            if index == 0:
                dic = d
                try:
                    count = int(float(dic.get("FDFILECOUNT") or 0))
                except (TypeError, ValueError):
                    count = None
            if count is not None and len(arrays) >= count:
                break
            arrays.append(np.asarray(raw))
        if not arrays:
            return None
        return np.stack(arrays, axis=-1), dic
    recon = work / "nus2d" / "recon.ft1"
    if not recon.is_file():
        return None
    dic, raw = ng.pipe.read(str(recon))
    arr = np.asarray(raw)
    if np.iscomplexobj(arr):
        planes: np.ndarray = arr.astype(np.complex128)
    else:
        planes = read_pipe_complex(recon)
    return planes, dic



def _uniform_axis_map(experiment: Experiment) -> dict[str, int]:
    """Uniform fid layout: 2D (F1, F2), 3D (F1, F2, F3), indirect dimension takes the axis
    according to internal convention.
    """
    from core.data.internal_data_model import AxisRole
    from core.processing.axes import axis_index

    return {
        dim.logical_axis: axis_index(dim.logical_axis, experiment.ndim)
        for dim in experiment.dimensions
        if dim.role is not AxisRole.DIRECT
    }


def _nus_axis_map(experiment: Experiment) -> dict[str, int]:
    """NUS reconstruction plane layout (0.2.199-patch29 correction): 2D (F2 frequency, F1 time)
    -> F1=1; 3D stack (F1 time, F2 time, F3) -> F1=0, F2=1. The old code used F1=2, which
    pointed at the direct-dimension axis.
    """
    if experiment.ndim >= 3:
        return {"F1": 0, "F2": 1}
    return {"F1": 1}


def _axis_sw(
    dic: dict[str, Any], axis: str, experiment: Experiment | None = None
) -> float:
    """Spectral width (SW in Hz) of a logical axis, taken from the fid / plane header.

    0.2.199-patch29: match the logical nucleus against the header nucleus label (FDF{n}LABEL)
    first (in a 3D header FDF1=15N/FDF2=1H/FDF3=13C, which does not agree with the logical
    F2/F3/F1, so taking the numeric suffix would read the wrong axis's SW); when the experiment
    is unknown, fall back to the numeric suffix (a 2D uniform header agrees with the logical
    axis).
    """
    if experiment is not None:
        dim = next(
            (d for d in experiment.dimensions if d.logical_axis == axis), None
        )
        nucleus = (dim.nucleus or "").strip() if dim is not None else ""

        norm = lambda v: "".join(ch for ch in v if ch.isalnum())  # noqa: E731
        if nucleus:
            for i in (1, 2, 3):
                label = str(dic.get(f"FDF{i}LABEL") or "").strip()
                if norm(label) == norm(nucleus):
                    try:
                        return float(dic.get(f"FDF{i}SW") or 0.0)
                    except (TypeError, ValueError):
                        return 0.0
    suffix = axis[1:] if axis.startswith("F") else axis
    try:
        return float(dic.get(f"FDF{suffix}SW") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def optimize_direct_window_from_work(
    work_dir: Path | str,
    experiment: Experiment,
    *,
    current: dict[str, Any] | None = None,
    zf_size: int | None = None,
    candidates: list[dict[str, Any]] | None = None,
    strict_candidates: bool = False,
) -> WindowOptimizeResult:
    """Load the converted fid (work directory, slice streams supported) and optimise the direct
    dimension window without re-running SMILE/process. SW (spectral width) is read from the fid
    header so GM/EM can be modelled exactly.
    """
    work = Path(work_dir)
    try:
        loaded = _load_fid(work, experiment)
    except Exception as exc:  # noqa: BLE001
        if strict_candidates:
            raise CandidateSelectionError(
                "Cannot read FID for explicit direct-window candidates"
            ) from exc
        return WindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            status="error", reason="fid_read_failed",
            logs=[tr("direct dimension window optimisation failed (read fid): {p0}", p0=exc)],
        )
    if loaded is None:
        if strict_candidates:
            raise CandidateSelectionError("Missing FID for explicit direct-window candidates")
        return WindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            reason="missing_fid",
            logs=[tr("direct dimension window optimisation skipped: converted.fid not found")],
        )
    fid, dic = loaded
    direct_axis = f"F{experiment.ndim}"
    return optimize_direct_window(
        fid,
        zf_size=zf_size,
        candidates=candidates,
        current=current,
        sw=_axis_sw(dic, direct_axis, experiment),
        strict_candidates=strict_candidates,
    )



def optimize_indirect_windows_from_work(
    work_dir: Path | str,
    experiment: Experiment,
    *,
    current: dict[str, dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    strict_candidates: bool = False,
) -> MultiWindowOptimizeResult:
    """Optimise every uniform indirect-dimension window from the converted fid (in-memory scoring,
    process is not re-run). Each axis's SW is read from the fid header so GM/EM can be modelled
    exactly.
    """
    work = Path(work_dir)
    try:
        loaded = _load_fid(work, experiment)
    except Exception as exc:  # noqa: BLE001
        if strict_candidates:
            raise CandidateSelectionError(
                "Cannot read FID for explicit indirect-window candidates"
            ) from exc
        return MultiWindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            status="error", reason="fid_read_failed",
            logs=[tr("indirect dimension window optimisation failed (reading fid): {p0}", p0=exc)],
        )
    if loaded is None:
        if strict_candidates:
            raise CandidateSelectionError("Missing FID for explicit indirect-window candidates")
        return MultiWindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            reason="missing_fid",
            logs=[tr("indirect dimension window optimisation skipped: converted.fid not found")],
        )
    fid, dic = loaded
    axis_map = _uniform_axis_map(experiment)
    sw_map = {axis: _axis_sw(dic, axis, experiment) for axis in axis_map}
    return optimize_indirect_windows(
        fid, axis_map, candidates=candidates, current=current, sw_map=sw_map,
        strict_candidates=strict_candidates,
    )



def optimize_indirect_windows_from_recon(
    work_dir: Path | str,
    experiment: Experiment,
    *,
    current: dict[str, dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    strict_candidates: bool = False,
) -> MultiWindowOptimizeResult:
    """Optimise every NUS indirect-dimension window from the SMILE reconstruction planes (in-memory
    scoring, SMILE is not re-run). Each axis's SW is read from the plane header so GM/EM can be
    modelled exactly.
    """
    work = Path(work_dir)
    try:
        loaded = _load_recon_planes(work, experiment)
    except Exception as exc:  # noqa: BLE001
        if strict_candidates:
            raise CandidateSelectionError(
                "Cannot read reconstruction for explicit window candidates"
            ) from exc
        return MultiWindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            status="error", reason="reconstruction_read_failed",
            logs=[tr(
                "Indirect dimension window optimisation failed (reading reconstruction plane): "
                "{p0}",
                p0=exc,
            )],
        )
    if loaded is None:
        if strict_candidates:
            raise CandidateSelectionError("Missing reconstruction for explicit window candidates")
        return MultiWindowOptimizeResult(
            choice=dict(current or {}),
            changed=False,
            reason="missing_reconstruction",
            logs=[tr(
                "indirect dimension window optimisation skip: not found SMILE reconstruction "
                "plane",
            )],
        )
    planes, dic = loaded
    axis_map = _nus_axis_map(experiment)
    sw_map = {axis: _axis_sw(dic, axis, experiment) for axis in axis_map}
    return optimize_indirect_windows(
        planes, axis_map, candidates=candidates, current=current, sw_map=sw_map,
        strict_candidates=strict_candidates,
    )



__all__ = [
    "DEFAULT_CANDIDATES",
    "INDIRECT_CANDIDATES",
    "MultiWindowOptimizeResult",
    "WindowChoice",
    "WindowOptimizeResult",
    "optimize_axis_window",
    "optimize_direct_window",
    "optimize_direct_window_from_work",
    "optimize_indirect_windows",
    "optimize_indirect_windows_from_recon",
    "optimize_indirect_windows_from_work",
]
