# NMRFinesse usage tutorial

This guide follows the current source interface. Open **Help → Usage tutorial** and select a topic in the contents panel. For an installed build, use **Help → About** and the release notes to identify the version and its features.

## 1. Preparation and first run

### 1.1 Versions, copyright and resources

- Software version **1.0.12** and Python/CLI API version **1.1.6**.
- Copyright © 2026 Xuanfeng Li. The source uses [Apache-2.0](https://github.com/RociferX/nmrfinesse/blob/main/LICENSE). See [NOTICE](https://github.com/RociferX/nmrfinesse/blob/main/NOTICE).
- [Project home](https://github.com/RociferX/nmrfinesse) · [Downloads and release notes](https://github.com/RociferX/nmrfinesse/releases) · [Issue tracker](https://github.com/RociferX/nmrfinesse/issues).
- Cite the version you used. See [CITATION.cff](https://github.com/RociferX/nmrfinesse/blob/main/CITATION.cff) and the [Zenodo concept record](https://doi.org/10.5281/zenodo.22909415), which links to individual versions.
- See [THIRD_PARTY.md](https://github.com/RociferX/nmrfinesse/blob/main/THIRD_PARTY.md) for third-party licences. The Linux AppImage bundles Qt/PySide6 under LGPL-3.0. Use `--licenses` to see its notices.

### 1.2 Complete a first workflow

Processing raw Bruker data requires NMRPipe. Reconstructing 2D or 3D NUS data also requires SMILE. To view an existing spectrum, open it from the viewer's File menu. The startup progress bar runs in the main window before the workspace appears.

1. Create a project on the welcome page. Select the project and create an experiment in the centre panel.
2. Select the experiment. Use **Single import** to add a Bruker directory containing `acqus`, then select the imported data in the tree.
3. In **Automatic processing**, run **Generate FID** and **Generate spectrum** in order. For 2D or 3D data, run **Peak picking** once a spectrum is ready.
4. Inspect the spectrum in the viewer. Expand **Peak tools and table** to review or edit peaks, then use **Save peaks**. Export a `.list` or copy an existing UCSF file when taking the results to POKY/Sparky.

## 2. Workspace, pages and notes

### 2.1 What each tree level opens

| Selection | Centre panel | Use it to |
| --- | --- | --- |
| Workspace | Welcome page | Create, open or resume a recent project |
| Project | Project overview | Create experiments, check counts and review recent runs |
| Experiment | Import forms and sample-data table | Add data and check names and states |
| Sample data | Processing page | Run the automatic route, reuse scripts and inspect reports |
| Data group | Notes and group processing | Compare members, select a reference and set a stopping step |
| Data subfolder | Processing page for that data | Locate raw files, scripts, spectra, peaks and reports |

The main File menu opens, saves and switches projects and closes the application. Right-click the tree for actions such as renaming and deleting. Data and folder entries can also open their locations in a file manager or terminal. Double-click a spectrum file to load it.

### 2.2 Window and task log

The normal window uses a 1920×1080 physical-pixel layout within the available desktop. Drag the boundaries to resize the three panes or the log. Smaller windows can scroll the workspace.

The log follows your selection. Select data for its processing log or a group for progress and the summary. **Clear** clears the current log scope, including the log stored on disk for an individual data set. **Stop task** requests cancellation. Outputs already produced can be checked in the data folder.

### 2.3 Bruker title and editable notes

Project notes describe the sample or protein. Experiment notes record conditions and instrumentation. Data notes include repeat number, buffer, pH, temperature, nuclei, sampling mode and peak sign. Select the relevant tree node, open **Edit notes**, then save. Set direct-axis range, phase and other processing parameters in their processing controls.

The source folder supplies the default data name. A name entered during import takes precedence. Bruker `title` supplies the default remark and appears under the data name. Short title lines are joined with ` | ` where they fit, with a preference for the original breaks when wrapping. Hover over spectra, layers, comparison entries or colour controls to distinguish items by title and path.

## 3. Projects and data import

### 3.1 Create an experiment and choose an import route

Create a project on the welcome page, then create an experiment on the project page. An experiment can hold several independent data sets. Select it and choose one of the three import cards. Check the resulting entries in the sample-data table below.

| Route | Select | Purpose |
| --- | --- | --- |
| Single import | A folder containing `acqus` | Register one data set, with an optional display name |
| Segments / repeats | A container without top-level `acqus`, with at least two child acquisition folders | Process compatible segments or repeats as one data set |
| Batch import | One top-level folder containing independent acquisitions | Discover several acquisitions and register them separately |

The segments route uses joint conversion and merging, so the acquisition parameters, nuclei and dimensionality must be compatible. Batch import gives each acquisition its own scripts, outputs and reports.

### 3.2 Filter, remove and group batch entries

1. Choose **Browse** in the batch card and select a top-level folder. The discovered paths appear in a scrollable list.
2. Use the dimensionality filter for all data, one dimension or any pair. The first row, **All**, checks or unchecks every path shown by the current filter. A mixed selection is shown as a partial check. `Ctrl+A` checks the visible paths as well. Use **Remove checked** to remove those candidates.
3. **Batch import** imports every path left in the filtered list. Enable **Group data by dimensionality** to create separate 1D, 2D and 3D groups after import. Grouping is off by default.
4. Review the tree and log. An import error identifies the affected path.

### 3.3 Source files and NUS schedules

**Link raw data to project** is enabled by default and uses a link where possible, with a copy when required. Clear it to reference the source directory in place. Keep referenced sources accessible. Registering the same folder as a new data entry leaves the earlier entry pointing to its original path.

Check the imported dimension, experiment type, nuclei and sampling mode. `acqus`, the indirect acquisition parameters and `fid` or `ser` identify the layout. NUS requires `nuslist` or an acquisition parameter that explicitly identifies the schedule. Consult the import log for missing files, incompatible segments or a layout mismatch.

## 4. Automatic processing, reference scripts and groups

### 4.1 What each automatic step does

| Step | Purpose | Where to check |
| --- | --- | --- |
| Generate FID | Convert the Bruker acquisition to NMRPipe FID data. 3D may use a slice set | FID data and conversion scripts in `process` |
| Generate spectrum | Apply windowing, transforms and phase, then write the final spectrum. NUS uses SMILE reconstruction | Final spectrum, available projections and UCSF in `spectra` |
| Peak picking | Detect peaks and record coordinates, intensity and SNR | Files in `peaks` and the viewer table |

**Direct dimension range** sets the retained direct-axis ppm interval. A common protein proton preset is 6.5–10.5 ppm. Check that the signals you need fall in the interval. Use **indirect dimension flip** to correct the direction of the selected indirect axis.

The picking threshold is a multiple of noise (σ). Raising it suppresses weaker candidates. **Reference spectrum** in the picking row constrains peak matching. Use **Compare** in the viewer for visual comparison or **Reference scripts** to reuse processing settings. The 1D workflow stops at spectrum generation.

For segmented acquisitions, **Inter-part field drift** applies entered offsets during conversion relative to the first part. The GUI uses SMILE for NUS reconstruction and provides a setting for its thread count.

### 4.2 Script editing, rerunning and reports

- **Script editor** opens the current step's script. Check which dimension a parameter belongs to, save and run, then review the reported changes.
- **Re-run the final script** repeats an existing final processing script. Run the processing step normally to optimise parameters again for the current data.
- **Report** describes inputs, parameters, outputs and quality results. **View log** identifies the failing stage. **Try again** reruns the step after you address the cause. A successful run refreshes the result being viewed.

### 4.3 Reuse scripts for a single data set

Use **Reference scripts** on the data page when a series of comparable samples should share one processing method.

1. Select another data set in the same experiment. Its dimensionality, ordered list of nuclei and sampling mode must match. It must have a saved spectrum script or an applicable successful run snapshot.
2. Choose the stopping step under **Processed to**. FID conversion uses the reference `fid.com` parameters. Spectrum generation also uses the reference spectrum script. The target keeps its own input and output paths.
3. To change the retained direct-axis interval or phase, open **Direct range** or **Phase**. The dialogs start with the reference values. P0 is constant phase and P1 varies along the axis. Set them separately for each logical dimension.
4. **Automatic phase** is off by default. Enable it to search the target's phases after FID conversion and apply them to the reused script. Windowing, zero filling and other settings come from the reference script.
5. Click **Run** and inspect the data's status and log. The reference report records the source, script snapshots and SHA256, overrides, engine logs and outputs. An automatic phase search has a linked record.

### 4.4 Create, maintain and process a group

`Ctrl`-select data sets of the same dimensionality in one experiment and choose **Create data group** from the context menu. The tree opens the new group. Its menu can add matching members, rename the group, remove the group tag or trash the group with its members. A member can be moved out to become an independent data entry. The multi-selection menu can trash the selected data and their outputs after one confirmation.

In the notes table, each column is a member. Remarks come first and fields appear when at least one member has a value. The temperature button cycles through **`·` original order, `>` low to high and `<` high to low**. The table and tree move together. Empty or unreadable temperatures sort last in either direction. Hover over the button to see the meanings.

- **Automatic group processing** chooses parameters for each member. Set the last step under **Processed to**. Automatic 2D processing runs up to five data sets at once by default, adjustable to 1–10. 1D and 3D run sequentially.
- **Process entire group by reference data** reuses one set of scripts and runs members sequentially. The range and phase tables accept per-member overrides. Automatic phase runs after that member's FID conversion.
- The group has a summary, and each member has its own status, log and report. One failed member leaves the others to continue. Removed or trashed entries drop out of future runs.

### 4.5 Interpret Needs update

**Needs update** means the current inputs or scripts differ from the last successful run for the existing output. Expand the reason to identify a missing path, changed file or upstream change. Older records with incomplete provenance show the level of detail available.

Restore access to a missing source, then check the status again. If inputs or scripts changed, rerun from the earliest affected step. **Simple mode** uses the existing output files to decide which steps are available.

## 5. Viewer, slices and comparisons

### 5.1 Open a spectrum and control the view

The viewer's File menu opens the current spectrum, opens an external spectrum or clears the plot. Load project files from the viewer list, the tree or **Display spectrum**. Files selects an input, and Layers controls which spectra appear in the plot. Use **Enlarge** to expand the viewer and close the expanded view to return to three panes.

| Control | Purpose |
| --- | --- |
| Wheel and middle button | Zoom, or hold the middle button and drag to pan |
| 2D/3D left drag | Zoom into a rectangle in normal viewing mode |
| Contour start | Set the starting intensity percentage. Lower values reveal weaker signals and may show more noise |
| Levels | Set how many contour levels are drawn |
| Positive and negative controls | Hide contours of either sign |
| Aspect | Set the horizontal/vertical ratio. Enter applies it, and 0 gives free scaling |
| Full view | Restore the initial or full extent for the current mode |

At more than roughly 150% zoom the overview shows your location in the whole spectrum. The crosshair and readout show the pointer's ppm in 2D/3D. ppm usually decreases to the right. The direct axis is F2 in 2D and F3 in 3D. Repeated nuclei can have x/y/z labels.

### 5.2 View 1D spectra and 1D strips

For a direct 1D spectrum, ppm is horizontal and intensity is vertical with zero centred. The default Aspect is 0.02. The initial view favours the full ppm range, so the water peak may exceed the vertical scale. Zoom out further to see the whole intensity range. With free scaling the wheel changes the vertical scale faster. Middle-button dragging pans.

In a 2D or 3D view, **1D** opens the top and right strips through the crosshair. **Hold the left button and drag** to move the strips. Release to hold the position. Each strip has independent P0/P1 preview controls and its own Reset and Copy. These phases affect the display preview. Set processing phases in the workflow.

### 5.3 3D projections and slices

Selecting 3D data first shows an existing 2D projection when available. Use **Display spectrum** or open the `.ft3` file to see actual slices.

The initial plane is F2–F3 with F1 fixed. Choose the two plotted axes in the plane list, then set the remaining axis with the slider, point number or ppm. All three position controls stay in sync. Use the projection to find regions of interest and slices to inspect a particular third-axis position. Check the active view before working with peaks.

### 5.4 Compare two or three spectra side by side

Enlarge the viewer and open **Compare**. Choose a project result or **Load spectrum…**. Each view has its own extent and display controls. Use **Add third spectrum** or **Remove third spectrum** to change the number of plots.

Planes with compatible nuclei and directions share the crosshair's **displayed ppm** so you can find the same location in each view. Zoom remains independent. Hover over a candidate or layer to check its Bruker title and path.

### 5.5 Overlay, translate and export SVG

1. Set Contour start, Levels, sign and visibility for each side-by-side spectrum, then switch to **Overlay comparison**. The overlay starts with those choices and carries adjustments back on exit.
2. Use colours to identify spectra. The current spectrum is fixed by default. Enable **Use comparison as reference** to choose a fixed comparison spectrum.
3. **Manual adjustment** translates the selected spectrum along an axis. **Auto-fit overlay** detects temporary peaks and estimates an overall ppm shift. Both adjust displayed coordinates. The peak tools collapse in overlay mode.
4. The overlay's full view covers the joint coordinate range. Set a shared Aspect as needed. **Export overlay SVG** lets you choose the range and ratio, preview, and save a vector image. Peak tables and UCSF have separate export actions.

## 6. Peaks, assignments and coordinate alignment

### 6.1 Read and edit the peak table

After **Peak picking**, expand **Peak tools and table**. Assignment holds the user-assigned label. The ppm columns give the position in each dimension. SNR is the value recorded during picking. Empty values indicate that the metric is unavailable.

| Action | Purpose |
| --- | --- |
| Click a peak or row | Locate its counterpart in the table or plot |
| Select mode | Hold the left button and drag to select peaks in a rectangle |
| Add peak mode | Click to add a peak near a local maximum, or at the clicked position if no distinct peak is found |
| Delete selected | Remove selected automatic or manual peaks |
| Assignment | Edit labels in the row's input fields. Click the column heading to toggle labels on the plot |
| Mark size | Change marker size in plot coordinates, with default 0.5 and minimum 0.1 |

Peak selection, peak addition and 1D strips have different left-button modes. Turn off the active mode to return to rectangle zoom. Use **Save peaks** after editing.

### 6.2 Import a POKY/Sparky peak list and align it

1. Pick peaks in the current data to provide an internal table for matching.
2. Select **Import peaks** and choose a `.list`. The program backs up the picked table and its assignments to a CSV in `peaks`, then matches the two tables to estimate an overall ppm translation.
3. Use the source selector to switch between picked and imported tables. Assignments are kept separately. Axis labels indicate the display shift, and the mouse readout shows both aligned and original ppm. Importing again estimates a new shift.
4. Import a NMRFinesse CSV to restore the saved table and remove the imported display shift. This restoration path is available before picking.

### 6.3 Save, export directly or export after alignment

- **Save peaks** writes the current table to the project. Internal records or CSV backups retain metrics such as intensity and SNR.
- **Export directly** writes the selected table's Assignment and ppm coordinates to a `.list` for exchange.
- **After alignment export** asks for a reference `.list`, estimates a translation and writes the shifted ppm. The current project table and spectrum keep their original coordinates.

The GUI `.list` columns are `Assignment w1 w2 [w3]`. Use the internal records or the full CSV to recover metrics such as intensity, volume and SNR.

## 7. Tools menu

### 7.1 Data quality inspection and spectrum quality assessment

**Data quality inspection…** checks converted NMRPipe FIDs. Select one file or a folder containing a slice set. The folder option checks direct child `*.fid` files and writes findings to the global log.

**Spectrum quality assessment…** reads an existing spectrum and reports quality metrics and findings. Both tools are available independently of a project. To omit bad sampling points from a raw Bruker acquisition, use the next tool.

### 7.2 Remove abnormal FIDs and export NUS…

Use this tool when some FIDs in a 2D/3D **uniformly sampled** Bruker acquisition are abnormal. It supports AQSEQ=0, complex direct acquisition and States, States-TPPI or Echo-Antiecho indirect acquisition. The `ser` layout must agree with the acquisition parameters.

1. Select the acquisition and run detection. Inspect zero-based sampling coordinates, original FID rows and diagnostic flags.
2. Automatic selection proposes points with non-finite values, wholly zero points and isolated 12-MAD spikes. A zero phase component or high energy alone is flagged for review. In manual mode you can select or deselect points.
3. Check the number removed and the fraction retained. The tool omits all two or four phase FIDs for each selected point. At least two points must remain.
4. Choose a new output folder. It receives `ser`, `nuslist`, updated acquisition parameters, title and `fid_selection.json`. The original grid and NusTD are retained. A 3D schedule follows acqu2s/acqu3s axis order.
5. Import the new folder as a single data set and use the NUS conversion and reconstruction workflow. Run detection again if the input changes.

This tool writes a new folder. Cleanup of invalid or duplicate points in an existing NUS schedule occurs separately during processing. It backs up the working `ser` and `nuslist` as `.bak` before rewriting them and logs the change.

### 7.3 Export UCSF files…

Open a project and choose **Tools → Export UCSF files…**. The dialog groups data by experiment and enables entries with UCSF files. Select data, click **Export** and confirm the target. The POKY/Sparky spectra folder from Settings supplies the default.

The tool copies existing files, adds a suffix to avoid collisions, and reports successes and failures. To create UCSF files first, complete 2D/3D spectrum processing with `pipe2ucsf` available. The 1D route writes a NMRPipe spectrum.

## 8. Software settings

### 8.1 Tool paths and default folders

The top-bar **Settings** opens **Software settings** directly. Use **Browse…** to choose an executable or script for a tool path and a folder for a directory field.

| Setting | Purpose |
| --- | --- |
| NMRPipe path | Locate the processing engine |
| bruker path | Locate the Bruker conversion tool |
| proj3D.tcl path | Locate the projection script |
| pipe2ucsf path | Write UCSF files for POKY/Sparky |
| SMILE plugin | Check whether NUS reconstruction is available |
| Data directory | Choose the starting folder for import browsing |
| POKY/Sparky spectra folder | Choose the default UCSF copy destination through auto-find, browsing or manual entry |

Leave tool paths blank to use automatic discovery. Browse starts from the entered path when available.

### 8.2 Interface, matching, resources and defaults

- **Language and font size.** Follow the system or choose Chinese or English and restart when prompted. Use automatic sizing or select 8–18 pt.
- **Default linewidth and alignment tolerance.** Linewidth defaults are in Hz by nucleus. Alignment and reference matching tolerances are in ppm. A smaller value requires a closer match.
- **SMILE threads and 2D concurrency.** Threads control one reconstruction, defaulting to two within the machine's limit. The 2D setting controls simultaneous data sets in automatic processing, defaulting to five.
- **Simple mode.** Use files from the preceding step to determine which actions are available.
- **Restore defaults.** Reset fields in the dialog, then save to apply the defaults. Settings belong to the current machine.

## 9. Outputs and troubleshooting

### 9.1 Find and retain results

| Data subfolder | Contents |
| --- | --- |
| `raw` | Raw data used in the project, links or copies |
| `process` | FID and processing scripts |
| `spectra` | Final spectra, available projections and UCSF |
| `peaks` | Picked peaks, internal saves and CSV backups |
| `figures` and `report` | Figures, reports, logs and reference processing records |

Manual `.list`, SVG and UCSF exports go to the chosen destination. Deleting data uses a recoverable trash route. Retain source folders still linked by other entries.

### 9.2 Where to start when something looks wrong

| Symptom | Check first |
| --- | --- |
| FID or spectrum processing fails | Tool paths, raw files and the first error in the data log |
| Reference list is empty | Another data set in the same experiment with matching dimensions, ordered nuclei, sampling mode and a saved script |
| Selecting 3D shows a 2D plot | Check for a projection and use Display spectrum or open `.ft3` |
| Expected peaks are missing | Direct-axis range, plane, slice, signs and contour start |
| Peak export is unavailable | Loaded spectrum, nonempty table and whether the plot shows a projection or overlay |
| A UCSF entry cannot be selected | Whether the data has a UCSF file in `spectra` |
| Needs update | The named missing path, changed file or upstream step |

When reporting an issue, include the version shown in About, your desktop session, the steps and the log. See the [troubleshooting guide](https://github.com/RociferX/nmrfinesse/blob/main/docs/troubleshooting.md) and [real-data validation](https://github.com/RociferX/nmrfinesse/blob/main/docs/evidence/real-data-comparison.md) for details.
