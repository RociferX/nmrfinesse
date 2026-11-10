"""Copy selected project UCSF results to an external spectra directory."""

from __future__ import annotations

import re
import shutil
from pathlib import Path


def ucsf_export_entries(manager) -> list[dict]:
    """List active project data and its current UCSF sidecar, grouped by experiment."""
    entries = []
    if manager.project is None:
        return entries
    for experiment in manager.project.experiments:
        if experiment.trashed:
            continue
        for data in experiment.data:
            if data.trashed:
                continue
            directory = manager.data_dir(experiment.id, data.id, "spectra")
            candidates = []
            if data.spectrum_path:
                spectrum = Path(data.spectrum_path)
                if not spectrum.is_absolute():
                    spectrum = manager.root / spectrum
                candidates.append(spectrum.with_suffix(".ucsf"))
            candidates.extend([directory / f"{experiment.id}-{data.id}.ucsf",
                               directory / f"{data.id}.ucsf"])
            available = [
                path for path in directory.glob("*.ucsf")
                if not path.name.startswith(f"{data.id}_")
            ]
            if len(available) == 1:
                candidates.extend(available)
            source = next((p for p in candidates if p.is_file()), None)
            entries.append({
                "exp_id": experiment.id, "data_id": data.id,
                "experiment": experiment.title or experiment.id,
                "data": data.title or data.id,
                "project": manager.project.name,
                "source": str(source) if source is not None else "",
            })
    return entries


def _filename(entry) -> str:
    parts = [entry[key] for key in ("project", "experiment", "data")]
    return "_".join(re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', part).strip(" .") or "data"
                    for part in parts) + ".ucsf"


def transfer_ucsf_files(entries: list[dict], destination: Path) -> dict:
    """Copy without deleting sources or overwriting existing destination files."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied, errors = [], []
    for entry in entries:
        target = None
        created = False
        try:
            source = Path(entry["source"])
            if not entry["source"] or not source.is_file():
                raise FileNotFoundError(entry["source"])
            name = Path(_filename(entry))
            counter = 0
            while True:
                target = destination / (name.name if counter == 0
                                        else f"{name.stem}_{counter}{name.suffix}")
                try:
                    output = target.open("xb")
                    created = True
                    break
                except FileExistsError:
                    counter += 1
            with output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
            copied.append(str(target))
        except OSError as exc:
            if created:
                target.unlink(missing_ok=True)
            errors.append(f'{entry["experiment"]} / {entry["data"]}: {exc}')
    return {"copied": copied, "errors": errors}
