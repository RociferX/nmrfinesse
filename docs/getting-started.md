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
`backend.nmrpipe.nmrpipe_bin` configuration first, then the environment available through
`csh` or `tcsh`, then `PATH`. SMILE is located with the NMRPipe installation.
Missing engines are reported when an operation needs them; the application does not silently
substitute a different processing engine.

The repository defaults are in `nmrfinesse_data/config/nmrfinesse.yaml`. In a source checkout,
create a sibling file named `nmrfinesse.local.yaml` and put machine-specific overrides there.
For the AppImage, use **Settings** to save the override to your user configuration.

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

Open **Help → Usage tutorial** or read the [GUI guide](gui.md). Its nine sections explain each action, the required inputs, where to find the results and how to diagnose common issues.

For a first run, create a project and experiment, import one Bruker acquisition, and run **Generate FID → Generate spectrum → Peak picking** for 2D/3D data. Use **Reference scripts** when processing comparable data with a shared script. In batch import, **All** checks every visible path for removal. **Batch import** uses the full filtered list.

The guide follows the current source. To check an installed version's features, use **Help → About** and its release notes.

## Where to go next

- [Installation](installation.md) — source and versioned Linux AppImage boundary.
- [External dependencies](external-dependencies.md) — NMRPipe/SMILE discovery and resource notes.
- [Processing model](processing-model.md) and [QC system](qc-system.md) — processing behaviour.
- [External API](external-api/README.md) — Python, CLI, records, and examples.
- [Troubleshooting](troubleshooting.md) and [FAQ](faq.md) — common issues.
