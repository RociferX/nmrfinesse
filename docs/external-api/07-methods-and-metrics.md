# 07 · Methods and QC criteria (v1.1.6)

> This page describes what the software **executed** and what QC records were left. Any
> cross-combination or cross-condition statistic
> (statistical inference and scientific conclusions) are outside the scope of this software and are
> computed downstream from the unified peak table.

## 7.1 Reference workflow

1. `generate_fid`(bruker `-AUTO`/fid.com conversion) -> `generate_spectrum`.
   (NMRPipe pipeline + unified phase route; NUS go SMILE reconstruction);
2. Freeze the **reference spectrum** and **reference script** (`process.com`, with SHA-256),
   which provide the condition’s base for parameter combinations;
3. Reference peak position: the software selects peaks on the reference spectrum (threshold
   `sigma_multiplier` is set when **generating the reference**, default 35σ; API `sigma_multiplier=` /
   CLI `peaks --sigma`). Automatic axial screening requires compatible experiment/acquisition
   priors and evidence from many narrow, aligned candidates at original spectrum edges; it does
   not use a blanket edge margin. An explicit margin is a manual override. Peaks receive stable
   identities in row order `R0001…`;
   **The threshold is frozen with the reference**. A different threshold raises an error and
   requires explicit reference rebuilding;
4. Apply the single supported localisation method, a **three-point parabola**, and write
   `reference_peak_table_parabolic.csv`;
5. The reference is only used as a benchmark for parameter perturbation and does not claim global optimality.

## 7.2 parameter perturbation (workflow)

- `parameters_used` for each combination = effective parameter (base) of the conditional reference run + combination table coverage;
- Phase is locked at the reference value by default (direct dimension skips phase search, indirect dimension follows reference optimisation phase);
  Manual deviation is represented by `phase_delta.<axis>.p0|p1` (relative reference) or `phase.<axis>.p0|p1` (absolute value).
  The actual value is written into `phase.<axis>.actual_p0/actual_p1`;
- Reference mode imports, converts and merges the source segments. Combination mode processes only
  the existing reference FID; it does not reconvert automatically. A missing/damaged FID, mismatched
  source or conversion evidence, or parameters requiring conversion/merge raises an error and requires
  rebuilding the reference. Single-file FIDs, 3D uniform slice directories and merged multi-segment
  FIDs are supported. Candidate spectra are written to `study/workflows/<id>/<condition>/` and do not
  replace the active spectrum; see [FID reuse boundary](09-limitations-and-roadmap.md#99-frozen-fid-reuse);
- Phase/window function/zero filling/baseline/NUS parameters are all executed according to the table, and all parameters that affect the results are dropped in three layers

## 7.2b Sampling route: coverage and schedule order

Sampling is classified from supported metadata, the valid data grid and schedule order. Only a
standard `nuslist` or a file explicitly named by `acqus.NUSLIST` is used. A full grid in standard
order may use uniform processing; full coverage in another order still requires schedule-based
placement. Explicit NUS data with a missing schedule or unrecoverable positions is rejected at
import. Trailing zero padding is not counted as missing samples. API parameter-combination support
for 3D NUS remains limited as described in [09](09-limitations-and-roadmap.md).

## 7.3 Peak localisation: three-point parabola

| Method | Practice | Scope of application |
| --- | --- | --- |
| `parabolic` | Refine the detected maximum independently along each requested axis using the local three points | Any dimension; only method |

- **Reference mode**: refine each peak in the reference peak table and write one parabolic table;
- **Combination mode**: each combination first picks peaks independently on **its own
  candidate spectrum** with the reference-locked threshold, then refines them with the parabola.
  `reference_peak_id` stays blank in the peak table --
  matching peaks between combinations, and against the reference, is downstream work.

Localisation is a deterministic closed-form calculation, not an iterative fit. `boundary_hit`
marks a vertex offset at ±0.5 points. `fit_success` indicates whether a finite equivalent linewidth
could be calculated; it differs from the localisation record's `success` (which indicates that
localisation ran). `fallback` and `fallback_reason` remain compatibility fields and do not imply
an algorithm switch. Unsupported method requests such as `gaussian` or `both` raise an error.

Parabolic localisation needs only the local three-point neighbourhood on each axis. There is no
ROI size or iterative evaluation budget.

## 7.4 Peak selection threshold and margin (physical width caliber)

- Peak selection threshold = **Noise σ multiple** (`sigma_multiplier`, internally as `min_snr`):
  The reference mode is determined (default 35σ), the combination mode is **locked and inherited**, and is archived by workflow.
  `parameters_resolved.detection`(`source="reference(locked)"`);
- Default edge handling uses experiment/acquisition priors and evidence from many narrow, aligned
  peaks at the original spectrum edges. No unconditional edge band is excluded. An isolated edge
  peak, internal carrier peak, unknown experiment or uncertain crop boundary is retained. An
  explicit `edge_margin_ppm` or `edge_margin_points` is a manual override and is recorded apart
  from automatic screening;
