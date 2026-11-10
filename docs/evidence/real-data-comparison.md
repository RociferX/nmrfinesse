# NMRFinesse validation

## How to read the figures

The automatically processed spectrum is on the left and the author spectrum is on the right.
Blue contours show positive signal and red contours show negative signal. As in the Viewer, each
panel uses 12 logarithmically spaced levels starting at 8% of its positive maximum, or the
absolute negative maximum if there is no positive signal. The axes use the same scale per Hz.
The 3D figures show signed
maximum-absolute-value HN, HC and NC projections over the common volume. Assignment counts use
the full 3D spectra.

## Data and references

| Route | Comparison |
| --- | --- |
| Uniform 2D | Automatic processing of a uniform acquisition compared with its reference spectrum |
| Controlled 2D NUS | Controlled downsampling of a uniform acquisition, reconstructed and compared with the uniform reference |
| Uniform 3D | Automatic processing compared with a full 3D reference, evaluated through three projections |
| Acquired 3D NUS | Reconstruction of an acquired NUS schedule compared with a full 3D reference |

## Agreement with residue assignments

The reference coordinates come from the public BMRB assignments. HSQC uses H and N from the
same residue. HNCO combines H and N from residue *i* with the deposited carbonyl shift of
residue *i−1*. The HNCO comparison uses full 3D coordinates. Each spectrum is picked independently at 5% of its maximum absolute peak height after median
centring, using the dominant sign. Candidate peaks are matched one-to-one to assigned coordinates
in the common range, within a joint normalized distance of 1 (H 0.02 ppm, N 0.20 ppm, C 0.15 ppm).
For bsCopL, a whole-axis offset to the author spectrum was fitted on half the assigned residues;
55 of 56 held-out coordinates matched at the 5% threshold. The resulting offset is fixed for both
2D comparisons, with the established author-to-automatic referencing applied.

| Route | Assigned coordinates | Assignments in common range | Found in automatic spectrum | Found in author spectrum |
| --- | --- | --- | --- | --- |
| Uniform 2D | [BMRB 27493](https://bmrb.io/data_library/summary/?bmrbId=27493) · [HSQC CSV](statistics/assigned-27493-hsqc.csv) | 113 | 108 | 108 |
| Controlled 2D NUS | Same HSQC assignments | 113 | 107 | 108 |
| Uniform 3D | [BMRB 15750](https://bmrb.io/data_library/summary/?bmrbId=15750) · [HNCO CSV](statistics/assigned-15750-hnco.csv) | 76 | 74 | 75 |
| Acquired 3D NUS | [BMRB 52533](https://bmrb.io/data_library/summary/?bmrbId=52533) · [HNCO CSV](statistics/assigned-52533-hnco.csv) | 97 | 90 | 88 |

In the uniform 3D control, adding the F2 SP window was the only processing change. At a 5%
threshold, it reduced detected candidates from 193 to 116 while retaining the same 74 assigned
matches. The
[assignment statistics](statistics/assigned-peak-comparison.json) include the thresholds,
matched residue IDs and local checks below.

### Why some assignments were missed

The uniform 2D spectrum recovered the same 108 assignments as the author spectrum. The automatic
GM 8/15 window separates Gly100 and His194 along N; the SP control merges them. EM 3 Hz also
separates the pair. At 5%, GM and EM recovered the same 108 assignments, with 208 and 290
candidates respectively. See the [Gly100/His194 close-up](figures/gly100-peak-shape.png).

At 5%, three assignments were found in the author spectra and missed in their corresponding
automatic spectra. We checked the author peak apexes against separate processing of the same
acquisitions and searched the automatic spectra locally at a lower threshold with the same
coordinate tolerances.

| Assignment | Author peak and processing check | Why the automatic spectrum missed it |
| --- | --- | --- |
| Ser93 · Controlled 2D NUS | A distinct peak appears in both the author and automatic uniform spectra, at 6.24% and 6.04% of their maximum peak heights. | The strongest local response within tolerance is 2.45% of maximum and 2.6 times the estimated noise. No distinct apex was recovered in the local check. |
| Gly100 · Controlled 2D NUS | The author and automatic uniform spectra both separate Gly100 and His194 along N. | The NUS spectrum shows one broad peak in this region. Lowering the threshold did not reveal a second apex. |
| Ser71 · Uniform 3D | A distinct apex appears in both 3D spectra at nearly the same position after referencing. | Its distance to the deposited assignment is 0.930 in the author spectrum and 1.020 in the automatic spectrum, just beyond the cutoff of 1. |

The 5% threshold includes Glu199 in controlled 2D NUS and Phe14 in uniform 3D. With the same
NUS reconstruction, changing the F1 window left Glu199 at 7.87%–8.15% of the maximum. In uniform
3D, changing one window at a time left Phe14 below 10% in all tested settings. Its automatic peak
is 66 times the estimated noise.

## Uniform 2D

![Uniform 2D comparison](figures/uniform2d.png)

### Processing parameters

| Axis | Window | Baseline polynomial order |
| --- | --- | --- |
| F2 | SP, off 0.45, end 0.98, power 2 | 3 |
| F1 | GM, g1 8 Hz, g2 15 Hz | 3 |

The direct dimension is extracted from 10.5 to 6.5 ppm. The processing record includes the
time-domain DC correction and the final transform script.

## Controlled 2D NUS

![Controlled 2D NUS comparison](figures/nus75.png)

### Processing parameters

| Axis | Window | Baseline polynomial order |
| --- | --- | --- |
| F2 | SP, off 0.45, end 0.98, power 1 | 3 |
| F1 | EM, 3 Hz | 2 |

SMILE reconstructs F1 from the supplied schedule. The final F2 window follows the reconstruction
route's SP setting. The indirect window is applied during finalization.

## Uniform 3D

![Uniform 3D projection comparison](figures/uniform3d.png)

### Processing parameters

F3 uses SP with off 0.65, end 1.00 and power 2. F2 and F1 both use SP with off 0.45, end 0.90
and power 1. The direct dimension is extracted from 10.0 to 6.0 ppm. The final script uses automatic zero filling and applies
time-domain DC correction. Spectrum-domain baseline correction is off for this case.

## Acquired 3D NUS

![Acquired 3D NUS projection comparison](figures/acquired3d.png)

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

The [processing record](statistics/processing.json) contains the conversion and processing scripts,
phase and window settings, and selected scoring rows. The [assignment statistics](statistics/assigned-peak-comparison.json)
record the axis offsets, tolerances and residue IDs. The [figure tool](../../scripts/vm_four_path_figure.py)
draws the contour comparisons using the recorded offsets.

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
