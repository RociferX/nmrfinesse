# NMRFinesse validation

## Automatic spectrum processing

The counts show matched pairs out of reference candidates. The 3D comparisons use HN, HC and NC projections.

| Processing route | Candidate matches | Figure | Statistics |
| --- | --- | --- | --- |
| Uniform 2D | HN 121/126 | [Spectra](figures/uniform2d.png) | [JSON](statistics/uniform2d-comparison.json) |
| Controlled 2D NUS | HN 123/126 | [Spectra](figures/nus75.png) | [JSON](statistics/nus75-comparison.json) |
| Uniform 3D | HN 82/84, HC 74/81, NC 65/71 | [Projections](figures/uniform3d.png) | [JSON](statistics/uniform3d-comparison.json) |
| Acquired 3D NUS | HN 89/89, HC 93/93, NC 79/79 | [Projections](figures/acquired3d.png) | [JSON](statistics/acquired3d-comparison.json) |

[Processing parameters and scripts](statistics/processing.json) · [Unmatched-candidate checks](statistics/local-response-audit.json)

## Peak-picking concordance with POKY/iPick

NMRFinesse and POKY/iPick's UCSFtool route use thresholded local maxima and per-axis three-point parabolic
localization. For positive 2D peaks at matched thresholds, candidate counts agreed in all 24 peak tables.
All 5,175 candidate entries had a unique counterpart within one grid step per axis. The typical coordinate
difference was about 0.00025 ppm and the maximum was about 0.00050 ppm.

[Peak-table statistics](ipick/table_comparison.csv) · [Candidate pairs](ipick/candidate_pairs.csv) · [Verification script](ipick/verify_tables.py)