- The conversion results are archived group by group: `run.json.window`(points/ppm/effective_ppm/
  Ppm_per_point/source) and `records/measurement.json`;
- The combination mode has no `max_peaks`; each workflow detects the peaks allowed by the
  reference-locked threshold. Reference measurements may use explicit search windows; these are
  not a blanket edge-exclusion rule. Automatic axial screening is separate and documented in
  [Peak picking](../peak-picking.md).
- Structural points (local maximum 3-point neighborhood, parabola +/-1 point) are not scaled -- they have nothing to do with resolution

Peak height, the selection threshold, S/N and reference measurements share the global median
background convention (`baseline_offset`, `height_reference="global_median_baseline"`). This is
not a spatial baseline correction and it does not change the spectrum. Automatic sign handling
follows the experiment template; phase-sensitive COSY/NOESY/ROESY retain both signs. For unknown or
low-confidence experiment types, strong evidence for both signs can be used as a fallback. An
explicit API request (`positive`, `negative`, `both` or `dominant`) takes precedence. The
low-level detector uses `sign_mode="auto"` by default.

### Baseline correction

- Time-domain DC correction uses `POLY -time` when diagnostics select `direct_poly_time`.
- Frequency-domain `mode=order` renders **`POLY -ord N -auto`**, selecting baseline points
  automatically before an Nth-order fit. Reference optimisation scores robust polynomial
  candidates in memory; the final script applies the corresponding baseline settings.
- `mode=auto` renders `POLY -auto` with the engine's default order.

### Reference window candidate scoring

Window selection has an FID-magnitude baseline stage and a phased complex-preview refinement.
The default baseline pool contains 13 candidates per axis: no window, six SP settings, two GM
settings (`g1/g2/g3/c = 8/15/0/1` and `4/8/0/1`) and four EM settings (`lb = 3, 5, 10, 20 Hz`).
Hz windows require a valid spectral width for the scored logical axis. Default selection chooses
among valid windows; no window remains a diagnostic reference and an explicit user choice.
Explicit lists are evaluated as supplied, without expansion or phased refinement, and select the
highest valid score. An entirely invalid explicit pool fails. NUS direct-axis processing retains
the reconstruction route's fixed SP window; explicit direct-axis candidates must also be SP.

FID baseline scoring first searches energy-leading traces at `12σ`. If fewer than four qualify,
deterministic supplementation uses energy rank and acquisition position. At most 256 traces are
probed and 12 shared traces are scored, subject to a 64 MiB FFT-cache budget. Only when no probed
trace qualifies at `12σ` does it try `6σ`. These weaker references require FWHM of at least two
points, adjacent samples at least half the peak height, and frequency support on five traces
(or all traces when fewer than five were scanned). Reference peaks must reach 25% of the
strongest significant peak on their trace. All candidates share references, traces and thresholds;
poor candidate responses are still included.

Direct FID trace scores multiply detection strength, separation, symmetry and sidelobe factors.
Detection equals SNR up to 60, then grows as `60 × (1 + ln(SNR/60))`. Indirect trace scores use
`min(detection/6, 1) × separation × sidelobe`, prioritizing sidelobes and peak valleys.
`raw_score` is the median of trace scores, including zeros. Component medians are recorded
separately and need not multiply to `raw_score`. The FID merge test considers pairs separated
by at most 1.5 times the smaller reference FWHM, with a reference valley at most 0.6 times the
smaller peak. A candidate is merged when its valley reaches 0.6 times the smaller candidate peak.
This stage uses `width_ratio = candidate_fwhm / min_valid_fwhm ≥ 1` and
`score = raw_score × width_ratio^-0.25` on every axis.

Phased 2D/3D refinement uses `score_profile=phased_global_window`. Uniform direct axes
(2D F2 and 3D F3) and indirect axes across the processing routes share this algorithm.
NUS indirect axes reuse the existing SMILE reconstruction. Strength and spatial coverage select
at most 128 orthogonal signal regions per axis, under a 64 MiB FFT-cache budget.
Noise is estimated over the full spectral width before scoring a requested crop. Reference peaks
must reach 8σ, 12% of the trace maximum and 3σ prominence. Regions have equal weight.
Measurements cover signed sidelobes, reference-peak retention, distinct neighbouring apices and
linewidth relative to the unwindowed reference. Sidelobes and widths use within-region medians
followed by the 80th percentile across regions; peak and pair retention use regional means.
Peak intensity does not weight the regional vote. Close pairs span at most five times the smaller
reference FWHM and have a reference valley at most 0.85 times the smaller peak. Candidates must
retain two distinct apices with a valley at most 0.995 times the smaller candidate peak.

