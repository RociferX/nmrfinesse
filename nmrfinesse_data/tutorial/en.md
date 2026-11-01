# NMRFinesse usage tutorial

Updated for the source interface as of 2026-11-01: software version 1.0.11 and API v1.1.5. The window title shows the software version; source and installers are on the [releases page](https://github.com/RociferX/nmrfinesse/releases). Change the interface language in Settings → Software settings; this tutorial follows that choice.


## Version, copyright and project resources

Help → About shows the running software version, API version, author, copyright and license, with clickable GitHub, release, documentation, issue-reporting and Zenodo links. Include these versions, your Linux desktop/display session, reproduction steps and relevant logs when reporting an issue. Remove private information before sharing data or logs.

- Author and copyright: Copyright © 2026 Xuanfeng Li. Project source is licensed under [Apache-2.0](https://github.com/RociferX/nmrfinesse/blob/main/LICENSE); see [NOTICE](https://github.com/RociferX/nmrfinesse/blob/main/NOTICE).
- Project and downloads: [GitHub](https://github.com/RociferX/nmrfinesse) · [Releases](https://github.com/RociferX/nmrfinesse/releases) · [Report an issue](https://github.com/RociferX/nmrfinesse/issues). Source and AppImage updates are released separately; restart a running program to load updated source.
- Citing the software: use [CITATION.cff](https://github.com/RociferX/nmrfinesse/blob/main/CITATION.cff) or [Zenodo](https://doi.org/10.5281/zenodo.22909415), and state the version you used. This DOI identifies the software across versions; obtain a version-specific DOI from the corresponding Zenodo record.
- Third-party components retain their own licenses; see [THIRD_PARTY.md](https://github.com/RociferX/nmrfinesse/blob/main/THIRD_PARTY.md). Qt/PySide6 in the Linux AppImage use LGPL-3.0; run the AppImage with `--licenses` to display bundled notices. NMRPipe and SMILE are installed separately.

## Axis conventions

Axes use logical dimension names: in 2D, F1 is indirect and F2 direct; in 3D, F1/F2 are the first/second indirect dimensions and F3 direct. Same-nucleus dimensions use x/y/z suffixes assigned in direct, acqu2, acqu3 priority. NMRPipe 3D storage order (F2,F1,F3) is converted to logical order on load; the axis reorder log entry records this conversion.

## 1. What the software does

- Reads Bruker data and identifies dimensions, experiment types and uniform/NUS sampling.
- Generates FIDs and spectra through NMRPipe, with automatic phase, baseline, window and other parameter choices. NUS uses SMILE reconstruction.
- Provides FID, sampling and spectrum quality checks, step reports, logs and editable processing scripts.
- Picks peaks with three-point parabolic localisation, supports assignment editing, peak-table import and coordinate alignment.
- Displays 1D, 2D and 3D slices; compares two or three spectra side by side or overlaid; exports peak lists, UCSF files and overlay SVGs.
- Organises projects, experiments, data and groups. Batch processing supports independent 2D data only.

Real processing requires a separate NMRPipe installation; NUS additionally needs SMILE. Neither is bundled.

## 2. The window at a glance

The main window has three adjustable columns:

- **Left: project tree.** Workspace → project → experiment → data or group. Selection opens the corresponding tools in the centre. Bruker `title` text appears below data names; hover for full details.
- **Centre: processing.** The welcome page creates or opens projects; the project page creates experiments and exports UCSF; the experiment page imports data; data pages show the pipeline. **The task log sits below the centre panel** and follows your selection.
- **Right: spectra.** Selecting data loads its current spectrum. Files and layers, display and slice controls, and peak tools/table collapse independently while the plot remains visible.

The top menus are File, View, Tools, Settings and Help. Create projects in the centre welcome page and experiments on the project page. Help → Usage tutorial opens this guide. Small screens and large fonts use scrolling. Notes appear above the centre tools; short fields wrap together and remarks preserve line breaks.

Operation dialogs open centred on their owner, stay on top and block the main window until closed. File/folder browsing uses the native system chooser, starting at the current path or relevant default folder. Web links in the tutorial and About open in your default browser.

The Object column starts compact, with status next to the name. Drag the header separator to adjust its width; title subtitles wrap and row height follows the text.

## 3. From a new project to a peak table

1. **New project:** select the workspace and click New project... in the centre welcome page. Enter a name and confirm. The project is created in the current workspace. Recent projects and File → Open project... open existing projects.
2. **New experiment:** select the project, enter a title and click New experiment in its centre page. This page also shows experiment/data counts and recent runs.
3. **Import data:** select an experiment, use Browse... in its inline import form, choose a Bruker data directory containing `acqus`, then import. The experiment's Import sample data... context action remains available. Names default to the source folder name; an entered name takes precedence. Bruker `title` becomes the default remark and appears in the tree.
4. **Check detection:** review experiment type, sampling class and dimension layout. Evidence is in the log. Correct relevant notes or parameters before continuing if detection is wrong.
5. **Generate FID → Generate spectrum:** run the pipeline in order. Set the direct-dimension range first if needed; the usual protein 1H range defaults to 6.5–10.5 ppm. The option to use that range for optimisation controls whether optimisation and the final run share it. NUS spectrum generation includes SMILE.
6. **Read reports and inspect spectra:** expand step reports for FID/sampling conclusions, spectrum quality items and actual parameters. The right viewer loads current results; large files load in the background, with F3–F2 as the default 3D plane.
7. **Pick and export peaks:** run Peak picking, inspect peaks and SNR, edit assignments as needed, then use the table's import, save or export actions.

The pipeline guide suggests the next step. A failed step offers View log. Regeneration, optimisation or a successful manual script refreshes the matching data's spectrum while keeping your selected log scope.

## 4. Pipeline steps and manual processing

### Generate FID

Creates and runs `fid.com`, using NMRPipe's `bruker -AUTO` to convert raw data. 3D uses single-file or slice layouts according to its sampling grid. Inspect or edit CAR during spectrum generation.

### Generate spectrum

Produces a final spectrum using automatic or manually specified parameters. NUS includes SMILE reconstruction. Display spectrum and Re-run the final script become available afterward. The latter reuses scripts without reoptimisation: 3D NUS reruns the indirect part, while uniform 3D follows the prompt about rerunning the direct dimension.

Edit CAR in the manual script to change the spectrum centre. Use indirect-axis flip controls only when positions are mirrored, then rerun. The 2D checkbox keeps the current state; selecting the same 3D flip command again cancels that flip. Existing PS parameters are compensated accordingly; the direct dimension is excluded.

Open, edit and run manual scripts. A successful run compares changes with the previous successful script; failed attempts are not reported as successfully applied parameters.

### SMILE optimisation

SMILE optimisation is an optional 2D NUS parameter scan and ranking with alternative ranking targets. It does not replace the active spectrum automatically: select and run the desired candidate. 3D NUS reconstruction works without this scan entry.

### Peak picking

Detects peaks and retains peak heights and picking-time SNR, with three-point parabolic sub-grid localisation. Change thresholds and rerun, or use the step's reference spectrum action to choose data with an existing peak table and retain matching peaks. Unreliable references or absent common nuclei keep detected peaks with an explanation. Clear removes the reference constraint.

Steps can be not ready, runnable, running, completed, failed or expired. Input or parameter changes expire affected downstream steps, which then need rerunning.

## 5. Viewing, zooming and comparing spectra

- Wheel to zoom, middle-drag to pan, and Full view to reset. Contour start adjusts contour threshold, Levels changes the level count, and Aspect controls proportions; `0` means free scaling.
- Press Enter to apply typed values. Leaving a field or Escape cancels a draft; arrow buttons apply immediately. Decimal Aspect values such as `0.8` are supported.
- The 1D full view centres zero vertically. With free Aspect, vertical wheel zoom grows at 1.5 times the horizontal rate. Both 1D and 2D support middle-button panning; 2D restores higher direct-axis ppm values on the left.
- Above 150% zoom, a full-spectrum thumbnail appears at the upper left. Click or drag it to navigate; Full view resets the range and hides it.
- Enlarge extends the plot to the left; click again to restore. 3D controls choose planes and slices and display projections.
- Compare two or three spectra with separate colours, positive/negative visibility, side-by-side views or a shared overlay. Full view covers their combined ranges. Side-by-side plots have equal heights; overlay hides peak tools/table until you exit.
- Overlay SVG export offers ppm ranges, aspect and a preview; default names identify spectra and colours.

The standalone viewer needs no project: run `nmrfinesse-viewer` or `python -m viewer`. It accepts dropped `.ft1`, `.ft2` and `.ft3` files.

## 6. Assigning, importing and exporting peaks

Expand peak tools and the table to select, box-select, add or delete peaks and edit Assignment. SNR retains the picking result; missing values stay empty.

- **Import `.list`:** Import peaks first asks for a file, then checks for existing picked peaks. It backs up picked assignments, coordinates, intensity and full-precision SNR as `<exp>-<data>_picked_<time>.csv` in the current data's `peaks` folder before estimating a global translation to the imported list. A failed backup stops the import.
- **Switch tables:** Picked peaks and Imported peaks retain separate assignments. Picked rows use native coordinates; imported rows use reference coordinates, with markers on their corresponding spectrum peaks. Axis labels show offsets and the cursor shows aligned and original ppm. Spectrum data/headers stay intact; repeated imports do not accumulate offsets.
- **Restore CSV:** Import a NMRFinesse CSV to restore the picked table directly without prior picking. This clears the reference and display offsets. Tables and calibration belong to the current loading session; reloading or repicking reads the project table again. Restore original assignments from CSV backups.
- **Export `.list`:** direct export saves the selected table. After alignment export first chooses a reference `.list`, estimates the same global translation as import, then asks where to save. Exports contain assignments and ppm only, without intensity/SNR. The current table and spectrum file stay unchanged.
- **Save peaks:** writes the active table back to the project and records a manual peak-table run. Internal saves retain intensity and SNR.

## 7. Segmented acquisitions and averaged repeats

Use the experiment page's segmented data or repeated experiment overlay import for complementary NUS segments, or repeats with the same parameters and sampling points. The experiment's import context dialog provides the same option.

The container has no top-level `acqus` and at least two subdirectories containing complete data. The program recognises this structure or reports unsuitable input. Import merges it into one data set and one FID/spectrum workflow. Use the next section for several independent data sets.

## 8. Data groups and batch imports: 2D only

Use Browse... on the right of the experiment page's Batch processing area to add independent data folders; Clear list removes candidates. Batch import and group is off by default. Enable it to put imported data into one group; group members can also be added or removed in the tree.

Batch import reports totals, successes and failures. Non-2D data is skipped with a reason; one failed data set does not stop the group. Individual member runs use member logs, and whole-group runs use group logs.

## 9. Tools menu

- **Data quality inspection:** choose a FID file or FID folder (slice group). Folders inspect directly contained `*.fid` files without recursion. Results go to the global log; no project is required and FIDs/processing records are unchanged.
- **Spectrum quality assessment:** reads an existing spectrum and reports quality items and conclusions.

## 10. Software settings and path browsing

Open Settings → Software settings:

- **Tool paths:** NMRPipe, bruker, proj3D.tcl and pipe2ucsf each have Browse to select an executable or script. Type a path directly if preferred; empty values use automatic discovery. SMILE is a plugin and displays detection status.
- **Data directory:** the default import starting folder. Entered paths take precedence; unavailable paths use an existing parent or home.
- **POKY/Sparky spectra folder:** the default UCSF destination. Browse chooses it manually; Auto-find reads this machine's user environment and POKY working-directory configuration, including paths with spaces or on other disks. Blank values use discovery; without a match, browsing starts at home.
- **Language and font:** follow the system or choose Chinese/English, with a restart as indicated. Automatic or manual 8–18 pt fonts apply on save; large layouts remain scrollable.
- **Per-nucleus default line width and alignment tolerance:** used by their corresponding optimisation and matching steps.
- **SMILE threads:** 2 by default, capped according to core count; low-core machines use 1.

Every path has its own Browse button. File and directory selection use separate modes, starting at the current path or relevant default folder. Settings are stored in this machine's configuration.

## 11. UCSF export and product locations

Select the project and click Export UCSF files… in the centre page. Choose one or more data sets by experiment; checking an experiment selects its available data. Click Export, then choose the destination. Entries without UCSF files are unavailable. Background copying keeps project originals, adds suffixes to duplicate destination names and reports successes/failures.

Each data set's `spectra` folder holds NMRPipe results (`.ft1`, `.ft2`, `.ft3`). For 2D/3D results, pipe2ucsf also produces a matching `.ucsf` when available. Picked-table CSV backups are in `peaks`; manual `.list` exports use your chosen location. Projects contain scripts, run records and logs; deleting project data uses the system trash.

**NUS bad-sampling-point cleaning rewrites source data.** It removes complete bad rows from raw `ser` and `nuslist`, first saving `ser.bak` and `nuslist.bak`; existing backups are not overwritten. The log records `Source cleanup …(backup .bak)`. Use a copy if originals are read-only or must remain intact.

## 12. Scope

Batch processing is 2D only. Peak-overlap deconvolution, structure determination and automatic assignment are outside the current scope. Inspect processing and quality reports against your data; statistics and scientific conclusions belong to your analysis workflow. Processing evidence is in `docs/evidence/real-data-comparison.md` in the repository.

## 13. When something fails

Start with the task log below the centre panel; failed steps offer View log. Check tool paths when an executable is missing, or use Tools → Data quality inspection for suspected input problems. Scripts, run records and `log.txt` retain input, parameter and result clues. See `docs/troubleshooting.md` and `docs/faq.md` in the repository for more guidance.
