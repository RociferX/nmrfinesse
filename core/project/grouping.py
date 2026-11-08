"""Cheap group membership and dimension checks without reading spectral arrays."""

import json
from pathlib import Path


def raw_ndim(path):
    path = Path(path)
    if any((path / name).is_file() for name in ("acqu3s", "acqu3")):
        return 3
    if any((path / name).is_file() for name in ("acqu2s", "acqu2")):
        return 2
    return 1 if (path / "acqus").is_file() else None


def data_ndim(manager, exp_id, data_id):
    data = manager.data(exp_id, data_id)
    raw = Path(data.raw_dir or data.source)
    if not raw.is_absolute():
        raw = manager.root / raw
    value = raw_ndim(raw)
    if value:
        return value
    if data.metadata_path:
        path = Path(data.metadata_path)
        if not path.is_absolute():
            path = manager.root / path
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            value = (
                metadata.get("ndim")
                or metadata.get("dataset", {}).get("ndim")
                or metadata.get("experiment", {}).get("ndim")
            )
            if value in (1, 2, 3):
                return value
        except (OSError, ValueError):
            pass
    suffix = Path(data.spectrum_path or "").suffix.lower()
    return {".ft1": 1, ".ft3": 3}.get(suffix, 2)


def active_members(manager, exp_id, group_id):
    exp = manager.project.experiment(exp_id) if manager.project else None
    group = manager.group(exp_id, group_id) if exp else None
    return (
        [data for data in exp.data if not data.trashed and data.id in group.data_ids]
        if group
        else []
    )


def validate_dimensions(manager, exp_id, data_ids):
    from core.project import ProjectError

    dimensions = {data_ndim(manager, exp_id, key) for key in data_ids}
    if len(dimensions) > 1:
        from ui_support.i18n import tr

        raise ProjectError(tr("All data in a group must have the same dimensionality"))
    return next(iter(dimensions), None)
