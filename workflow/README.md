# workflow/

Orchestration. This layer sequences the steps of a processing session and records what happened.
It may use `core/` and `backend/`, and must not import `gui/` or `viewer/`.

| Module | Role |
| --- | --- |
| `import_workflow.py` | import: read parameters, copy or link raw data, classify, register |
| `stepwise.py` | the stepwise pipeline (FID generation, spectrum generation) shared with the GUI |
| `phase_routes.py` | the unified phase route: complex preview, in-memory phase search, parameter optimisation, final run |
| `manual.py` | the manual path: view, edit and run `fid.com` and the processing scripts |
| `batch.py` | homogeneous 1D/2D/3D groups; automatic 2D can run concurrently, other groups run sequentially |
| `pick_peaks.py` | peak picking and localisation |
| `peak_align.py` | aligning peak tables between spectra |
| `direct_diagnostics.py` | FID diagnostics: DC offset, bad points, drift, broadband peaks |
| `smile_optimize.py` | the SMILE parameter scan |
| `baseline_optimize.py`, `window_optimize.py`, `param_optimize.py` | parameter-optimisation grids |
| `memory_phase_search.py` | in-memory phase search |
| `script_check.py` | script validation before a run |
| `script_audit.py` | manual-script parameter diffs, baselines and reports; parses only and never executes scripts or infers physical axes |
| `optimization_report.py` | writing the quality and optimisation record |
| `ucsf_export.py` | exporting processed spectra |

Reference baseline scores come from `baseline_optimize` calling `core.qc.baseline_quality.evaluate`; the score combines slope, offset, curvature and stripe penalties. The attachment records those raw metrics and their separate score components. Window selection starts with FID baseline scoring, then refines phased 2D/3D axes using equally weighted regions to compare signed sidelobes, peak retention and resolution. The FID resolution factor is `width_ratio^-0.25`; refinement compares width with the unwindowed reference and uses `(1+d+d²)^-w`, with direct-axis `w=1` and indirect-axis `w=0.25`. First-order phase uses a receiver-delay prior and phases of separated peaks, with preview/final axis coordinates reconciled. See the [score fields](../docs/external-api/06-outputs-and-records.md#611-reference-optimization-score-table).
One documented exception to the boundary rule: `stepwise.py` reads the experiment-type labels from
`gui/notes.py`, so that the GUI list and the stepwise path cannot drift apart.

End-to-end coverage lives in [`tests/test_full_paths.py`](../tests/test_full_paths.py).
