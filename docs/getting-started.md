# Getting started

This guide covers first data inspection and the processing boundary. For Linux desktop use,
download the [1.0.12 AppImage](https://github.com/RociferX/nmrfinesse/releases/tag/v1.0.12).
For source installation, follow the steps below.

## Install from source

Linux is the target runtime. Create an editable installation:

```bash
git clone https://github.com/RociferX/nmrfinesse.git
cd nmrfinesse
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
python main.py
```

For the complete dependency and packaged-resource notes, see
[Installation](installation.md). NMRPipe is required for spectral conversion and processing;
SMILE is required for NUS reconstruction. NMRFinesse does not install or bundle these external tools.

## Inspect a Bruker dataset

Parsing and data understanding can be used without NMRPipe. In a source checkout, run:

```bash
python examples/quickstart.py /path/to/bruker/dataset
```

The inspection reports available acquisition files, dimensionality and axis metadata, experiment
classification, sampling classification and its evidence, time-domain layout, and whether external
processing engines can be located. To make a clearly synthetic example:

```bash
python examples/make_synthetic_dataset.py --out ./example_data/hsqc_2d
python examples/quickstart.py ./example_data/hsqc_2d
```

Synthetic data are for software checks and walkthroughs only, not scientific conclusions.

## Configure external engines

NMRPipe is resolved from the explicit `backend.nmrpipe.path` or
`backend.nmrpipe.nmrpipe_bin` configuration first, then `PATH`, the environment available
through `csh`, and supported common locations. SMILE is located with the NMRPipe installation.
Missing engines are reported when an operation needs them; the application does not silently
substitute a different processing engine.

Use the tracked defaults in `nmrfinesse_data/config/nmrfinesse.yaml`. For a machine-local path, copy
the file to the ignored `nmrfinesse_data/config/nmrfinesse.local.yaml` and edit the local copy:

```yaml
backend:
  nmrpipe:
    path: /path/to/nmrpipe/bin
```

Do not commit machine-specific paths. See [External dependencies](external-dependencies.md) for
resource discovery, memory notes, and what remains available without NMRPipe.

## Run a processing study

The Python API and command line use the same backend. A study consists of registered input
conditions, a frozen reference, and user-supplied parameter combinations:

```bash
python -m nmrfinesse_api init --study ./study --dataset /path/to/bruker/dataset --condition A
python -m nmrfinesse_api reference --study ./study
python -m nmrfinesse_api peaks --study ./study
python -m nmrfinesse_api sweep --study ./study --reference ./study --combos design.csv
python -m nmrfinesse_api report --study ./study
```

For a complete option list, see [CLI reference](cli.md). The API runs peak selection independently
on each candidate spectrum using the reference-locked threshold, then writes one
`peak_table_parabolic.csv` per study/run level as documented in
[Outputs and records](external-api/06-outputs-and-records.md). Localization is three-point
parabolic only.

## Current source interface

Help → Usage tutorial has nine navigable sections with separate section and task headings.
The experiment page has three horizontal import cards (single, segmented, batch), actions above
their descriptions, and the sample-data table below. Import-and-group is off by default.
Batch processing supports 2D only; process 3D data individually.
Tools → Export UCSF files… becomes available after opening a project. Configure its destination
through automatic POKY/Sparky discovery or Browse in Settings.
Tools also provides read-only FID checks and an automatic/manual abnormal-FID selection tool for
2D/3D uniform Bruker acquisitions. The latter exports a new NUS folder, omits complete phase groups,
retains the source, and records its schedule and conversion report.

The normal startup window uses a 1080p workspace baseline: smaller screens scroll, while larger
screens retain the baseline window. Automatic fonts change on maximize/fullscreen, not ordinary resize.
Pure 1D defaults to Aspect 0.02. In 2D/3D 1D-strip mode, hold the left button to move the strips;
top and right strips have independent display phase controls. Comparison crosshairs share displayed
ppm coordinates; overlay comparison retains contour settings. File/color tooltips include title text.
Needs-update details identify missing paths or changed files; old records explicitly identify missing
provenance. Picked/imported peak tables retain separate assignments. CSV restores the full table;
GUI `.list` exports contain assignments and coordinates only.

The v1.0.12 AppImage includes these features. Subsequent source changes and rebuilt
AppImages are published separately. See the [GUI guide](gui.md) for full instructions.

## Where to go next

- [Installation](installation.md) — source and versioned Linux AppImage boundary.
- [External dependencies](external-dependencies.md) — NMRPipe/SMILE discovery and resource notes.
- [Processing model](processing-model.md) and [QC system](qc-system.md) — processing behaviour.
- [External API](external-api/README.md) — Python, CLI, records, and examples.
- [Troubleshooting](troubleshooting.md) and [FAQ](faq.md) — common issues.
