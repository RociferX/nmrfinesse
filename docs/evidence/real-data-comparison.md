# NMRFinesse validation

## How to read the figures

The automatically processed spectrum is on the left and the reference is on the right. Blue solid
contours show positive signal and red dashed contours show negative signal. Contours start at 7.5%
of each panel's maximum absolute intensity. Red dots mark detected candidates and purple crosses
mark unmatched reference candidates.

Candidates are picked independently at 10% of each spectrum's maximum absolute peak height after
median centring. The dominant sign is selected from the sum of squared candidate SNRs. Same-sign
candidates are matched one-to-one within a joint normalized distance of 1, using axis tolerances of
0.02 ppm for H, 0.20 ppm for N and 0.15 ppm for C. Whole-axis referencing preserves relative peak
positions. For 3D, both spectra are cropped to a common volume before generating signed
maximum-absolute-value HN, HC and NC projections. Each projection is picked and matched independently.

## Data and references

| Route | Comparison |
| --- | --- |
| Uniform 2D | Automatic processing of a uniform acquisition compared with its reference spectrum |
| Controlled 2D NUS | Controlled downsampling of a uniform acquisition, reconstructed and compared with the uniform reference |
| Uniform 3D | Automatic processing compared with a full 3D reference, evaluated through three projections |
| Acquired 3D NUS | Reconstruction of an acquired NUS schedule compared with a full 3D reference |

## Results overview

| Route | Matched reference candidates | Comparison statistics |
| --- | --- | --- |
| Uniform 2D | HN 121/126 | [JSON](statistics/uniform2d-comparison.json) |
| Controlled 2D NUS | HN 123/126 | [JSON](statistics/nus75-comparison.json) |
| Uniform 3D | HN 82/84, HC 76/81, NC 66/71 | [JSON](statistics/uniform3d-comparison.json) |
| Acquired 3D NUS | HN 89/89, HC 93/93, NC 79/79 | [JSON](statistics/acquired3d-comparison.json) |

Coverage is matched pairs divided by reference candidates. The results measure agreement between
detected lists. Candidate counts depend on overlap, line shape and the threshold. The same 3D
signal may appear in several projections, so projection counts cannot be summed as assigned peaks.

## Uniform 2D

![Uniform 2D comparison](figures/uniform2d.png)

The automatic spectrum has 129 HN candidates, of which 121 match the 126 reference candidates.
Median absolute differences among matches are H 0.00051 ppm and N 0.00926 ppm. Four of the five
unmatched reference positions reach the threshold locally without yielding a separate matched
candidate. One is below the threshold.

### Processing parameters

| Axis | Window | Baseline polynomial order |
| --- | --- | --- |
| F2 | SP, off 0.45, end 0.98, power 2 | 3 |
| F1 | SP, off 0.65, end 1.00, power 2 | 3 |

The direct dimension is extracted from 10.5 to 6.5 ppm. The processing record includes the
time-domain DC correction and the final transform script.

## Controlled 2D NUS

![Controlled 2D NUS comparison](figures/nus75.png)

The controlled example tests the reconstruction route against a uniform reference. Each spectrum
has 126 HN candidates and 123 match. Median absolute differences are H 0.00122 ppm and N
0.00723 ppm. One of the three unmatched reference positions reaches the threshold locally without a
separate candidate, and two are below the threshold.

### Processing parameters

| Axis | Window | Baseline polynomial order |
| --- | --- | --- |
| F2 | SP, off 0.45, end 0.98, power 1 | 3 |
| F1 | EM, 3 Hz | 2 |

SMILE reconstructs F1 from the supplied schedule. The final F2 window follows the reconstruction
route's SP setting. The indirect window is applied during finalization.

## Uniform 3D

![Uniform 3D projection comparison](figures/uniform3d.png)

| Projection | Automatic / reference candidates | Matched | Median absolute ppm differences |
| --- | --- | --- | --- |
| HN | 82 / 84 | 82 | H 0.00103, N 0.01398 |
| HC | 77 / 81 | 76 | H 0.00101, C 0.03087 |
| NC | 69 / 71 | 66 | N 0.01639, C 0.02770 |

