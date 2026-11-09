# NMRFinesse validation

## Automatic spectrum processing

The counts show matched pairs out of reference candidates. The 3D comparisons use HN, HC and NC projections.

| Processing route | Candidate matches | Comparison |
| --- | --- | --- |
| Uniform 2D | HN 121/126 | [Spectrum comparison](figures/uniform2d.png) |
| Controlled 2D NUS | HN 123/126 | [Spectrum comparison](figures/nus75.png) |
| Uniform 3D | HN 82/84, HC 74/81, NC 65/71 | [Projection comparison](figures/uniform3d.png) |
| Acquired 3D NUS | HN 89/89, HC 93/93, NC 79/79 | [Projection comparison](figures/acquired3d.png) |

## Peak-picking concordance with POKY/iPick

NMRFinesse and POKY/iPick's UCSFtool route use thresholded local maxima and per-axis three-point parabolic
localization. For positive 2D peaks at matched thresholds, candidate counts agreed in all 24 peak tables.
All 5,175 candidate entries had a unique counterpart within one grid step per axis. The typical coordinate
difference was about 0.00025 ppm and the maximum was about 0.00050 ppm.
