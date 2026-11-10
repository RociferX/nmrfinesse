# Processing model

The desktop and scripting API use Bruker readers, workflow orchestration and the NMRPipe/SMILE
backend. The desktop exposes import, Generate FID, Generate Spectrum and peak picking; the API
separates reference construction from parameter-combination execution.

## Data understanding

| Decision | Input and implementation |
| --- | --- |
| Dimensionality | `PARMODE` and acquisition-file availability in `core/data/bruker_reader.py` |
| Logical axes and nuclei | `NUC1`, `TD`, `SFO1`, offsets, acquisition order and quadrature metadata |
| Sweep width | `resolve_sweep_width`: compare `SW_h` with `SW × SFO1`, retain adopted value/source and raw metadata |
| FT mode, ALT and NEG | `core/experiment/acquisition_mode_detector.py` with per-axis FnMODE/mode evidence |
| Experiment type | Pulse program, nucleus combination, dimension order and acquisition parameters; templates in `nmrfinesse_data/presets/` |
| Sampling | `core/experiment/sampling_detector.py` and `core/data/nus_reader.py`: schedule, grid, data layout and acquisition evidence |

NUS schedules come from standard `nuslist` or `acqus.NUSLIST`; arbitrary integer files are not
discovered as schedules. Full coverage in standard order can use uniform processing; reordered
coverage still requires schedule placement. Explicit NUS without recoverable positions is rejected.
Trailing storage padding is not an unsampled increment. Unsupported kinetic/pseudo-dimension
layouts are filtered before ordinary multidimensional processing.

## Import and FID generation

`workflow.stepwise` binds processing to a project experiment/data entry. Import records the source,
copies data into the project and writes metadata. Segmented input preserves source order and checks
acquisition compatibility before conversion/merge.

Generate FID calls `backend.convert_to_fid`. Conversion interprets Bruker physical row lengths,
quadrature modes and acquisition order; declared TD, NMRPipe real/complex counts and logical grid
sizes are distinct quantities. Automatic conversion may produce a single FID or supported plane
layout. Manual conversion overrides apply through the same backend boundary.

Direct-data diagnostics run at the end of FID generation and write `process/diagnostics.json`.
They report DC offset, non-finite values, blank/high-energy traces and bad-point evidence. Applied
repairs retain backups and audit records. `segment_shift_hz` is a user-provided conversion-time
shift, with the first segment at 0 Hz; the software does not estimate it automatically.
Spectrum processing reuses matching diagnostics; missing/stale evidence triggers a fallback check.

## Plans, execution and caches

`ProcessingPlan` carries method choices, rationale, confidence and a `ProcessingDag`.
The DAG validates dependencies and supplies topological execution order. `PipelineRunner` provides
node/cache execution for the graph-based entry point. The desktop's unified optimisation route is
explicitly orchestrated in `workflow/phase_routes.py`; its phase/reconstruction caches are not an
unconditional promise to reuse every spectrum or reconstruction after a parameter change.

Reference caching and combination resume are separate API mechanisms. Their fingerprints bind
normalised requests, condition inputs, parameters and frozen conversion evidence. A missing or
changed reference FID requires explicit reference rebuilding rather than conversion on demand.

## Uniform automatic route

`unified_route()` chooses indirect axes before the direct axis. For each phase-sensitive axis,
the backend produces a complex preview: the searched axis retains its imaginary component,
while already fixed axes use their selected phases. The search operates on that preview in memory.
After the direct phase is fixed, indirect phases are revisited with the direct correction applied.
Magnitude experiments skip automatic phase search according to their template.

```text
converted FID + diagnostics
  -> per-axis complex previews and phase search
  -> indirect-axis review after direct phase selection
  -> joint spectrum with selected phases and automatic zero filling
  -> baseline scoring
  -> direct-window scoring from FID
  -> indirect-window scoring from FID
  -> complete final backend run
  -> spectrum QC and registered products
```

Baseline candidates are evaluated before window candidates. FID scoring supplies a direct-axis
baseline window. Phase-sensitive uniform 2D and 3D then use one shared complex direct-axis preview
for phased line-shape comparison. Indirect-axis scoring emphasizes sidelobes and separation. The route supplies resolved
baseline, windows and automatic zero-fill settings to the final script. If a scoring stage cannot
evaluate its inputs, its logged fallback retains available settings instead of inventing a result.

## NUS automatic route

`_unified_nus()` first calls SMILE reconstruction, retains reconstruction data for phase evaluation,
and evaluates indirect phases with an in-memory equivalent of the finalisation chain. The direct
phase is searched using a real finalised spectrum and Hilbert-transform quadrature. Indirect phases
are then reviewed with the direct correction applied.

For **2D NUS only**, a lightweight P0 seed may be estimated before the first reconstruction from
the zero-indirect-increment quadrature pair. Layout/confidence checks gate acceptance. Subsequent
search applies residual correction without adding the seed twice; the seed is bound into the
phase-cache evidence. This initialisation does not search P1 and is not applied to 3D NUS.

```text
converted FID + diagnostics
  -> optional gated 2D P0 seed
  -> first SMILE reconstruction
  -> indirect-phase search, direct-phase search, indirect review
  -> joint finalisation for baseline scoring
  -> baseline and window parameter selection
  -> complete reconstruction and finalisation with selected parameters/phases
  -> spectrum QC and registered products
```

