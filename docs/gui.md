# NMRFinesse GUI guide

This guide describes the current source interface. Help → About identifies the running version. Source updates and AppImage builds are published separately; check the release notes for the features in an installed build. Use the contents panel to jump between sections.

## 1. Versions, copyright and requirements

### 1.1 Project resources and citation

- Software 1.0.11, Python/CLI API v1.1.5. Help → About shows the running versions, author, licence and project links.
- Copyright © 2026 Xuanfeng Li. Source uses [Apache-2.0](https://github.com/RociferX/nmrfinesse/blob/main/LICENSE); see [NOTICE](https://github.com/RociferX/nmrfinesse/blob/main/NOTICE).
- [GitHub](https://github.com/RociferX/nmrfinesse) · [Downloads and release notes](https://github.com/RociferX/nmrfinesse/releases) · [Issue tracker](https://github.com/RociferX/nmrfinesse/issues).
- Cite [CITATION.cff](https://github.com/RociferX/nmrfinesse/blob/main/CITATION.cff) or [Zenodo](https://doi.org/10.5281/zenodo.22909415), naming the version used. This is the concept DOI; a specific version DOI is listed in its record.
- Third-party licences are listed in [THIRD_PARTY.md](https://github.com/RociferX/nmrfinesse/blob/main/THIRD_PARTY.md). The Linux AppImage includes Qt/PySide6 under LGPL-3.0; `--licenses` displays bundled notices.

### 1.2 Engines and supported work

Processing raw spectra requires a separate NMRPipe installation; NUS reconstruction also needs the SMILE plugin. Viewing existing 1D/2D/3D spectra, handling peak tables and copying UCSF files are separate from processing raw data again.

The application organises projects, experiments, data and groups, with Bruker import, FID/spectrum generation, quality reports and peak picking. Batch processing handles independent 2D data only; process 3D data individually. Peak-overlap deconvolution, structure determination and automatic assignment are outside the current feature set.

## 2. Pages, windows and notes

### 2.1 Selection and page layout

| Left-tree selection | Centre page and main actions |
| --- | --- |
| Workspace | Create/open projects and select recent projects |
| Project | Create experiments; inspect counts and recent runs |
| Experiment | Import controls above the sample-data table |
| Data or its subfolder | Processing pipeline for the selected data |
| Group | Batch operations, group parameters and results |

The viewer is on the right; task logs sit below the centre panel and follow selection. A data page has one header containing its purpose, flow and project/experiment. Create projects on the welcome page and experiments on the project page; UCSF export is in Tools.

### 2.2 Window size and fonts

The application starts in a normal window, capped at the logical 1080p workspace after allowing for panels and window borders. Smaller screens use scrolling; larger screens keep this initial size. Automatic fonts use the normal-window baseline and adapt on maximising/fullscreen; ordinary window resizing does not rescale them. A manual size takes precedence.

Drag the three column boundaries to resize them. Application dialogs are centred above their owner and block interaction with the window behind them. Menus and drop-downs open at their trigger. Native file/folder choosers start from the entered path or relevant default folder.

### 2.3 Titles and notes

New data defaults to the source folder name unless a name was entered. Bruker `title` becomes the default remark and appears below the data name in the tree; automatic filling preserves an existing manual remark.

Original title lines are display units: join them with ` | ` when they fit, and prefer the original boundaries when wrapping. An individual line wider than the available space may wrap further to keep its content readable. Spectrum names, layers, comparison choices, colour buttons and export summaries show the corresponding title, source and full path on hover.

The notes area shows content and Edit notes directly, without a separate Note: heading. Short fields wrap together; data remarks use the title rule above. Stored text is unchanged.

## 3. Projects and data import

### 3.1 Create a project and experiment

1. Select the workspace and use New project... on the welcome page, or File → Open project....
2. Select the project, enter an experiment title and use Create experiment on its page.
3. Select the experiment and choose an import route at the top. Imported data appears in the table below and in the tree.

### 3.2 The three import routes

| Route | Directory to select | Result |
| --- | --- | --- |
| Single import | A Bruker directory directly containing `acqus` | One data entry; an optional name overrides the folder name |
| Segments / repeats | A container without top-level `acqus`, with at least two data subdirectories | Complementary parts of one acquisition or compatible repeats, combined as one data entry |
| Batch import | An umbrella folder of independent data, or several folders added in turn | Separate entries; only Group data (2D) creates a group |

Browse and the main import actions align at the top of each column, with descriptions below. Group data is off by default. The batch list hides when empty and shows up to four rows before scrolling. Batch import skips 3D data with a reason; one failure does not stop the other entries.

### 3.3 Source paths and identification

Link raw data to project is checked by default, preferring read-only links and copying when needed; unchecked registers the source by reference. Keep linked/referenced sources accessible. Importing another entry does not repair broken links in an older entry.

Check dimension, experiment type, sampling and layout after import. Ordinary inputs need the acquisition parameters and `ser`/`fid`; NUS needs `nuslist` or the schedule explicitly named in the acquisition parameters. Import existing NUS as NUS. Logs explain rejected layouts or inconsistent parameters.

## 4. Processing, reports and status

### 4.1 Run the steps

1. **Generate FID:** create and run conversion scripts to produce NMRPipe FIDs; 3D can use one file or a slice layout.
2. **Generate spectrum:** use automatically selected or specified processing parameters. NUS includes SMILE reconstruction. Set the direct-dimension range when needed; the common protein 1H default is 6.5–10.5 ppm, to be checked against the data.
3. **Peak picking:** detect peaks, preserve intensity/SNR and create a table. See section 6 for editing and export.

SMILE parameter optimisation, ranking and ranked reruns are temporarily unavailable in the GUI. NUS spectrum generation still uses SMILE reconstruction.

### 4.2 Manual scripts, reports and logs

Manual opens the step script for editing and execution. A successful run compares parameters with the preceding successful script; a failed attempt is not described as successfully applied changes.

Re-run final script reuses generated scripts without repeating optimisation. Indirect-dimension flips affect only the corresponding indirect processing; select the nucleus shown in the interface. Report expands quality conclusions, parameters and run details. Successful processing refreshes the target spectrum while log display continues to follow selection.

Individual operations write data logs; group operations show group logs and member results. A failed step offers View log.

### 4.3 What Needs update means

An output can exist while current inputs or scripts differ from the last successful snapshot. Needs update names missing paths, missing/added/changed files or scripts; downstream steps include the upstream cause. New successful records contain per-file fingerprints. Older multi-file records say when there is insufficient evidence to identify a particular changed file.

Software settings → Simple mode checks only whether outputs exist. It disables fingerprint and age comparisons; it does not repair inputs or regenerate results.

## 5. Viewing and comparing spectra

### 5.1 Common controls and coordinates

Selecting data loads its current spectrum. Files/layers, display/slice controls and peak tools/table fold separately; the peak section starts collapsed. Enlarge gives the plot more space; click again to restore.

- Use the wheel to zoom and the middle button to pan. In 2D/3D, left-drag selects a zoom box.
- Contour start sets the contour percentage; Levels sets the count. Positive/negative contours can be hidden separately.
- Aspect zero selects free scaling. Enter applies a typed value; focus loss or Esc cancels an uncommitted edit.
- Full view resets the view. Beyond about 150% zoom, a full-spectrum overview appears at the top left.
- Hover over files, layers and comparison entries to distinguish identical names from different experiments.

In 2D, F1 is indirect and F2 direct; in 3D, F1/F2 are indirect and F3 direct. Axes use logical dimensions, with x/y/z distinguishing repeated nuclei. Ordinary ppm x axes decrease from left to right.

### 5.2 Viewing a 1D spectrum

The 1D default Aspect is 0.02 and zero intensity is centred. The initial view prioritises the full x range, so a water peak may extend beyond the vertical range. With Aspect locked, zoom out beyond the full x range until the complete intensity range also fits. Full view restores the initial view.

With free Aspect, the vertical wheel factor is the horizontal factor raised to 1.5. 1D and 2D Aspect settings are separate, and middle-button panning remains available. Phase preview changes display only, without writing raw data or spectrum files.

### 5.3 1D strips and phase in 2D/3D

Ordinary 2D/3D crosshairs follow the pointer without pressing a button. With the 1D strip toggle on, **hold the left button** in the spectrum to move the crosshair and top/right cuts. Release to freeze them; the chosen position remains visible on leaving the plot.

Top and right strips identify their nuclei and have separate P0/P1 rows. Reset/Copy acts on its own row, and moving to another cut preserves both settings. This phase adjustment is for display only.

3D starts on F3–F2; slice controls choose the plane, fixed-axis position or projection.

### 5.4 Two/three spectra, overlays and SVG

After enlarging, use Compare to choose a reference. Add third spectrum opens a right-hand submenu. Side-by-side views place the reference left and current spectrum in the middle, with equal plot heights and independent zoom/display controls.

Matching 2D/3D nuclei and plane orientations link crosshairs at the same **displayed ppm**, including display shifts. Zoom and spectral data remain independent.

Overlay inherits each spectrum's current Contour start, Levels, sign and layer visibility; changes return to the separate views on leaving. Colour buttons, reference selection and manual/fitted ppm shifts support comparison. Shifts affect display, not spectral arrays or headers. Overlay hides peak tools/table and restores them on exit.

Full view covers the union of ranges, using a separate shared Aspect. Export overlay SVG lets you set ranges and image aspect, preview, then save. Image export, peak-coordinate export and copying UCSF files are separate operations.

## 6. Peak tables, assignments and alignment

### 6.1 Pick and edit peaks

Expand Peak tools/table to select, box-select, add/delete peaks and edit Assignment. Marker size starts at 0.5, steps up by 0.5 at/above it and down by 0.1 below it, with minimum 0.1. SNR shows the value saved during picking and leaves missing values blank; existing noise/threshold calculations are retained.

### 6.2 Import .list or restore CSV

Import peaks first selects a file. Importing `.list` needs current picked peaks to estimate the overall ppm translation; otherwise it asks you to pick peaks first. The original picked table and assignments are backed up as a NMRFinesse CSV in the data's `peaks` directory before import. A failed backup stops replacement.

Switch between picked and imported tables while keeping assignments separately. Axis names show the display shift and mouse readouts show aligned and original ppm. Arrays and headers stay unchanged, repeated imports do not accumulate offsets, and low-quality alignment does not force peak deletion.

A NMRFinesse CSV restores the original table directly, without prior picking, and clears the imported display shift. Switching/reloading data reads project-saved state.

### 6.3 Save, direct export and aligned export

- **Save peaks:** write the current table to the project, retaining intensity/SNR internally.
- **export directly:** export assignments and ppm from the selected table.
- **After alignment export:** choose a reference `.list` and export the current table after overall translation to it. The current table and spectrum are unchanged.

GUI `.list` exports contain only `Assignment w1 w2 [w3]`, without intensity, volume or SNR. Internal tables/localisation attachments and CSV backups may retain metrics; an exchange .list is not a full backup.

## 7. Tools and UCSF export

### 7.1 Standalone quality inspection

- **Data quality inspection... → FID file / FID folder (slice group):** inspect converted FIDs. A folder checks its direct-child `*.fid` slices only, without recursion. Inputs are unchanged; results use the global log.
- **spectrum quality assessment...:** select an existing spectrum and review quality items and conclusions without changing its file.

These work without a project. Use the next tool to omit bad FIDs from raw Bruker acquisitions.

### 7.2 Remove abnormal FIDs and export NUS…

This handles uniformly sampled data with some abnormal FIDs. Validated Bruker 2D/3D layouts use AQSEQ=0, complex direct acquisition and States/States-TPPI/Echo-Antiecho indirect modes. Existing NUS, kinetic/pseudo dimensions and inconsistent parameter/SER geometry are rejected.

1. Browse to raw data and detect. Inspect raw FID row numbers, increment coordinates and findings.
2. Automatic mode selects nonfinite, entirely zero increments and 12-MAD isolated-spike candidates. A zero phase component or high energy is advisory. Manual mode can select or cancel any increment.
3. Review the omitted count and retained fraction; select a new destination. Each increment removes its complete two/four-row phase group, with at least two increments retained.
4. Export a new Bruker NUS directory with `ser`, `nuslist`, updated acquisition parameters, title and `fid_selection.json`, excluding old processed spectra. The source stays unchanged and an existing destination is not overwritten.
5. Import the output normally, then process through NUS/SMILE. Export itself does not reconstruct a spectrum.

Coordinates are zero-based, in acqu2s/acqu3s order for 3D. Original grid coordinates and NusTD are retained. Changed inputs require a new inspection.

Existing NUS processing also has source-level cleaning for invalid/duplicate schedule coordinates. When executed, it rewrites the raw ser/nuslist in use, first saving `.bak` and recording the action. That is separate from the **new-directory export** above.

### 7.3 Export UCSF files…

Open a project and use Tools → Export UCSF files…; the entry is no longer on the project page. Check one or more available data entries by experiment, then Export and choose the destination. Entries without UCSF files are unavailable.

Background copying preserves originals, adds suffixes for duplicate names and reports successes/failures. The default comes from the POKY/Sparky spectrum-folder setting; you may choose another destination. This copies existing UCSF files rather than converting or processing data again.

## 8. Software settings

In Settings → Software settings...:

- **Engine paths:** choose NMRPipe, bruker, proj3D.tcl and pipe2ucsf executables/scripts, or leave blank for discovery. SMILE is detected as a plugin.
- **Data root:** the default starting folder for new imports; an entered path takes precedence.
- **POKY/Sparky spectrum folder:** default UCSF destination, discovered on the current machine or chosen manually. Discovery uses environment, working-folder configuration and common user folders.
- **Language/font:** system or explicit English/Chinese language, effective after restart; manual fonts are 8–18 pt and apply on saving.
- **Default linewidths, matching tolerances, SMILE threads and Simple mode:** choose for the relevant processing/matching task. SMILE defaults to two threads, limited on low-core machines.

Each path has Browse..., with file/folder selection as appropriate. An invalid path falls back to an available parent or home folder. Local settings are separate from exported project data.

## 9. Outputs and troubleshooting

### 9.1 Product locations

For each data entry, `process` holds scripts/conversion products, `spectra` final spectra and available UCSF files, `peaks` tables/CSV backups, and `report` reports/logs. 2D/3D generate UCSF when pipe2ucsf is available; 1D does not generate UCSF.

Manual .list, SVG and UCSF-copy operations use the selected destination. Deleting project data uses the system trash; keep source directories needed by linked imports.

### 9.2 First checks when something fails

| Symptom | First check |
| --- | --- |
| Raw processing cannot start | NMRPipe/SMILE detection, configured paths and task log |
| Needs update | The named input/script path; distinguish missing links, actual changes and legacy evidence limits |
| UCSF menu disabled | A project must be open |
| A UCSF data entry cannot be selected | Check that its supported 2D/3D result has a UCSF file |
| Peak export disabled | Loaded data with nonempty peaks, outside projection viewing |
| Unexpected spectrum/coordinates | Current file, 3D plane, display shift and contour-sign settings |

Report the About version, desktop/display session, steps and relevant logs. See [troubleshooting](https://github.com/RociferX/nmrfinesse/blob/main/docs/troubleshooting.md) and [real-data evidence](https://github.com/RociferX/nmrfinesse/blob/main/docs/evidence/real-data-comparison.md) for further guidance and validation boundaries.
