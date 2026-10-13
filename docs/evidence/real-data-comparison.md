# Four Processing Routes: 2D Spectra and 3D Projection Comparisons

This page presents final spectra produced by software 1.0.7 / API v1.1.3 under the current
processing workflow. All four cases were reprocessed from raw data, measured and plotted on
2026-10-14. Final phases were not manually overridden. The source and independence of each
reference are identified below.

## How to read the figures

NMRForge is on the left and the reference is on the right. Blue solid contours indicate positive
signals and red dashed contours indicate negative signals. In both panels, contours begin at 7.5%
of that spectrum's maximum absolute intensity. The 7.5% and 10% contours use 0.25 pt lines; higher
contours use 0.4 pt lines. Ordinary candidates are small red dots (`marker='.'`, `s=4`, no outline);
only unmatched reference candidates are marked with purple crosses. For 3D, the shared complete
volume is cropped first, then signed maximum-absolute-value HN, HC and NC projections are generated
and detected/matched independently. Same-sign HSQC/HNCO use `dominant`. Candidate detection uses
10% of each spectrum's maximum absolute peak height after centering on its median baseline. This is
separate from the internal window-scoring thresholds of 12σ/6σ.

**Reference-candidate coverage = matched pairs / reference candidates.** It is not recovery of
independently assigned true peaks. An unmatched candidate does not by itself mean a peak was lost,
and extra candidates are not automatically real peaks or noise. The two spectra are normalized
separately, so their absolute intensities cannot be compared. Only a constant whole-axis reference
translation documented in the records is applied; peaks are not shifted individually.

## Data and references

| Route | Input | Reference |
| --- | --- | --- |
| 2D uniform | BMRB 27493, `Apo_CBL_0.4mM/2`, 90 complex increments | Author Bruker `pdata/1` |
| Controlled 2D NUS | Same uniform raw data; 75% requested, 68/90 = 75.56%, seed 20261008 | Corresponding NMRForge uniform final spectrum from this run |
| 3D uniform | BMRB 15750 HNCO; complete 32×32 complex grid | Complete 3D spectrum rebuilt from the same raw data using the author's `fid.com`/`proc.com` unchanged |
| Acquired 3D NUS | BMRB 52533 HNCO; 441/(42×42) = 25% | Deposited `DomainIV_HNCO.ft3` |

