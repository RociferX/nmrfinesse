"""Process homogeneous 1D/2D/3D groups with separate per-data records.

Automatic 2D groups support bounded parallelism (max_workers=1 by default, capped at 10).
1D/3D and reference-script groups run sequentially. One failed member does not abort the group.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from core.project import ProjectManager
from core.project.run_refs import STEP_RUN_REFS
from ui_support.i18n import tr

# Supported batch steps (aligned with the first five steps of gui/pipeline_panel.PIPELINE_STEPS;
# Engine does not import Qt, batch group semantics are aligned by reading the status file) Batch
# steps (aligned with gui/pipeline_panel.PIPELINE_STEPS; Engine does not import Qt).
BATCH_STEPS = ("import", "fid", "spectrum", "peaks")





# Homogeneous groups support all three dimensions.
BATCH_SUPPORTED_NDIM = (1, 2, 3)



BATCH_COOLDOWN_SECONDS = 2.0

STATE_FILENAME = ".pipeline_state.json"


class BatchError(Exception):
    """Batch engine error (parameter check/Target analysis/Step not supported)."""


def _data_exists(manager: ProjectManager, exp_id: str, data_id: str) -> bool:
    """Whether the data entry exists (members in the group may have been deleted)."""
    try:
        return not manager.data(exp_id, data_id).trashed
    except Exception:  # noqa: BLE001 - ProjectError Unified as non-existence.
        return False


def _batch_id_of(manager: ProjectManager, exp_id: str, data_id: str) -> str:
    """Read the batch key of GUI side.pipeline_state.json (same semantics as
    gui.pipeline_state.batch_id).
    """
    path = manager.data_base(exp_id, data_id) / STATE_FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        value = raw.get("batch", "")
    except (OSError, json.JSONDecodeError):
        value = ""
    return str(value) if value else ""


def _resolve_data_ids(
    manager: ProjectManager, exp_id: str, targets: str | Iterable[str]
) -> tuple[list[str], str]:
    """Parse batch_id(str) or data_ids(iterable) into a list of data ids in the experiment. Return
    (data_ids, batch_id); when data_ids is explicit, batch_id is an empty string.
    """
    entry = manager.project.experiment(exp_id) if manager.project is not None else None
    if entry is None:
        raise BatchError(tr("experiment does not exist: {p0}", p0=exp_id))
    if isinstance(targets, str):
        batch = targets
        # Schema 1.4 data group priority (project.json); old batch group mark (pipeline_state)
        # compatible.
        group = manager.group(exp_id, batch)
        if group is not None:
            data_ids = [
                d
                for d in group.data_ids
                if _data_exists(manager, exp_id, d)
            ]
            if not data_ids:
                raise BatchError(tr(
                    "data group {p0} in experiment {p1} There is no data "
                    "in",
                    p0=batch,
                    p1=exp_id,
                ))
            return data_ids, batch
        data_ids = [
            data.id
            for data in entry.data
            if not getattr(data, "trashed", False)
            and _batch_id_of(manager, exp_id, data.id) == batch
        ]
        if not data_ids:
            raise BatchError(tr(
                "batch group {p0} in experiment {p1} There is no data "
                "in",
                p0=batch,
                p1=exp_id,
            ))
        return data_ids, batch
    data_ids = [str(d) for d in targets]
    if not data_ids:
        raise BatchError(tr("No data specified (data_ids is empty)"))
    for data_id in data_ids:
        try:
            manager.data(exp_id, data_id)
        except Exception as exc:  # noqa: BLE001 - ProjectError Unified conversion to BatchError.
            raise BatchError(tr("Data does not exist: {p0}/{p1}", p0=exp_id, p1=data_id)) from exc
    return data_ids, ""


def _reference_spectrum_params(
    manager: ProjectManager,
    exp_id: str,
    data_id: str,
) -> dict[str, Any]:
    """Get the valid parameters of the latest successful spectrum run of the reference data
    (processing script / parameter reuse). Get the last successful run in the WorkflowRun append
    order and workflow_ref belongs to the spectrum chain; no available run returns an empty dict
    (the caller falls back to unified automatic processing by default). Fix 24: ref table and
    Pipeline/Project tree same origin(core.project.run_refs), data_id and workflow_ref are
    changed to **exact match** -- The original substring matching will mistakenly run refs with
    similar names as spectrum, and finalize_nus/generate_spectrum in the table are never
    registered refs.
    """
    if manager.project is None:
        return {}
    spectrum_refs = STEP_RUN_REFS["spectrum"]
    wanted = str(data_id)
    matches = [
        run
        for run in manager.project.workflow_runs
        if run.experiment_id == exp_id
        and str((run.inputs or {}).get("data_id", "")) == wanted
        and run.status == "success"
        and run.workflow_ref in spectrum_refs
    ]
    if not matches:
        return {}
    return dict(matches[-1].params or {})


def _run_step(
    manager: ProjectManager,
    exp_id: str,
    data_id: str,
    step: str,
    backend: Any,
    params: dict[str, Any],
    progress: Callable[[str], None] | None = None,
) -> Any:
    """Execute a single step and return the step product (fid/spectrum path, peaks dict, etc.)."""
    if step == "import":
        # Import is the input of batch processing: if the data entry already exists, it is deemed to
        # have been imported (no re-creating the entry).
        data = manager.data(exp_id, data_id)
        raw = Path(data.raw_dir) if getattr(data, "raw_dir", "") else Path(data.source)
        if not raw.is_absolute():
            raw = manager.root / raw
        return {
            "status": "already_imported",
            "data_id": data_id,
            "source": str(raw),
        }
    if step == "fid":
        from workflow.stepwise import generate_fid

        return generate_fid(
            manager, exp_id, data_id, backend, progress=progress
        )
    if step == "spectrum":
        from workflow.stepwise import generate_spectrum

        return generate_spectrum(
            manager,
            exp_id,
            data_id,
            backend,
            params=params,
            progress=progress,
        )
    if step == "peaks":
        from workflow.pick_peaks import pick_peaks

        return pick_peaks(manager, exp_id, data_id, backend)
    raise BatchError(tr("Unsupported batch steps: {p0}", p0=step))




def _step_already_done(manager: object, exp_id: str, data_id: str, step: str) -> bool:
    """This data specifies whether the step has been completed (the output file exists) and is used
    to skip processed data in batches.
    """
    if step == "import":
        return False
    try:
        data = manager.data(exp_id, data_id)
    except Exception:
        return False
    if step == "fid":
        p = getattr(data, "fid_path", "")
        return bool(p) and Path(p).is_file()
    if step == "spectrum":
        p = getattr(data, "spectrum_path", "")
        return bool(p) and Path(p).is_file()
    if step == "peaks":
        try:
            peaks_dir = manager.data_dir(exp_id, data_id, "peaks")
        except Exception:  # noqa: BLE001 -
            return False
        for pat in (f"{exp_id}-{data_id}.list", f"{exp_id}-{data_id}.csv"):
            if (peaks_dir / pat).is_file():
                return True
        return False
    return False


def _data_source_path(manager: object, exp_id: str, data_id: str):
    """Get the original directory of the data (raw_dir or source)."""
    data = manager.data(exp_id, data_id)
    source = Path(data.raw_dir) if getattr(data, "raw_dir", "") else Path(data.source)
    if not source.is_absolute():
        source = manager.root / source
    return source


def _data_fingerprint(manager: object, exp_id: str, data_id: str):
    """Data spectrum fingerprint: dimension + each dimension (core, spectrum width, carrier
    frequency), used to compare types/condition.
    """
    from core.data.bruker_reader import read_dataset
    exp = read_dataset(_data_source_path(manager, exp_id, data_id))
    dims = tuple(
        (d.nucleus, round(float(d.sw or 0.0), 3), round(float(d.o1 or 0.0), 3))
        for d in exp.dimensions
    )
    return (exp.ndim, dims)


def _fingerprints_match(ref, member):
    """Compare two spectral fingerprints to see if they are consistent (type/condition); return
    (whether they are consistent, reason).
    """
    if ref[0] != member[0]:
        return False, tr("different dimensions")
    if len(ref[1]) != len(member[1]):
        return False, tr("different number of dimensions")
    for (rn, rsw, ro1), (mn, msw, mo1) in zip(ref[1], member[1]):
        if rn != mn:
            return False, tr("The core is different ({p0} vs {p1})", p0=rn, p1=mn)
        if abs(rsw - msw) > 1e-3 * max(abs(rsw), abs(msw), 1.0):
            return False, tr(
                "The spectrum width varies greatly ({p0:.1f} vs "
                "{p1:.1f})",
                p0=rsw,
                p1=msw,
            )
        if abs(ro1 - mo1) > 1e-3 * max(abs(ro1), abs(mo1), 1.0):
            return False, tr(
                "The carrier frequency difference is large ({p0:.1f} vs "
                "{p1:.1f})",
                p0=ro1,
                p1=mo1,
            )
    return True, ""


def run_batch(
    manager: ProjectManager,
    exp_id: str,
    targets: str | Iterable[str],
    steps: Iterable[str],
    backend: Any,
    *,
    params: dict[str, Any] | None = None,
    progress: Callable[[str], None] | None = None,
    reference_data_id: str | None = None,
    max_workers: int = 1,
    on_data_done: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute the specified steps in order for each data in the group. Failure of a single data
    will not interrupt the entire group. Each executable step (import idempotent confirmation)
    in steps will be registered by the underlying implementation WorkflowRun (convert_to_fid /
    process / reconstruct_nus / pick_peaks); failed data records failed_step/error, and the
    entire group continues. Return data-by-data results and summary (see module docstring).
    progress: message callback for each data and step (such as "d_001: Start spectrum").

    Parameters
    ----------
    manager: ProjectManager The manager of the loaded project. exp_id: str Experiment id.
    targets: str | Iterable[str] A single data id, a list of data ids, or a data group id
    (``B1`` and the like, parsed by ``.pipeline_state.json``). steps: Iterable[str] A subset of
    steps to be performed (``["fid", "spectrum"]`` etc.), executed in the given order. backend:
    Any processing backend. params: dict[str, Any], optional processing parameter (same copy
    data by data; see ``reference_data_id`` for reference data parameter reuse). progress:
    Callable[[str], None], optional progress callback: output before the start of each data
    ``[x/y] Start processing data <id>``. reference_data_id: str | on_data_done:
    Callable[[dict[str, Any]], None], optional Call back the step-by-step result (including
    failure) at the end of each data.

    Returns
    -------
    dict[str, Any] ``summary``(total/success/failed), ``results`` (data step-by-step and
    status), ``failed`` (failed data id list), ``skipped`` (skipped members in the group and
    reasons).

    Raises
    ------
    BatchError The step name is illegal, the data id does not exist, or the group parsing fails.

    Side effects
    ------------
    Execute processing and registration one by one data ``WorkflowRun``; the product falls into
    ``process/``, ``spectra/``, ``peaks/`` of the data; failure of a single data does not
    interrupt the entire group (see ``summary``).

    Examples
    --------
    result = run_batch(manager, "exp_001", ["d_001"], ["fid", "spectrum"], backend) if
    result["failed"]:... # The failure data and reasons are in
    result["results"][data_id]["error"].
    """
    if manager.project is None:
        raise BatchError(tr("Project is not loaded and cannot be processed in batches"))
    from backend.runtime import cancel_requested

    steps = list(steps)
    unknown = [s for s in steps if s not in BATCH_STEPS]
    if unknown:
        raise BatchError(tr("Unsupported batch steps: {p0}", p0=unknown))
    data_ids, batch = _resolve_data_ids(manager, exp_id, targets)
    step_params = dict(params or {})
    per_data_options = step_params.pop("_data_options", {})
    from core.project.grouping import validate_dimensions

    dimension = validate_dimensions(manager, exp_id, data_ids)
    max_workers = max(1, min(10, int(max_workers))) if dimension == 2 else 1
    if max_workers > 1 and len(data_ids) > 1 and not reference_data_id:
        import copy
        from concurrent.futures import ThreadPoolExecutor

        def run_member(key):
            options = dict(step_params)
            options.update(per_data_options.get(key, {}))
            return run_batch(
                manager,
                exp_id,
                [key],
                steps,
                copy.copy(backend),
                params=options,
                progress=(lambda message: progress(f"[{key}] {message}")) if progress else None,
                on_data_done=on_data_done,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            batches = list(pool.map(run_member, data_ids))
        results = {
            key: value for batch_result in batches for key, value in batch_result["results"].items()
        }
        failed = [key for key in data_ids if results[key]["status"] == "failed"]
        skipped = [key for key in data_ids if results[key]["status"] == "skipped"]
        cancelled = [key for key in data_ids if results[key]["status"] == "cancelled"]
        return {
            "experiment_id": exp_id,
            "batch_id": batch,
            "data_ids": data_ids,
            "steps": steps,
            "results": results,
            "failed": failed,
            "skipped": skipped,
            "cancelled": cancelled,
            "summary": {
                "total": len(data_ids),
                "success": len(data_ids) - len(failed) - len(skipped) - len(cancelled),
                "failed": len(failed),
            },
        }
    ref_params = {}

    # 0.2.199-patch29pq: When processing with reference to the entire group, First take the
    # reference data spectrum fingerprint for type/condition check.
    ref_fp = None
    if reference_data_id and "spectrum" in steps:
        try:
            ref_fp = _data_fingerprint(manager, exp_id, reference_data_id)
        except Exception:  # noqa: BLE001 -
            ref_fp = None
    total = len(data_ids)
    results: dict[str, dict[str, Any]] = {}
    for index, data_id in enumerate(data_ids, start=1):
        per_data: dict[str, Any] = {
            "data_id": data_id,
            "status": "success",
            "steps": {},
            "failed_step": "",
            "error": "",
            "logs": [],
        }
        # 0.2.199-patch29hf: Stop button has requested cancellation -> Remaining data mark has been
        # canceled and terminated the entire group.
        if cancel_requested():
            for _remaining in data_ids[index - 1 :]:
                _per = {
                    "data_id": _remaining,
                    "status": "cancelled",
                    "steps": {},
                    "failed_step": "",
                    "error": tr("user has stopped batch processing"),
                    "logs": [tr("The batch has been stopped and the data has not been processed")],
                }
                results[_remaining] = _per
                if on_data_done is not None:
                    on_data_done(_per)
            break
        # 0.2.199-patch29gv: Output the progress x/y before starting to process each data, so that
        # the user can understand the progress.
        if progress is not None:
            progress(tr("[{p0}/{p1}] Start processing data {p2}", p0=index, p1=total, p2=data_id))
        # Reference to the entire group processing: Members that are inconsistent with the reference
        # data (type/condition) cannot be applied to the reference parameter, and will be skipped
        # and notified, and will not be processed.
        if ref_fp is not None and data_id != reference_data_id:
            try:
                member_fp = _data_fingerprint(manager, exp_id, data_id)
            except Exception:  # noqa: BLE001 -
                member_fp = None
            if member_fp is not None:
                ok, reason = _fingerprints_match(ref_fp, member_fp)
                if not ok:
                    per_data["status"] = "skipped"
                    per_data["error"] = (
                        tr(
                            "the fingerprint is inconsistent with reference data {p0} ; its "
                            "processing parameters cannot be applied, skipped: ",
                            p0=reference_data_id,
                        )
                        + reason
                    )
                    per_data["logs"].append(per_data["error"])
                    results[data_id] = per_data
                    if on_data_done is not None:
                        on_data_done(per_data)
                    if progress is not None:
                        progress(tr("{p0}: jump over({p1})", p0=data_id, p1=reason))
                    continue
        # BATCH-012 Capability boundary: Batch only supports 2D spectra -- 1D/3D data (especially 3D
        # NUS/SMILE data that is prone to power outages on unstable hosts) is skipped directly
        # without running any steps.
        try:
            from workflow.stepwise import _read_experiment

            _exp = _read_experiment(manager, exp_id, data_id)
            _ndim = int(getattr(_exp, "ndim", 2) or 2)
        except Exception:  # noqa: BLE001 -
            _ndim = 2
        if _ndim not in BATCH_SUPPORTED_NDIM:
            per_data["status"] = "skipped"
            _msg = tr(
                "Batch only supports {p0}D spectra, so {p1}D data are skipped (see the "
                "capability boundary in docs/manager/architecture.md)",
                p0=BATCH_SUPPORTED_NDIM,
                p1=_ndim,
            )
            per_data["error"] = _msg
            per_data["logs"].append(_msg)
            results[data_id] = per_data
            if on_data_done is not None:
                on_data_done(per_data)
            if progress is not None:
                progress(f"{data_id}: {_msg}")
            continue
        for step in steps:
            if _ndim == 1 and step == "peaks":
                per_data["steps"][step] = "not_applicable"
                continue
            # 0.2.199-patch29gt: Group the batch and directly skip the steps that have been done (to
            # avoid re-running the processed data).
            if not reference_data_id and _step_already_done(manager, exp_id, data_id, step):
                per_data["steps"][step] = "already_done"
                per_data["logs"].append(tr("{p0} Completed, skip", p0=step))
                if progress is not None:
                    progress(tr("{p0}: {p1} Completed, skip", p0=data_id, p1=step))
                continue
            if progress is not None:
                progress(tr("{p0}: start {p1}", p0=data_id, p1=step))
            step_logs: list[str] = []

            def _collect_log(_msg: str) -> None:
                """Collect member output and forward it to the group log."""
                step_logs.append(_msg)
                if progress is not None:
                    progress(_msg)

            try:
                merged = dict(ref_params) if step == "spectrum" else {}
                merged.update(step_params)
                merged.update(per_data_options.get(data_id, {}))
                runner = _run_step
                if reference_data_id and step in ("fid", "spectrum", "peaks"):
                    from workflow.reference_scripts import run_reference_step

                    def runner(manager, exp, data, step, backend, params, progress):
                        return run_reference_step(
                            manager,
                            exp,
                            data,
                            reference_data_id,
                            step,
                            backend,
                            progress,
                            overrides=params,
                        )

                value = runner(
                    manager,
                    exp_id,
                    data_id,
                    step,
                    backend,
                    merged,
                    progress=_collect_log,
                )
            except Exception as exc:  # noqa: BLE001 -
                if cancel_requested():
                    per_data["status"] = "cancelled"
                    per_data["error"] = tr("user has stopped batch processing")
                    per_data["logs"].append(tr("{p0} Interrupt (user stops)", p0=step))
                else:
                    per_data["status"] = "failed"
                    per_data["failed_step"] = step
                    per_data["error"] = f"{type(exc).__name__}: {exc}"
                    per_data["logs"].append(tr("{p0} fail: {p1}", p0=step, p1=exc))
                per_data["logs"].extend(step_logs)
                break
            per_data["steps"][step] = value
            per_data["logs"].extend(step_logs)
        results[data_id] = per_data
        if on_data_done is not None:
            on_data_done(per_data)
        if progress is not None:
            progress(
                f"{data_id}: "
                + (
                    tr("success")
                    if per_data["status"] == "success"
                    else tr("fail ") + per_data["error"]
                )
            )
        if index < total:
            # 0.2.199-patch29hd: Cooling between adjacent data to avoid continuous SMILE back-to-
            # back to unstable host (power supply/Heat dissipation) power outage (problems.md
            # record).
            time.sleep(BATCH_COOLDOWN_SECONDS)
    manager.save()
    failed = [d for d, r in results.items() if r["status"] == "failed"]
    skipped = [d for d, r in results.items() if r["status"] == "skipped"]
    cancelled = [d for d, r in results.items() if r["status"] == "cancelled"]
    return {
        "experiment_id": exp_id,
        "batch_id": batch,
        "data_ids": data_ids,
        "steps": steps,
        "results": results,
        "failed": failed,
        "skipped": skipped,
        "cancelled": cancelled,
        "summary": {
            "total": total,
            "success": total - len(failed) - len(skipped) - len(cancelled),
            "failed": len(failed),
        },
    }


__all__ = ["BATCH_STEPS", "BATCH_SUPPORTED_NDIM", "BatchError", "run_batch"]