The refined raw score is `peak_retention × sidelobe_factor × separation_factor`, where
`sidelobe_factor = 1 / (1 + 5 × (negative_lobe_ratio + 0.25 × positive_lobe_ratio))` and
`separation_factor = 0.25 + 0.75 × mean_regional_pair_retention`, or 1 when there are no reference pairs.
For `d = max(width_ratio - 1, 0)`, the resolution factor is `(1 + d + d²)^-w`, with `w=1` on
the direct axis and `w=0.25` on indirect axes. The final score remains
`score = raw_score × resolution_score`. Refinement adds SP onset `0.40/0.50/0.60`, endpoint
`0.90/0.94/0.98/1.00` and powers one/two. It adds no LP and does not rerun processing or
reconstruction for each candidate.

Without valid reference signal or a positive valid score, default optimization retains the
current/default settings and explicit candidate requests fail. Score attachments preserve
components, sampling and candidate diagnostics; peak tables remain at 38 columns. Rebuild frozen
references with `force=True` to use current selection. Scores rank candidates within the same
stage, axis and run. Fields and cache rules are documented in
[06 §6.1.1](06-outputs-and-records.md#611-reference-optimization-score-table).

### Axis effects are reported according to conditions

The same parameter may be completely different under different conditions (different data, different reference configurations). The software changes one by one.
(workflow, condition) Compare the candidate spectrum with SHA-256 of **the reference spectrum** of the condition: bit by bit identical and emitted.
`no_spectrum_change` Warning -- Formal plans should not treat this axis as a real perturbation under this condition.

`dominant` compares the squared signal-to-noise sums `Σ(SNR²)` for the two signs, rather
than counting candidates. Numerous weak opposite-sign candidates therefore have less influence
than strong main signals. Exact weight ties favour positive peaks; truly negative-dominated
spectra remain detectable. Normally processed single-sign spectra are expected to be positive.
For unknown types, automatic mixed-sign inference requires at least three candidates per sign,
a weaker-to-stronger weight ratio of at least 20%, and support beyond one isolated extreme
candidate on each side. Detection metadata `sign_evidence` records counts, normalised weights,
weight shares and the dominant sign.

## 7.5 Peak by Peak QC(drop table field)

| Field | Meaning |
| --- | --- |
| `detected` | Whether the peak is detected on the spectrum (combination mode: only the detected peaks are in the table -> constant true; refer to the peak table
Unmeasured reference peaks in tracking mode retain rows and `detected=false`) |.
| `intensity` / `SNR` | Signed peak height relative to the global median background and `\|height\|/σ` (σ = robust MAD noise) |
| `fit_success` / `FWHM_H` / `FWHM_N` / `boundary_hit` | Three-point parabolic localisation QC; the equivalent linewidth is a local-curvature estimate (`FWHM = 2.3548 sigma`, `sigma^2 = H/(2\|a\|)`) |
| `duplicate_localization` | The row shares its coordinates with another row of the same table (ppm to 1e-6): every row of a group is flagged true and no row is dropped; `peak_localization.parabolic.n_duplicate` counts extra rows and `run.json.warnings` gains `duplicate_localization` |
| `localization_requested` / `localization_method` | Requested method versus actual result: `parabolic` or `none` when not detected/skipped |
| `failure_reason` / `fallback_reason` | Independent localization failure reason versus actual fallback reason |
| `cell_low_*` / `cell_high_*` / `cell_edge` | Always NaN; joint multidimensional ownership cannot be represented by per-axis cell bounds |
| `search_bounds_by_axis` / `candidate_ownership_conflict` | Physical search intervals and ownership conflicts are separate audit fields |

`cell_edge` is always NaN in the current contract; physical search windows and ownership-conflict
audit are recorded separately. It is not a boolean boundary detector.

Reference-measurement `window_edge` describes a physical search-window boundary;
it does not imply that the peak is an artefact. `cell_edge` remains uncomputed (`NaN`).

Reference-measurement records may include additional location and boundary fields; the public
peak-table columns and meanings are listed in [outputs and records](06-outputs-and-records.md).

## 7.6 test/Detection aid (not included in the processing contract)

`nmrfinesse_api.uncertainty` (`position_uncertainty`, `uncertainty_summary`,
`PeakUncertainty`) is retained only as a test/detection aid. The processing pipeline does not call it
or write it to `records/`. It does not match peaks and its output is not a CSP detection floor or
significance threshold. Do not pass independent runs or unmatched peak tables to it. The utility is for:

- **Regression detection**: unchanged outputs can flag an ignored parameter for investigation,
  but zero dispersion alone does not prove a processing defect.
- **Regression/detection checks only**: it is not a downstream analysis method or scientific result.

```python
# Do not calculate a CSP floor from independent, unmatched peak-picking runs.
# Downstream analysis must match peaks using its own explicit criteria first.
```

Formal statistics and significance judgment should be completed according to your own assumptions in your analysis code.

## 7.7 Versions and Recalculability

Each record contains: software version (`core.__version__`), Python and key dependency versions, real machine registration.
NMRPipe/SMILE version, reference script and candidate script SHA-256, reference spectrum and candidate spectrum SHA-256.
Grid hash (`grid_sha256`), parameter three layers, window conversion record, complete log. With.
`records/manifest.json` + `workflows/<id>/` can be recalculated and checked.
