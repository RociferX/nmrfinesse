"""Inspect uniform Bruker 2D/3D FIDs and export a selected NUS subset."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path

import numpy as np

from core.data.bruker_dtype import sample_dtype  # noqa: E402
from core.data.ser_layout import solve_row_points  # noqa: E402
from core.experiment.experiment_classifier import is_kinetics_source  # noqa: E402
from core.project.manager import atomic_write_text
from workflow.direct_diagnostics import _find_bad_points  # noqa: E402


def _params(text: str) -> dict[str, str]:
    return dict(re.findall(r"^##\$\s*(\w+)\s*=\s*(\S+)", text, re.MULTILINE))


def _set(text: str, key: str, value: object) -> str:
    pattern = rf"^##\$\s*{re.escape(key)}\s*=\s*[^\r\n]*"
    line = f"##${key}= {value}"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, lambda _: line, text, count=1, flags=re.MULTILINE)
    # Keep new scalar parameters before the JCAMP terminator.
    if "##END=" in text:
        return text.replace("##END=", f"{line}\n##END=", 1)
    return text.rstrip() + f"\n{line}\n"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprint(source: Path) -> dict:
    files = {p.name: _sha(p) for p in sorted(source.iterdir()) if p.is_file()}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"sha256": digest, "files": files}


def _layout(source: Path) -> dict:
    names = ["acqus", "acqu2s"]
    if (source / "acqu3s").exists():
        names.append("acqu3s")
    if (source / "acqu4s").exists() or is_kinetics_source(source):
        raise ValueError("Only spectral 2D/3D inputs are supported; not kinetics/pseudo dimensions")
    texts = [(source / name).read_text(encoding="latin-1") for name in names]
    pars = [_params(text) for text in texts]
    if int(pars[0].get("AQSEQ", "0")) != 0:
        raise ValueError("Only AQSEQ=0 is supported by the validated evidence row ordering")
    if int(pars[0].get("AQ_mod", "-1")) not in (1, 3):
        raise ValueError("Complex direct acquisition AQ_mod=1/3 is required")
    schedule = pars[0].get("NUSLIST", "").strip("<>")
    if (
        (source / "nuslist").exists()
        or (schedule and (source / schedule).exists())
        or any(int(p.get("FnTYPE", "0")) == 2 for p in pars)
    ):
        raise ValueError("Input must be uniform, not an existing NUS dataset")
    td = [int(p["TD"]) for p in pars]
    if any(n <= 0 or n % 2 for n in td):
        raise ValueError("All complex dimensions require positive even TD")
    if any(int(p.get("FnMODE", "-1")) not in (4, 5, 6) for p in pars[1:]):
        raise ValueError("Indirect axes must declare States/States-TPPI/Echo-Antiecho")
    dtype = sample_dtype(pars[0])
    size = (source / "ser").stat().st_size
    row_points = solve_row_points(td[0], dtype.itemsize, size)
    if row_points is None or size != math.prod(td[1:]) * row_points * dtype.itemsize:
        raise ValueError("SER size does not exactly match the declared padded uniform grid")
    return dict(
        names=names,
        texts=texts,
        params=pars,
        td=td,
        dtype=dtype,
        row_points=row_points,
        row_bytes=row_points * dtype.itemsize,
        grid=[n // 2 for n in td[1:]],
    )


def _rows(coordinate: tuple[int, ...], td: list[int]) -> list[int]:
    y = coordinate[0]
    return [
        (2 * coordinate[1] + zp) * td[1] + 2 * y + yp if len(coordinate) == 2 else 2 * y + yp
        for zp in range(2 if len(coordinate) == 2 else 1)
        for yp in range(2)
    ]


def inspect_uniform(source: Path) -> dict:
    """Return per-increment findings without changing acquisition bytes."""
    source = Path(source).resolve(strict=True)
    layout = _layout(source)
    td, grid = layout["td"], layout["grid"]
    delay = max(0, math.ceil(float(layout["params"][0].get("GRPDLY", "0"))))
    if td[0] // 2 - delay < 5:
        raise ValueError("Insufficient direct points after the declared group delay")
    before = _source_fingerprint(source)
    data = np.memmap(
        source / "ser",
        dtype=layout["dtype"],
        mode="r",
        shape=(math.prod(td[1:]), layout["row_points"]),
    )
    points = []
    try:
        for index in range(math.prod(grid)):
            coord = (index % grid[0], index // grid[0]) if len(grid) == 2 else (index,)
            rows = _rows(coord, td)
            reasons, advisory = [], []
            energy = 0.0
            zero_rows = 0
            spike_rows = []
            for row_index in rows:
                row = np.asarray(data[row_index, : td[0]], dtype=np.float64)
                if not np.isfinite(row).all():
                    reasons.append("nonfinite")
                    continue
                zero_rows += int(not np.any(row))
                trace = row[::2] + 1j * row[1::2]
                trace = trace[delay:]
                energy += float(np.mean(np.abs(trace) ** 2))
                if np.any(_find_bad_points(trace)):
                    spike_rows.append(row_index)
            if zero_rows == len(rows):
                reasons.append("all_zero_increment")
            elif zero_rows:
                advisory.append("zero_phase_component")
            if spike_rows:
                reasons.append("isolated_spike")
            points.append(
                dict(
                    coordinate=list(coord),
                    raw_rows=rows,
                    reasons=sorted(set(reasons)),
                    advisory=advisory,
                    energy=energy if math.isfinite(energy) else None,
                    spike_rows=spike_rows,
                )
            )
    finally:
        del data
    finite_energy = [p["energy"] for p in points if p["energy"] is not None and p["energy"] > 0]
    median = float(np.median(finite_energy)) if finite_energy else 0.0
    for point in points:
        if median and point["energy"] is not None and point["energy"] > 100 * median:
            point["advisory"].append("high_energy_over_100x_median")
        point["auto_remove"] = bool(point["reasons"])
    if _source_fingerprint(source) != before:
        raise ValueError("Source changed during inspection; scan again")
    return dict(
        ndim=len(td),
        complex_grid=grid,
        coordinate_base=0,
        coordinate_order="acqu2s, acqu3s (if present); y-fast",
        raw_row_base=0,
        group_delay_skipped=delay,
        source=before,
        points=points,
    )


def export_nus(
    source: Path,
    destination: Path,
    *,
    automatic: bool = False,
    excluded: list[tuple[int, ...]] | None = None,
    expected_source: dict | None = None,
) -> dict:
    """Export either automatic findings or the user's exact coordinate selection."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be disjoint")
    if destination.exists():
        raise ValueError("Destination exists; choose a new directory")
    if automatic and excluded is not None:
        raise ValueError("Choose automatic OR manual selection")
    report = inspect_uniform(source)
    if expected_source is not None and report["source"] != expected_source:
        raise ValueError("Source changed since the displayed inspection; inspect again")
    layout = _layout(source)
    known = {tuple(p["coordinate"]) for p in report["points"]}
    remove = (
        {tuple(p["coordinate"]) for p in report["points"] if p["auto_remove"]}
        if automatic
        else set(excluded or [])
    )
    if not remove <= known:
        raise ValueError("Deletion coordinates are outside the original complex grid")
    keep = [
        tuple(p["coordinate"]) for p in report["points"] if tuple(p["coordinate"]) not in remove
    ]
    if not remove:
        raise ValueError("No increments selected for deletion; uniform source is unchanged")
    if len(keep) < 2:
        raise ValueError("At least two complete increments must remain")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".nus-export-", dir=destination.parent))
    try:
        for p in source.iterdir():
            if p.is_file() and p.name not in ("ser", "fid", "nuslist"):
                shutil.copyfile(p, staging / p.name)
        (staging / "nuslist").write_text(
            "".join(" ".join(map(str, c)) + "\n" for c in keep), encoding="ascii"
        )
        with (source / "ser").open("rb") as src, (staging / "ser").open("wb") as dst:
            for coordinate in keep:
                for row in _rows(coordinate, layout["td"]):
                    src.seek(row * layout["row_bytes"])
                    block = src.read(layout["row_bytes"])
                    if len(block) != layout["row_bytes"]:
                        raise ValueError("Source truncated during export")
                    dst.write(block)
        title = source / "pdata/1/title"
        if title.is_file():
            (staging / "pdata/1").mkdir(parents=True)
            shutil.copyfile(title, staging / "pdata/1/title")
        for i, (name, text) in enumerate(zip(layout["names"], layout["texts"], strict=True)):
            if i == 0:
                text = _set(
                    _set(_set(text, "FnTYPE", 2), "NUSLIST", "<nuslist>"),
                    "NusAMOUNT",
                    100 * len(keep) / len(known),
                )
            else:
                text = _set(text, "NusTD", layout["td"][i])
            (staging / name).write_text(text, encoding="latin-1")
            live_name = name.removesuffix("s")
            if (staging / live_name).exists():
                (staging / live_name).write_text(text, encoding="latin-1")
        report.update(
            destination=str(destination),
            source_directory=str(source),
            selection="automatic" if automatic else "manual",
            deleted_coordinates=[list(c) for c in sorted(remove)],
            sample_count=len(keep),
            sampling_fraction=len(keep) / len(known),
            retained_rows=len(keep) * 2 ** len(layout["grid"]),
            nuslist_sha256=_sha(staging / "nuslist"),
            ser_sha256=_sha(staging / "ser"),
        )
        if _source_fingerprint(source) != report["source"]:
            raise ValueError("Source changed during export")
        atomic_write_text(
            staging / "fid_selection.json", json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return report