SMILE requires the direct SP window. Its optimiser does not replace that direct window with no
window, Gaussian or exponential weighting. Indirect window candidates use reconstruction-plane
information. Final direct phase goes into the corresponding PS command; final indirect phases are
passed to SMILE and remain consistent with subsequent PS. The result is a full final run, rather
than a display-only rotation of preview planes.

API reference construction accepts `optimization_candidates`. Each explicit list replaces its
corresponding default pool, and the highest-scoring valid candidate is applied in the final run.
Explicit NUS direct-dimension candidates must use SP; the selected SP configuration is applied
in the full reconstruction. Unspecified stages/directions retain defaults. An entirely invalid
pool raises an error instead of falling back. Reference score CSV rows record scores and application.

The default pool has 13 candidates per axis, comprising no window, six SP settings, two GM
settings (`g1/g2/g3/c = 8/15/0/1` and `4/8/0/1`) and four EM settings (`lb = 3, 5, 10, 20 Hz`).
Hz-based candidates require a valid spectral width for the scored axis. Default selection favours
a valid window on every axis. No window is retained as a diagnostic reference and an explicit user choice.

Direct-axis FID scores combine detection, separation, symmetry and sidelobe factors. Detection
strength grows linearly up to SNR 60 and logarithmically above it. Indirect scores prioritize
sidelobes and peak valleys, using `sidelobe * separation * min(detection/6, 1)` per trace.
The median trace score is multiplied by `width_ratio^-0.25`, where
`width_ratio = candidate_fwhm / min_valid_fwhm` and is at least 1.

Phase-sensitive 2D and 3D axes share a signed complex-preview refinement. It samples distinct
orthogonal signal regions by strength and spatial coverage, with at most 128 regions and a
64 MiB FFT-cache budget. Noise is estimated over the full spectral width before scoring the
requested crop. Regions have equal weight. Negative/positive sidelobes and linewidth
use the 80th percentile across regions; reference-peak and close-pair retention use regional
retention rates. An exceptionally strong peak therefore does not weight the score by intensity.
Neighbour spans scale with reference linewidth and include already well-separated, unequal-height
pairs. Linewidth is compared with the shared unwindowed reference. For broadening `d = max(width_ratio - 1, 0)`,
the resolution factor is `(1 + d + d²)^-w`, with `w=1` on the direct axis and `w=0.25` on indirect
axes. Larger broadening incurs a continuously increasing cost; indirect axes retain their
emphasis on sidelobes and peak connections. SP refinement searches onset `0.40/0.50/0.60`, endpoint
`0.90/0.94/0.98/1.00` and powers one/two. It adds no LP. Candidates share one complex preview
per axis, and NUS indirect axes use the existing SMILE reconstruction. Default NUS direct-axis
processing retains the reconstruction route's SP window. Explicit pools are not expanded and
retain their highest-valid-score rule.

FID scoring probes at most 256 traces and formally scores at most 12 shared representative
traces under an FFT-cache limit. The fast path looks for references at `12σ`; only if none qualify
does it try `6σ` references with a supported line profile and frequency support on five traces (or
all traces when fewer than five were scanned). Candidates share reference peaks and traces, including
traces with zero score when no valid shared peak is present. If no qualifying reference trace exists,
default optimization keeps the current/default settings and an explicit candidate request fails.
Scoring diagnostics, including the per-component and resolution terms, are recorded in the
53-column `optimization_scores.csv`; the API peak table remains 38 columns. Older valid CSVs are
reused as-is and can retain fewer columns until the reference is rebuilt with `force=True`.

## Ranges, phases and manual execution

`final_ext_lo`/`final_ext_hi` set the final direct-dimension window. The optimisation-range switch
decides whether this window also applies to previews/scoring. When the final range changes, direct
P1 is renormalised to the final window width. Axis identity, units and applied range are recorded.
Single-sign templates resolve the 180-degree ambiguity; mixed-sign templates preserve physical
positive/negative signals. Magnitude templates skip phase optimisation.

`phase_route="none"` calls the backend without unified phase optimisation. The manual route
exposes conversion/spectrum scripts through `workflow.manual`, executes the edited text, checks
products and records script text, changes and outcome against the appropriate dataset target.

## Parameter resolution and outputs

Templates and configuration provide processing defaults. Desktop calls supply selected overrides;
reference studies can overlay common parameters per condition. API combinations merge candidate
values with frozen reference defaults, with locked conversion/phase-route keys enforced by the
combination layer. Empty combination cells mean unspecified values. There is no single precedence
list covering every GUI and API operation; see [API inputs](external-api/05-inputs-and-data.md).

Each run records requested and resolved/applied values, scripts, input/product references, software
and tool versions, status, diagnostics and warnings. Products are registered under the project data
entry or the API study workflow/condition. Peak detection/localisation operates on the resulting
spectrum. The API writes independent tables without assigning cross-spectrum identities.

## Four processing paths

| Path | Engine route |
| --- | --- |
| 2D uniform | Conventional NMRPipe FT; automatic/manual entry points |
| 2D NUS | SMILE reconstruction; automatic/manual entry points; optional initial P0 seed |
| 3D uniform | Conventional NMRPipe FT with logical/storage-axis mapping |
| 3D NUS | SMILE reconstruction/finalisation without the 2D seed |

Desktop batch groups support homogeneous 1D/2D/3D data. API 3D NUS supports reference construction but rejects
parameter-combination execution. See [shared interfaces](API_CONTRACT.md), [quality control](qc-system.md),
[backend architecture](backend/architecture.md) and [API boundaries](external-api/09-limitations-and-roadmap.md).
