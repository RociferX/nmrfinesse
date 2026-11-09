# FAQ

### Is NMRFinesse a replacement for NMRPipe?

No. NMRFinesse decides *what* to run and records *why*,
then drives NMRPipe to do the processing. You need an NMRPipe installation.

### Do I need Python to use NMRFinesse?

Not for the AppImage: it bundles Python and Qt. For the source path you need Python 3.12+ and the
editable repository checkout.

### Can I run it on Windows or macOS?

Linux is the target runtime; Windows is an editing environment. macOS has not been validated.
Download the Linux AppImage from the [latest release](https://github.com/RociferX/nmrfinesse/releases/latest).

### Does NMRFinesse send my data anywhere?

No. There is no telemetry, upload or account requirement. Processing is local, and the
application itself makes no network calls. Source installation downloads dependencies; the AppImage
includes its runtime.

### Does it modify my raw data?

Source-level cleanup of invalid or duplicate NUS points can rewrite acquisition files. It creates `.bak` backups and records the change in logs and audit records. Linked or referenced imports still depend on their source directories. The Tools abnormal-FID-to-NUS export writes a new folder and preserves its input. GUI project deletion uses the system trash.

### Does it handle non-uniform sampling?

Yes, for both 2D and 3D, using SMILE reconstruction. SMILE parameter optimisation and ranked
reruns are temporarily unavailable in the GUI.

### Which dimensions does batch processing support?

Batch groups support 1D, 2D and 3D separately. Automatic 2D processing defaults to five concurrent data sets, configurable from 1 to 10. 1D, 3D and reference-script groups run sequentially.

### Why does it refuse to process when sampling is "uncertain"?

Because uniform and NUS change the meaning of every processing parameter. Guessing there produces
a spectrum that looks processed and is quietly wrong. Resolve the metadata conflict first; the
log states which rule fired.

### Is there an English interface?

Yes - English is the interface's source language, so the menus, panel labels, statuses and
messages are English by default. The same build also speaks Chinese: the interface follows the
system language, or you can pin it with `NMRFINESSE_LANG=zh` (the Chinese text lives in
`ui_support/locales/zh.json`). One code base, two languages; a Chinese edition of the
**documentation** is in `Chinese_version/`.

**You can also change it inside the GUI**: `Settings -> Interface
language`, choosing "Follow the system language / Chinese / English"; it is saved to the local
override config and takes effect after a restart. The resolution order is "explicit setting,
then the `NMRFINESSE_LANG` environment variable, then the preference from the settings, then the
system locale (QLocale / `LANG` / `LC_ALL`), then the default of this tree". `NMRFINESSE_LANG`
deliberately comes before the setting so that `NMRFINESSE_LANG=zh ./NMRFinesse.AppImage` keeps
overriding a stale setting for one run - while `LANG=en_US.UTF-8` is only the system locale and
does **not** override the Chinese you picked in the settings.

### Does NMRFinesse include HSQC CSP analysis?

No. NMRFinesse does not provide HSQC CSP analysis. Downstream analysis code can consume
`nmrfinesse_api` output.

### How is the version number managed?

`core/__init__.py` defines `__version__`. `pyproject.toml` and the AppImage build read it, and run
records store it. The scripting API version is managed separately by `nmrfinesse_api.API_VERSION`.

### How do I cite NMRFinesse?

Citation metadata is in [CITATION.cff](../CITATION.cff): author Xuanfeng Li, affiliation University
of Science and Technology of China. The concept DOI is
[10.5281/zenodo.22909415](https://doi.org/10.5281/zenodo.22909415). Include the software version;
obtain a version-specific DOI from that release’s archive record when needed.
If you publish results, also cite NMRPipe and SMILE;
see [THIRD_PARTY.md](../THIRD_PARTY.md).

### Can I use NMRFinesse commercially?

Yes. This project's own source is Apache-2.0: the verbatim text is [LICENSE](../LICENSE) and the
copyright line plus SPDX identifier are in [NOTICE](../NOTICE). The Qt/PySide6 libraries bundled
inside the packaged distribution are LGPL-3.0, which constrains that distribution, not your use of
the source. [LICENSE_OPTIONS.md](../LICENSE_OPTIONS.md) records the source/binary split and
[THIRD_PARTY.md](../THIRD_PARTY.md) the third-party components.

### How do I know a published result is reproducible from NMRFinesse?

Run records contain the resolved parameters, the scripts used, the software version, the external
tool versions and the warnings; generated scripts and spectra are kept. See
[processing-model.md](processing-model.md) and
[external-api/06-outputs-and-records.md](external-api/06-outputs-and-records.md).
