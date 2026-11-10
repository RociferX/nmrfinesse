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
| Uniform 3D | [BMRB 15750](https://bmrb.io/data_library/summary/?bmrbId=15750) · [HNCO CSV](statistics/assigned-15750-hnco.csv) | 76 | 73 | 75 |
| Acquired 3D NUS | [BMRB 52533](https://bmrb.io/data_library/summary/?bmrbId=52533) · [HNCO CSV](statistics/assigned-52533-hnco.csv) | 97 | 90 | 88 |

The [assignment statistics](statistics/assigned-peak-comparison.json) record the matched residue
IDs and the local checks below.

### Why some assignments were missed

The uniform 2D spectrum recovers the same 108 assignments as the author spectrum. Its selected
F1 EM 10 Hz window separates Gly100 and His194 along N. The controlled NUS spectrum has one
broad peak in this region. See the [Gly100/His194 close-up](figures/gly100-peak-shape.png).

At 5%, four assignments appear in the author spectra but are not counted in the corresponding
automatic spectra. Local checks retain the same coordinates and tolerances, lower the detection
threshold and inspect whether an independent apex exists.

| Assignment | Author peak and processing check | Why the automatic spectrum missed it |
| --- | --- | --- |
| Ser93 · Controlled 2D NUS | Distinct author and automatic uniform peaks reach 6.24% and 5.66% of their respective maxima. | The strongest in-tolerance response is 2.55% of maximum, or 2.65 estimated noise standard deviations. No independent apex was found. |
| Gly100 · Controlled 2D NUS | The author and automatic uniform spectra both separate Gly100 and His194 along N. | One broad peak remains in the NUS spectrum; lowering the threshold does not reveal a second apex within tolerance. |
| Ile69 · Uniform 3D | The author apex reaches 6.45% of maximum. The automatic spectrum also has an independent apex at the expected position. | Its automatic height is 4.57% of maximum, below the 5% cutoff, and 32.7 estimated noise standard deviations. A local 4% check recovers it. |
| Ser71 · Uniform 3D | Distinct apexes occur in both spectra at nearly the same referenced position. | The normalized assignment distance is 0.930 in the author spectrum and 1.0013 in the automatic spectrum, just beyond the cutoff of 1. |

### Author processing and peak separation

The author spectra have narrower peaks and deeper valleys in some regions. The case sections
below identify the additional operations documented in the author files. LP extends a short FID
before windowing and can improve truncation artefacts and peak separation together; zero filling
mainly improves frequency-domain sampling. The automatic spectra use automatic windows without
LP, with independent apexes and linewidths evaluated separately.

## Uniform 2D

![Uniform 2D comparison](figures/uniform2d.png)

### Processing parameters

| Axis | Window | Baseline polynomial order |
| --- | --- | --- |
| F2 | SP, off 0.40, end 0.94, power 2 | 3 |
| F1 | EM, 10 Hz | 3 |

**Additional author processing.** The author enables forward LP on N (`ME_mod=2`, `NCOEF=32`,
`LPBIN=356`) from an acquisition with 90 complex indirect increments. Both axes then use the
squared-sine window (`WDW=4`, `SSB=2`, `FCOR=0.5`), with final `SI=2048/256` for F2/F1.
The narrower peaks and deeper valleys combine LP and windowing; the window alone does not
account for the full difference.

The direct dimension is extracted from 10.5 to 6.5 ppm. The processing record includes the
time-domain DC correction and the final transform script.

## Controlled 2D NUS

![Controlled 2D NUS comparison](figures/nus75.png)

### Processing parameters

| Axis | Window | Baseline polynomial order |
| --- | --- | --- |
| F2 | SP, off 0.45, end 0.98, power 1 | 3 |
| F1 | EM, 5 Hz | 2 |

SMILE reconstructs F1 from the supplied schedule. The final F2 window follows the reconstruction
route's SP setting. The indirect window is applied during finalization.

This case retains 68 of 90 complex increments (75.56%). The author reference uses the complete
90-increment acquisition and the F1 LP/window processing described under Uniform 2D. This
comparison therefore also includes sampling completeness and LP differences.

## Uniform 3D

![Uniform 3D projection comparison](figures/uniform3d.png)

### Processing parameters

F3 uses EM at 3 Hz. F2 uses SP with off 0.60, end 0.94 and power 1; F1 uses SP with
off 0.60, end 0.90 and power 2. The direct dimension is extracted from 10.0 to 6.0 ppm. The final script uses automatic zero filling and applies
time-domain DC correction. Spectrum-domain baseline correction is off for this case.

**Additional author processing.** Both indirect axes use `LP -fb` with a first-power SP window
(off 0.50, end 0.98). The direct axis uses second-power SP (off 0.50, end 1.00) and two phase
corrections, including a 43° first-order phase. The carbon axis is inverse-transformed and
processed again with LP, windowing and FT. LP and the tailored windows improve narrow peaks
and valleys; phase correction improves absorptive line shape. The script also applies baseline
and referencing corrections. A reference-axis translation does not increase resolution.

## Acquired 3D NUS

![Acquired 3D NUS projection comparison](figures/acquired3d.png)

### Processing parameters

F3 uses the reconstruction route's SP window (off 0.45, end 0.98, power 2). SMILE reconstructs
the indirect dimensions, which are finalized with F2 EM at 20 Hz and F1 EM at 5 Hz. Spectrum-domain baseline correction is off.

The author reference is a deposited spectrum without a corresponding processing script, so
the specific tailored processing operations are not established for this case.

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
