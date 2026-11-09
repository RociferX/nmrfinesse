# Installation

On Linux, download the desktop AppImage from the [latest release](https://github.com/RociferX/nmrfinesse/releases/latest).
For Python and CLI tools, follow the source installation steps below.

## AppImage (Linux)

Download the AppImage and checksum file into an empty directory. Verify and launch the app there.

```bash
sha256sum -c SHA256SUMS-*.txt
chmod +x NMRFinesse-*-x86_64.AppImage
./NMRFinesse-*-x86_64.AppImage --licenses
./NMRFinesse-*-x86_64.AppImage
```

The AppImage includes third-party licence notices, including those for PySide6/Qt. See the
release assets and [THIRD_PARTY.md](../THIRD_PARTY.md) for distribution information.

## Source installation

```bash
git clone https://github.com/RociferX/nmrfinesse.git
cd nmrfinesse
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Launch the source GUI from the checkout with `python main.py`. It creates or reuses the application's local environment.

Packaged installs and wheels include runtime resources (`nmrfinesse_data/config`,
`nmrfinesse_data/presets`, `gui/assets`, `ui_support/locales`). Real processing requires a separately
installed NMRPipe; NUS reconstruction also requires SMILE. Neither tool is downloaded or bundled
by NMRFinesse.

## Developers: editable source install

```bash
git clone https://github.com/RociferX/nmrfinesse.git
cd nmrfinesse
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional dependency groups (declared in `pyproject.toml`):

```bash
pip install -e ".[test]"    # pytest
pip install -e ".[dev]"     # pytest + ruff
pip install -e ".[docs]"    # documentation tooling
```

`python main.py` creates or reuses the local application environment on first run.

The editable install exposes one console script:

| Command | What it does |
| --- | --- |
| `nmrfinesse-viewer` | Standalone spectrum viewer (`python -m viewer` works too) |

Use `python main.py` to start the main GUI from an editable checkout.

The processing command line lives in the `nmrfinesse_api` package:

```bash
python -m nmrfinesse_api --help
```

## Verifying an installation

```bash
python -m pytest -q                                       # full test suite
python -m ruff check .                                    # static checks
python -c "import core, nmrfinesse_api, gui, viewer; print('imports ok')"
python examples/make_synthetic_dataset.py --out example_data/hsqc_2d
python examples/quickstart.py example_data/hsqc_2d
```

GUI tests need a display or an offscreen Qt platform:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## Upgrading and uninstalling

```bash
pip install -e .            # re-run after editing pyproject.toml or entry points
pip uninstall NMRFinesse      # removes the package and its console scripts
```

Uninstalling never deletes your projects or studies: those live in the directories you chose.
