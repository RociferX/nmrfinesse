# POKY/iPick peak-table concordance evidence

The original portable package was verified on 2026-11-05. This public derivative preserves all
CSV tables and the standard-library verifier byte-for-byte. Source-machine identifiers in metadata
and the source README are redacted; original file and manifest hashes in `manifest.json` retain provenance.

Core mechanisms are similar and outputs are highly concordant in this batch: thresholded local
maxima with per-axis three-point parabolic localization, for 12 retained 2D positive HN spectra.
All 24 low/high tables agree in counts and their 5175 within-table records have unique one-grid-step
matches. Four equal-threshold tables are reused; there were 20 independent valid iPick calls.
8084/8088 downstream availability cells agree; four discrepancies repeat one member/run.
Historical versions remain 1.0.8/API1.1.4 (main grid) and 1.0.9/API1.1.5 (diagnostics).
The corrected ipick_transfer_v2 transfer was used. Raw spectra and third-party code are not included.
Run `python verify_tables.py` here to repeat table-level integrity and correspondence checks.
This is evidence for the tested conditions, not implementation equivalence or a current-release rerun.