Sources: [BMRB 27493](https://bmrb.io/data_library/summary/?bmrbId=27493),
[BMRB 15750](https://bmrb.io/data_library/summary/?bmrbId=15750), and
[BMRB 52533](https://bmrb.io/data_library/summary/?bmrbId=52533). The artificial 2D case is a
controlled downsampling of uniform raw data, not an acquired NUS experiment; the software and raw
source are shared by the comparison. The 15750 reference was independently processed with the
author's scripts; the 52533 reference is the deposited final spectrum. These comparisons do not
provide a complete independent peak-identity truth set.

## Results overview

Within the common windows, the main signal positions correspond, with no clear systematic loss of
major signals in these cases. This supports reliable routine processing for these examples. The
author's experiment-specific linear prediction, windows and phases can change weak features and
linewidths. Phase proximity, encoding agreement and resolution of the spectral-width conflict are
auditable processing strengths, but candidate coverage alone does not validate every weak peak or
all experiment types.

## 2D uniform: comparison with the author's Bruker spectrum

![2D uniform compared with the author's Bruker spectrum](evidence-uniform2d_20261014.png)

NMRForge detected 135 candidates and the author spectrum 126; 125 pairs matched. One unmatched
reference location has a local response but no independent detected candidate. The N dimension in
the new spectrum uses GM 4/8 Hz, unlike the author's window. Weak neighboring and side-lobe structure
and linewidth differences remain visible; extra candidates are not counted as new true peaks. A
constant whole-axis shift of H +0.072584594 and N +0.059775701 ppm follows the frozen strong-peak
anchor convention; the new figure was not refit to improve coverage.

| Projection | NMRForge / reference candidates | Matched / reference candidates | Median absolute position difference (ppm) |
| --- | --- | --- | --- |
| HN | 135 / 126 | 125/126 = 99.21% | H 0.00049; N 0.00759 |

Median local equivalent-linewidth ratio, NMRForge/reference, among matched candidates: HN H 0.94 / N
0.92. This is a local linewidth proxy in the figure, not an independent line-shape decomposition.

Automatic end-to-end processing took 33.102 s and produced a 512×1028 final spectrum.

[Comparison statistics and unmatched coordinates](2d-uniform-author-comparison_20261014.json);
[local-response audit](local-response-audit_20261014.json).

### Processing script and parameter comparison

The automatic script below is the actual final run. The table identifies logical-axis settings by
Bruker nucleus; axes not listed as selected retained normal processing defaults. The complete
commands below define what actually ran.

| Nucleus / logical axis | Window explicitly selected for this run |
| --- | --- |
| 1H / F2 | `{"c": 0.5, "end": 0.98, "off": 0.45, "pow": 2, "type": "sine_bell"}` |
| 15N / F1 | `{"c": 1.0, "g1": 4.0, "g2": 8.0, "g3": 0.0, "type": "gaussian"}` |

The author reference is Bruker `pdata/1` in the same source directory; WDW=4, SSB=2, LB=GB=0,
and H/N SI=2048/256. The PHC and NMRPipe PS conventions have not been mapped to one another, so
matching numbers are not treated as equivalent phases. The deposited spectrum was read directly;
the author's 2D processing was not rerun.

<details>
<summary>Show the actual automatic conversion and final-processing scripts for this case</summary>

**Automatic conversion**

```csh
#!/bin/csh

bruk2pipe -verb -in ./ser \
  -bad 0.0 -ext -aswap -AMX -decim 2088 -dspfvs 20 -grpdly 67.9876556396484  \
  -xN              2048  -yN               180  \
  -xT              1024  -yT                90  \
  -xMODE            DQD  -yMODE  Echo-AntiEcho  \
  -xSW         9578.544  -ySW         2187.227  \
  -xOBS         599.503  -yOBS          60.754  \
  -xCAR           4.771  -yCAR         118.077  \
  -xLAB 1H  -yLAB             15N  \
  -ndim               2  -aq2D         Complex  \
| nmrPipe -fn MULT -c 9.76562e-01 \
  -out ./d_001.fid -ov
```

**Automatic final processing**

```csh
#!/bin/csh
# NMRForge processing script
# experiment: d_001
xyz2pipe -in d_001.fid -x \
| nmrPipe -fn POLY -time \
| nmrPipe -fn SP -off 0.45 -end 0.98 -pow 2 -c 0.5 \
| nmrPipe -fn ZF -size 4096 \
| nmrPipe -fn FT \
| nmrPipe -fn PS -p0 0 -p1 0 -di \
| nmrPipe -fn POLY -ord 3 -auto \
| nmrPipe -fn EXT -x1 10.5ppm -xn 6.5ppm -sw -round 2 \
| nmrPipe -fn TP \
| nmrPipe -fn GM -g1 4 -g2 8 \
| nmrPipe -fn ZF -size 512 \
| nmrPipe -fn FT \
| nmrPipe -fn PS -p0 265 -p1 0 -di \
| nmrPipe -fn POLY -ord 3 -auto \
| nmrPipe -fn TP \
| pipe2xyz -out d_001.ft2 -x
```

</details>

<details>
<summary>Show the author's deposited parameters</summary>

**procs**

```text
##$BC_mod= 6
##$GB= 0
##$LB= 0
##$OFFSET= 12.68878
##$PHC0= 7.599999
##$PHC1= 0
##$SF= 599.5
##$SI= 2048
##$SSB= 2
##$SW_p= 9578.54406130266
##$WDW= 4
```

**proc2s**

```text
##$BC_mod= 0
##$GB= 0
##$LB= 0
##$OFFSET= 136.0028
##$PHC0= -2.4
##$PHC1= 0
##$SF= 60.74680744
##$SI= 256
##$SSB= 2
##$SW_p= 2187.22659667541
##$WDW= 4
```

</details>

## Controlled artificial 2D NUS: 75% requested, 75.56% actual

![Controlled artificial 2D NUS at 75% requested sampling](evidence-nus75_20261014.png)

The input was regenerated with `vm_make_evidence_nus.py`: 68 of the 90 full orthogonal increments
were retained, including the zero and terminal increments; retained data were not rewritten. The
new `ser` and `nuslist` hashes match the construction manifest. The dataset was reimported,
converted, and run through complete SMILE final processing. The H window was 10.5–6.5 ppm, with no
additional shift. NMRForge produced 126 candidates against 135 in the corresponding uniform
reference and matched 123 pairs. Of the 12 unmatched reference candidates, six had local responses
below 10%; six had local responses but no independent candidate within tolerance. Several locations
are near strong peaks, so shoulders, side lobes and resolution need to be considered; they cannot
all be classified as noise or lost peaks. The updated window in the uniform reference also changed
its candidate set, so the old reference denominator is not reusable.

| Projection | NMRForge / reference candidates | Matched / reference candidates | Median absolute position difference (ppm) |
| --- | --- | --- | --- |
| HN | 126 / 135 | 123/135 = 91.11% | H 0.00137; N 0.00441 |

Median local equivalent-linewidth ratio, NMRForge/reference, among matched candidates: HN H 0.91 / N
1.50. This is a local linewidth proxy in the figure, not an independent line-shape decomposition.

Automatic end-to-end processing took 17.066 s and produced a 256×1028 final spectrum.

[Comparison statistics and unmatched coordinates](controlled-2d-nus75-comparison_20261014.json);
[local-response audit](local-response-audit_20261014.json).

### Processing script and parameter comparison

The automatic script below is the actual final run. The table identifies logical-axis settings by
Bruker nucleus; axes not listed as selected retained normal processing defaults. The complete
commands below define what actually ran.

| Nucleus / logical axis | Window explicitly selected for this run |
| --- | --- |
| 1H / F2 | `Fixed NUS direct-dimension SP: off .45 / end .98 / pow 2 / c .5` |
| 15N / F1 | `{"c": 1.0, "lb": 5.0, "type": "exp"}` |

The reference is the corresponding uniform spectrum from this run, not an independent author
spectrum. The two spectra have different phases and windows. The default NUS direct-dimension score
is not described as the window actually selected for processing.

<details>
<summary>Show the actual automatic conversion and final-processing scripts for this case</summary>

**Automatic conversion**

```csh
#!/bin/csh

nusExpand.tcl -yT 90 -mode bruker -sampleCount 68 -avg -off 0 \
 -in ./ser -out ./ser_full -sample ./nuslist

bruk2pipe -verb -in ./ser_full \
  -bad 0.0 -ext -aswap -AMX -decim 2088 -dspfvs 20 -grpdly 67.9876556396484  \
  -xN              2048  -yN               180  \
  -xT              1024  -yT                90  \
  -xMODE            DQD  -yMODE  Echo-AntiEcho  \
  -xSW         9578.544  -ySW         2187.227  \
  -xOBS         599.503  -yOBS          60.754  \
  -xCAR           4.771  -yCAR         118.077  \
  -xLAB 1H  -yLAB             15N  \
  -ndim               2  -aq2D         Complex  \
| nmrPipe -fn MULT -c 9.76562e-01 \
  -out ./d_001.fid -ov
```

**Automatic final processing**

```csh
#!/bin/csh
# NMRForge 2D NUS SMILE reconstruction (two-stage)
# experiment: d_001
mkdir -p nus2d
# stage 1: direct dim (F2) FT + EXT + POLY, SMILE reconstruct F1
nmrPipe -in d_001.fid \
| nmrPipe -fn POLY -time \
| nmrPipe -fn SP -off 0.45 -end 0.98 -pow 1 -c 0.5 \
| nmrPipe -fn ZF -zf -size 4096 \
| nmrPipe -fn FT \
| nmrPipe -fn EXT -x1 10.5ppm -xn 6.5ppm -sw -round 2 \
| nmrPipe -fn PS -p0 173.559 -p1 -0 -di \
| nmrPipe -fn POLY -ord 3 -auto \
| nmrPipe -fn TP \
| nmrPipe -fn SMILE -nDim 2 \
           -sample nuslist -nThread 2 \
           -sampleCount 68 -nSigma 5 -off 0 0 -report 1 \
           -maxMem 11.8195 \
           -scaling 1 \
           -maxIter 300 \
           -xT 90 \
           -xP0 85 -xP1 0 \
           -thresh 0.95 \
| pipe2xyz -out nus2d/recon.ft1 -x -ov

# stage 2: indirect dim (F1) window + ZF + FT -alt + PS + POLY
nmrPipe -in nus2d/recon.ft1 \
| nmrPipe -fn EM -lb 5 \
| nmrPipe -fn ZF -size 256 \
| nmrPipe -fn FT \
| nmrPipe -fn PS -p0 85 -p1 0 -di \
| nmrPipe -fn POLY -ord 2 -auto \
| nmrPipe -fn TP \
  -out d_001.ft2 -ov
```

</details>

## 3D uniform: BMRB 15750 and the author's complete 3D script-reconstructed spectrum

![3D uniform BMRB 15750 comparison](evidence-uniform3d_20261014.png)

The raw `ser` is 16,777,216 bytes, consistent with a complete 32×32 complex grid and its orthogonal
components; the reference is not a stack of 2D slices. H/N/C reference shifts of +0.018999577,
+0.025001526 and +0.001007080 ppm come from same-nucleus spectrum-header CAR differences in this
run. There are 21 unmatched reference candidates across the three projections (some may recur
between projections; these are not 21 independent 3D peaks): 11 have local responses below 10%,
eight have candidate competition within tolerance, and two have local responses but no independent
candidate. The automatic spectrum has broader N and narrower H/C features; weak negative structure
and resolution differences are retained in the figure. The author's LP and specific windows help
weak structure, but this comparison did not isolate individual factors, so all improvements cannot
be attributed to LP.

| Projection | NMRForge / reference candidates | Matched / reference candidates | Median absolute position difference (ppm) |
| --- | --- | --- | --- |
| HN | 80 / 84 | 79/84 = 94.05% | H 0.00088; N 0.01671 |
| HC | 79 / 81 | 72/81 = 88.89% | H 0.00082; C 0.03183 |
| NC | 70 / 71 | 64/71 = 90.14% | N 0.01873; C 0.03074 |

Median local equivalent-linewidth ratios, NMRForge/reference, among matched candidates: HN H 0.67 / N
1.57; HC H 0.68 / C 0.75; NC N 1.59 / C 0.72. These are local linewidth proxies in the figure,
not independent line-shape decompositions.

Automatic end-to-end processing took 52.337 s and produced a 128×128×548 final spectrum.

[Comparison statistics and unmatched coordinates](3d-uniform-bmrb15750-comparison_20261014.json);
[local-response audit](local-response-audit_20261014.json).

### Processing script and parameter comparison

The automatic script below is the actual final run. The table identifies logical-axis settings by
Bruker nucleus; axes not listed as selected retained normal processing defaults. The complete
commands below define what actually ran.

| Nucleus / logical axis | Window explicitly selected for this run |
| --- | --- |
| 1H / F3 | `{"c": 1.0, "g1": 4.0, "g2": 8.0, "g3": 0.0, "type": "gaussian"}` |
| 15N / F2 | `Normal default; see the actual script` |
| 13C / F1 | `{"type": "none"}` |

The author used an H-dimension SP and two PS operations (3°/0° and −4°/43°), with indirect-dimension
LP and experiment-specific windows. NMRForge converted the original Bruker data and automatically
optimised phase, windows and baseline; it did not copy the author's final phases or LP scheme. The
carbon `SW_h` conflicted with `SW×SFO1`; NMRForge used 3636.364 Hz, matching the author's conversion.
This is the project's general spectral-width policy, not a dataset-specific exception.

<details>
<summary>Show the automatic conversion, automatic final-processing, and original author scripts</summary>

**Automatic conversion**

```csh
#!/bin/csh

bruk2pipe -verb -in ./ser \
  -bad 0.0 -ext -aswap -AMX -decim 1568 -dspfvs 20 -grpdly 67.9841461181641  \
  -xN              1024  -yN                64  -zN                64  \
  -xT               512  -yT                32  -zT                32  \
  -xMODE            DQD  -yMODE Echo-AntiEcho  -zMODE States-TPPI  \
  -xSW        12755.102  -ySW         2500.000  -zSW 3636.364  \
  -xOBS         850.104  -yOBS          86.150  -zOBS         213.795  \
  -xCAR           4.819  -yCAR         118.125  -zCAR         178.251  \
  -xLAB 1H  -yLAB             15N  -zLAB             13C  \
  -ndim               3  -aq2D         Complex                         \
| nmrPipe -fn MULT -c 1.95312e+00 \
| pipe2xyz -x -out ./fid/test%03d.fid -ov
```

**Automatic final processing**

```csh
#!/bin/csh
# NMRForge processing script
# experiment: d_001
xyz2pipe -in fid/test%03d.fid -x \
| nmrPipe -fn POLY -time \
| nmrPipe -fn GM -g1 4 -g2 8 \
| nmrPipe -fn ZF -size 2048 \
| nmrPipe -fn FT \
| nmrPipe -fn PS -p0 15 -p1 0 -di \
| nmrPipe -fn EXT -x1 10ppm -xn 6ppm -sw -round 2 \
| nmrPipe -fn TP \
| nmrPipe -fn SP -off 0.45 -end 0.95 -pow 1 -c 0.5 \
| nmrPipe -fn ZF -size 128 \
| nmrPipe -fn FT \
| nmrPipe -fn PS -p0 267.5 -p1 0 -di \
| nmrPipe -fn ZTP \
| nmrPipe -fn ZF -size 128 \
| nmrPipe -fn FT -alt \
| nmrPipe -fn PS -p0 2.5 -p1 0 -di \
| nmrPipe -fn TP \
| pipe2xyz -out d_001.ft3 -x
```

**fid.com**

```csh
#!/bin/csh

bruk2pipe -in ./ser -bad 0.0 -aswap -DMX -decim 1568 -dspfvs 20 -grpdly 67.9841461181641  \
  -xN              1024  -yN                64  -zN                64  \
  -xT               512  -yT                32  -zT                32  \
  -xMODE            DQD  -yMODE  Echo-AntiEcho  -zMODE    States-TPPI  \
  -xSW        12755.102  -ySW         2500.000  -zSW         3636.364  \
  -xOBS         850.104  -yOBS          86.150  -zOBS         213.795  \
  -xCAR           4.800  -yCAR         118.100  -zCAR         178.250  \
  -xLAB              H1  -yLAB             N15  -zLAB             C13  \
  -ndim               3  -aq2D          States                         \
  -out ./data/test%03d.fid -verb -ov

sleep 5
```

**proc.com**

```csh
#!/bin/csh

xyz2pipe -in  data/test%03d.fid -x  -verb           \
| nmrPipe  -fn POLY -time                           \
| nmrPipe  -fn SP -size 512 -off 0.5 -end 1.00 -pow 2 -c 0.5  \
| nmrPipe  -fn ZF -auto                             \
| nmrPipe  -fn FT                                   \
| nmrPipe  -fn PS -p0  3.0 -p1 0                    \
| nmrPipe  -fn PS -p0 -4  -p1 43.0 -di               \
| nmrPipe  -fn EXT -x1 10.0ppm -xn 6.0ppm -sw       \
| pipe2xyz -out data/test%03d.ft3 -x -ov

xyz2pipe -in data/test%03d.ft3 -z -verb               \
| nmrPipe  -fn SP -off 0.5 -end 0.98 -pow 1 -c 0.5  \
| nmrPipe  -fn ZF -auto                             \
| nmrPipe  -fn FT -alt                              \
| nmrPipe  -fn PS -p0 0.0 -p1 0.0 -di               \
| pipe2xyz -out data/test%03d.ft3 -z -inPlace

xyz2pipe -in data/test%03d.ft3 -y -verb               \
| nmrPipe  -fn LP -fb                               \
| nmrPipe  -fn SP -off 0.5 -end 0.98 -pow 1 -c 1.0  \
| nmrPipe  -fn ZF -auto                             \
| nmrPipe  -fn FT                                   \
| nmrPipe  -fn PS -p0 -90 -p1 0 -di                   \
| nmrPipe  -fn POLY -auto -ord 0                    \
| nmrPipe  -fn TP                                   \
| nmrPipe  -fn POLY -auto -ord 0                    \
| pipe2xyz -out data/test%03d.ft3 -y -inPlace

xyz2pipe -in data/test%03d.ft3 -z -verb               \
| nmrPipe  -fn HT  -auto                            \
| nmrPipe  -fn PS  -inv -hdr                        \
| nmrPipe  -fn FT  -inv                             \
| nmrPipe  -fn ZF  -inv                             \
#| nmrPipe  -fn LP -pred 32 -ord 8                   \
| nmrPipe  -fn LP -fb                               \
| nmrPipe  -fn SP  -hdr                             \
| nmrPipe  -fn ZF  -auto                            \
| nmrPipe  -fn FT                                   \
| nmrPipe  -fn PS  -hdr -di                         \
| nmrPipe  -fn CS  -ls 3.0ppm   -sw                   \
| nmrPipe  -fn POLY -auto -ord 0                    \
| pipe2xyz -out data/test%03d.ft3 -z -inPlace

xyz2pipe -in ./data/test%03d.ft3  -y -verb  \
  > ./hnco.ft3
```

</details>

## Acquired 3D NUS: BMRB 52533 and the deposited complete final spectrum

![Acquired 3D NUS BMRB 52533 comparison](evidence-acquired3d_20261014.png)

The acquired schedule contains 441 points on a 42×42 complex grid (25% sampling); the `ser` and
`nuslist` hashes are unchanged. All reference candidates matched in the three projections, with no
additional shift. The automatic spectrum still has extra candidates and linewidth/weak-structure
differences. 100% projection-candidate coverage does not establish complete 3D peak identities or
the absence of reconstruction artefacts. This is acquired NUS data; the retired artificial 3D case
is not used.

| Projection | NMRForge / reference candidates | Matched / reference candidates | Median absolute position difference (ppm) |
| --- | --- | --- | --- |
| HN | 95 / 89 | 89/89 = 100.00% | H 0.00033; N 0.00946 |
| HC | 99 / 93 | 93/93 = 100.00% | H 0.00029; C 0.00317 |
| NC | 91 / 79 | 79/79 = 100.00% | N 0.01006; C 0.00335 |

Median local equivalent-linewidth ratios, NMRForge/reference, among matched candidates: HN H 0.95 / N
0.76; HC H 0.94 / C 0.78; NC N 0.75 / C 0.77. These are local linewidth proxies in the figure,
not independent line-shape decompositions.

Automatic end-to-end processing took 235.346 s and produced a 256×256×1176 final spectrum.

[Comparison statistics and unmatched coordinates](acquired-3d-bmrb52533-comparison_20261014.json);
[local-response audit](local-response-audit_20261014.json).

### Processing script and parameter comparison

The automatic script below is the actual final run. The table identifies logical-axis settings by
Bruker nucleus; axes not listed as selected retained normal processing defaults. The complete
commands below define what actually ran.

| Nucleus / logical axis | Window explicitly selected for this run |
| --- | --- |
| 1H / F3 | `Fixed NUS direct-dimension SP: off .45 / end .98 / pow 2 / c .5` |
| 15N / F2 | `{"c": 1.0, "g1": 4.0, "g2": 8.0, "g3": 0.0, "type": "gaussian"}` |
| 13C / F1 | `{"type": "none"}` |

The reference reads the deposited `DomainIV_HNCO.ft3` directly. The author's `conv_smile.com` shown
below is method provenance; it was not run to regenerate or alter the deposited spectrum. SMILE/FT
encoding can be compared across the scripts. Automatic indirect phases are passed to SMILE and agree
with the final PS operations; peaks were not aligned individually.

<details>
<summary>Show the actual automatic conversion, automatic final-processing, and author scripts</summary>

**Automatic conversion**

```csh
#!/bin/csh

nusExpand.tcl -zT 42 -yT 42 -mode bruker -sampleCount 441 -avg -off 0 \
 -in ./ser -out ./ser_full -sample ./nuslist

bruk2pipe -verb -in ./ser_full \
  -bad 0.0 -ext -aswap -AMX -decim 1792 -dspfvs 20 -grpdly 67.9841766357422  \
  -xN              2048  -yN                84  -zN                84  \
  -xT              1024  -yT                42  -zT                42  \
  -xMODE            DQD  -yMODE States-TPPI  -zMODE States-TPPI  \
  -xSW        11160.714  -ySW         2269.632  -zSW         2816.901  \
  -xOBS         799.864  -yOBS          81.059  -zOBS         201.160  \
  -xCAR           4.773  -yCAR         117.084  -zCAR         176.207  \
  -xLAB 1H  -yLAB             15N  -zLAB             13C  \
  -ndim               3  -aq2D         Complex  \
| nmrPipe -fn MULT -c 1.95312e+00 \
  -out ./d_001.fid -ov
```

**Automatic final processing**

```csh
#!/bin/csh
# NMRForge 3D NUS SMILE reconstruction
# experiment: d_001
mkdir -p nus3d_1 nus3d_rc
# step 1: direct dim (F3) FT + EXT + PS
xyz2pipe -in d_001.fid -x \
| nmrPipe -fn SP -off 0.45 -end 0.98 -pow 2 -c 0.5 \
| nmrPipe -fn ZF -zf -size 4096 \
| nmrPipe -fn FT \
| nmrPipe -fn EXT -x1 10ppm -xn 6ppm -sw -round 2 \
| nmrPipe -fn PS -p0 107.969 -p1 -0 -di \
| pipe2xyz -out nus3d_1/test%04d.ft1 -z

# step 2: SMILE reconstruct indirect dims (F2/F1)
xyz2pipe -in nus3d_1/test%04d.ft1 -x \
| nmrPipe -fn SMILE -nDim 3 \
           -sample nuslist -nThread 2 \
           -sampleCount 441 -nSigma 5 -off 0 0 -report 1 \
           -maxMem 10.0464 \
           -scaling 1 \
           -maxIter 1500 \
           -xP0 182.5 -xP1 0 \
           -yP0 0 -yP1 0 \
           -xAlt -xNeg \
           -yAlt \
           -thresh 0.95 \
| pipe2xyz -out nus3d_rc/test%04d.ft1 -x

# step 3: indirect dims (F2/F1) window + ZF + FT + PS
xyz2pipe -in nus3d_rc/test%04d.ft1 -x \
| nmrPipe -fn GM -g1 4 -g2 8 \
| nmrPipe -fn ZF -size 256 \
| nmrPipe -fn FT -alt -neg \
| nmrPipe -fn PS -p0 182.5 -p1 0 -di \
| nmrPipe -fn TP \
| nmrPipe -fn ZF -size 256 \
| nmrPipe -fn FT -alt \
| nmrPipe -fn PS -p0 0 -p1 0 -di \
| nmrPipe -fn TP \
| nmrPipe -fn ZTP \
| pipe2xyz -out d_001.ft3 -x
```

**Author `conv_smile.com`**

```csh
#!/bin/csh

set CONVERSION = y
set PROCESSING_1 = y
set RECONSTRUCTION = y
set PROCESSING_23 = y
set PROJECTIONS = y



if ($CONVERSION == 'y') then

nusExpand.tcl -mode bruker -sampleCount 441 -off 0 \
 -in ./ser -out ./ser_full -sample ./nuslist

bruk2pipe -verb -in ./ser_full \
  -bad 0.0 -ext -aswap -AMX -decim 1792 -dspfvs 20 -grpdly 67.9841766357422  \
  -xN              2048  -yN                84  -zN                84  \
  -xT              1024  -yT                42  -zT                42  \
  -xMODE            DQD  -yMODE    States-TPPI  -zMODE    States-TPPI  \
  -xSW        11160.714  -ySW         2269.632  -zSW         2816.901  \
  -xOBS         799.864  -yOBS          81.059  -zOBS         201.160  \
  -xCAR           4.773  -yCAR         117.084  -zCAR         176.207  \
  -xLAB              HN  -yLAB             15N  -zLAB              CO  \
  -ndim               3  -aq2D         Complex                         \
| nmrPipe -fn MULT -c 1.95312e+00 \
| pipe2xyz -x -out ./fid/test%03d.fid -ov




  echo "Expansion & conversion done..."

endif

if ($PROCESSING_1 == 'y') then

echo "Processing Direct dimension..."

xyz2pipe -in ./fid/test%03d.fid -x                    \
| nmrPipe  -fn POLY -time                             \
| nmrPipe  -fn SP -off 0.4 -end 0.98 -pow 2 -c 0.5    \
| nmrPipe  -fn ZF -auto                         \
| nmrPipe  -fn FT                                     \
| nmrPipe  -fn EXT -x1 10ppm -xn 6ppm -sw -round 2  \
| nmrPipe  -fn PS -p0 -73.0 -p1 0.0 -di                 \
#| nmrPipe  -fn POLY -auto   \
| pipe2xyz -out ft1/test%04d.ft1 -z -verb

echo "Direct dimension processing done..."

endif

if ($RECONSTRUCTION == 'y') then
date
echo "Starting reconstruction..."

xyz2pipe -in ft1/test%04d.ft1 -x                           \
| nmrPipe  -fn SMILE -nDim 3 -sample nuslist -nThread 40   \
           -sampleCount 441 -nSigma 5 -off 0 -report 2		\
           -xCT 42 -xAlt -xNeg -yAlt -xQ3 2 -yQ3 2                                    \
| pipe2xyz -out ft1/rc%04d.ft1 -x

endif

if ($PROCESSING_23 == 'y') then

xyz2pipe -in ft1/rc%04d.ft1 -x                        \
| nmrPipe  -fn ZF -auto                         \
| nmrPipe  -fn FT -alt -neg                                     \
| nmrPipe  -fn PS -p0 0 -p1 0 -di                     \
| nmrPipe  -fn TP                                     \
| nmrPipe  -fn ZF -auto                         \
| nmrPipe  -fn FT -alt                                    \
| nmrPipe  -fn PS -p0 0 -p1 0 -di                     \
| nmrPipe  -fn TP                                     \
| nmrPipe  -fn ZTP                                    \
| pipe2xyz -out ft/DomainIV_HNCO_%03d.ft3 -x

proj3D.tcl -in ft/DomainIV_HNCO_%03d.ft3

endif

xyz2pipe -verb -in ft/DomainIV_HNCO_%03d.ft3 -x  \
|  nmrPipe -ov -out DomainIV_HNCO.ft3
```

</details>

## Automatic phase and encoding checks

Phases are compared modulo 360°. For same-sign multidimensional spectra, adding 180° jointly to H and
N is a sign-equivalent transformation; the comparison does not independently choose a favourable
180° difference for each axis. The artificial 2D case and this run's uniform spectrum have H/N
residuals of 6.441°/0° after the joint equivalence. The 15750 N/C residuals are each 2.50°. For
15750 H, NMRForge used 15°/0° and the author used −1°/43°, so P1 differs. Both PS operations were
applied to the same complex Fourier-transformed data: the rotation residual in the shared H window
was −2.06° to +9.28°, and 3.61° near 8 ppm. The parameters themselves are not equal. For 52533, the
H/N/C residuals after the joint H/N equivalence are 0.969°/2.50°/0°. Bruker PHC and NMRPipe PS have
not been mapped to a common convention, so no misleading cross-software angle error is reported.
The 15750 carbon `FT -alt`, 52533 nitrogen `-alt -neg`, carbon `-alt`, and Echo–AntiEcho conversion
are checked against the actual scripts rather than applying ALT/NEG mechanically.
[This run's phase check](phase-and-encoding-comparison_20261014.json) records original values,
equivalent transformations and phase-operator results.

## Methods, records and reproduction

Matching uses same-sign candidates, H/N/C tolerances of 0.02/0.20/0.15 ppm, a normalized joint
distance ≤1, and a nearest-first one-to-one greedy assignment. For 3D, the common complete volume is
cropped first. The source was software 1.0.7 / API 1.1.3; each case was run once, with automatic
phase selection by axis followed by ordinary baseline/window scoring and a complete final run.
The default window pool contains no window, five SP, two GM and two EM candidates. The internal 6σ
fallback is used only when 12σ reference selection finds no eligible reference; it does not change
the 10% display-detection threshold used on this page. NUS keeps the direct SP fixed by default.
The gated lightweight P0 seed may be used at the first 2D NUS reconstruction; it is not used for 3D.
Statistics did not change processing parameters, thresholds or individual peak coordinates.

[Construction manifest](controlled-nus75-construction_20261014.json),
[processing provenance](processing-provenance_20261014.json), and
[the four actual scripts](script-comparisons_20261014.json) record versions, input/final-spectrum
hashes, optimization outcomes and executed commands. Displayed script paths were made relative;
the SHA-256 hashes of the original executed scripts remain in the records, and final-spectrum bytes
were not changed. For ordinary reproduction, use each case's original Bruker directory:

```python
from nmrforge_api import open_study, add_dataset, build_reference
study = open_study("new-evidence-project")
dataset = add_dataset(study, "raw/experiment", condition="A")
reference = build_reference(study, dataset, params={
    "ext_lo": "10.5", "ext_hi": "6.5",
    "final_ext_lo": "10.5", "final_ext_hi": "6.5", "apply_ext_to_opt": True,
})
```

For both 3D cases, use an H window of 10–6 ppm. The 15750 reference was generated by running the
deposited `fid.com`/`proc.com` unchanged; the acquired NUS reference reads the deposited FT3. For the
artificial input, first run:

```bash
python scripts/vm_make_evidence_nus.py raw/uniform raw/nus75 --fraction .75 --seed 20261008
python scripts/vm_projection_report.py --spectrum automatic.ft3 --reference author.ft3 --pairs all --min-height-fraction .10 --sign-mode dominant --json comparison.json
python scripts/vm_four_path_figure.py --case "3D comparison,automatic.ft3,author.ft3" --projection all --mark-peaks --peak-height-fraction .10 --peak-marker-size 4 --peak-sign-mode dominant --out comparison.png
```

The commands above should also receive the whole-axis reference shifts documented on this page.
Use the actual scripts and provenance JSON for complete parameters and selected windows. These
results support routine processing reliability in these cases; they do not replace independent
assigned-peak truth, complete 3D identity validation or scientific acceptance of all weak peaks.