Eight of the 12 unmatched projection entries involve nearby candidates competing for one-to-one
matches. Two have local responses below the detection threshold, and two have local responses
without independent candidates.

### Processing parameters

F3 uses SP with off 0.65, end 1.00 and power 2. F2 and F1 both use SP with off 0.45, end 0.90
and power 1. The direct dimension is extracted from 10.0 to 6.0 ppm. The final script uses automatic zero filling and applies
time-domain DC correction. Spectrum-domain baseline correction is off for this case.

## Acquired 3D NUS

![Acquired 3D NUS projection comparison](figures/acquired3d.png)

| Projection | Automatic / reference candidates | Matched | Median absolute ppm differences |
| --- | --- | --- | --- |
| HN | 94 / 89 | 89 | H 0.00031, N 0.00989 |
| HC | 98 / 93 | 93 | H 0.00028, C 0.00312 |
| NC | 84 / 79 | 79 | N 0.01068, C 0.00383 |

All reference candidates match in the three projections. The automatic spectra also contain five
additional candidates per projection under the same detection rule.

### Processing parameters

F3 uses the reconstruction route's SP window (off 0.45, end 0.98, power 2). SMILE reconstructs
the indirect dimensions, which are finalized with F2 EM at 10 Hz and F1 SP at off 0.65, end 1.00
and power 2. Spectrum-domain baseline correction is off.

## Automatic phase and transform encoding

The table gives the logical-axis zero-order phases applied in the automatic processing scripts.
All applied first-order phases are zero in these examples. These are processing settings in the
NMRPipe convention. Peak comparison uses the resulting spectra after whole-axis referencing.

| Route | F1 P0 | F2 P0 | F3 P0 | FT encoding in the final script |
| --- | --- | --- | --- | --- |
| Uniform 2D | 265° | 0° | — | F1 and F2 use FT |
| Controlled 2D NUS | 85° | 173.559° | — | F1 and F2 use FT |
| Uniform 3D | 2.5° | 267.5° | 15° | F1 uses FT -alt |
| Acquired 3D NUS | 0° | 182.5° | 107.969° | F1 uses FT -alt, F2 uses FT -alt -neg |

## Methods, records and reproduction

The [processing record](statistics/processing.json) contains the actual conversion and processing
scripts, applied phase and window settings, and selected scoring rows. The per-route JSON files
retain crop limits, offsets, tolerances, counts, coordinate differences and line-width measurements.
The [unmatched-candidate audit](statistics/local-response-audit.json) shows local responses and
the number of nearby automatic candidates at each unmatched reference position.

Use the [comparison tool](../../scripts/vm_projection_report.py) for candidate statistics and the
[figure tool](../../scripts/vm_four_path_figure.py) for contour overlays. The options for a repeat
comparison include all projections, the 10% height threshold, the dominant-sign rule and the
recorded axis offsets.

## Peak-picking concordance with POKY/iPick

NMRFinesse and POKY/iPick's UCSFtool route use thresholded local maxima and per-axis three-point
parabolic localization. At matched thresholds on 12 positive 2D HN spectra, candidate counts agree
in all 24 tables. All 5,175 candidate entries have a unique counterpart within one grid step per
axis. Coordinate differences are typically about 0.00025 ppm and at most about 0.00050 ppm, on the
scale of iPick's three-decimal output. Four equal-threshold tables reuse results.

The separate downstream availability check agrees in 8,084 of 8,088 cells. The four differences
repeat one member and run across four controls. This count measures downstream availability, while
the peak-table check measures candidate counts and coordinates.

[Peak-table statistics](ipick/table_comparison.csv) · [Candidate pairs](ipick/candidate_pairs.csv) ·
[Availability statistics](ipick/matching_comparison.csv) · [Verification script](ipick/verify_tables.py)

Download the `ipick` directory and run `python verify_tables.py` to verify file hashes, unique
candidate pairing, coordinate tolerances and availability totals.
