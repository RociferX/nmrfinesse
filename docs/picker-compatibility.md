# Peak-picker compatibility validation

## POKY/iPick concordance

Core mechanisms are similar and outputs are highly concordant in this batch. Thresholded local
maxima and per-axis three-point parabolic localization agree in all 24 matched-threshold tables
from 12 retained 2D positive HN spectra: 5175 within-table records uniquely match within one grid
step. This includes four reused equal-threshold tables, not 5175 independent physical peaks.
Coordinate differences are typically about 0.00025 ppm and at most about 0.00050 ppm, consistent
with iPick three-decimal output. Downstream availability agrees in 8084/8088 cells, with four
repeats of one member/run discrepancy. Historical 1.0.8/API1.1.4 and 1.0.9/API1.1.5 provenance is
retained; this is not a current-release spectral rerun. Threshold conversion uses median plus
T*1.4826*MAD for iPick's absolute threshold. Existing NMRFinesse calculations are unchanged.
See the [evidence package](evidence/picker-ipick-v1/README.md) and
[verification output](evidence/picker-ipick-v1/verification.txt).
