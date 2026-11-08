"""Reuse recorded scripts without invoking automatic spectrum optimisation."""

from __future__ import annotations

import re

from core.project import ProjectError
from core.project.run_refs import STEP_RUN_REFS
from ui_support.i18n import tr
from workflow.script_audit import previous_script
from workflow.stepwise import _read_experiment


def data_signature(manager, exp_id, data_id):
    from pathlib import Path

    data = manager.data(exp_id, data_id)
    raw = Path(data.raw_dir or data.source)
    if not raw.is_absolute():
        raw = manager.root / raw
    cache = manager.__dict__.setdefault("_reference_signature_cache", {})
    key = (exp_id, data_id)
    extra = cache.get(key, (None, None, ()))[2]
    stamps = []
    for name in ("acqus", "acqu2s", "acqu3s", "acqu2", "acqu3", "nuslist"):
        path = raw / name
        try:
            stat = path.stat()
            stamps.append((name, stat.st_mtime_ns, stat.st_size))
        except OSError:
            stamps.append((name, None, None))
    for value in (*extra, data.metadata_path):
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = manager.root / path
        try:
            stat = path.stat()
            stamps.append((str(path), stat.st_mtime_ns, stat.st_size))
        except OSError:
            stamps.append((str(path), None, None))
    token = (id(manager.project), str(raw), tuple(stamps))
    if key not in cache or cache[key][0] != token:
        experiment = _read_experiment(manager, exp_id, data_id)
        cache[key] = (
            token,
            (
                experiment.ndim,
                experiment.sampling.mode,
                tuple(d.nucleus for d in experiment.dimensions),
            ),
            tuple(
                str(raw / name)
                for name in (getattr(experiment.sampling, "schedule_file", None),)
                if name
            ),
        )
    return cache[key][1]


def reference_script(manager, exp_id, data_id, step):
    work = manager.data_dir(exp_id, data_id, "process")
    mode = data_signature(manager, exp_id, data_id)[1]
    nus = str(getattr(mode, "value", mode)).lower() == "nus"
    names = (
        ["fid.com"] if step == "fid" else (["nus.com", "process.com"] if nus else ["process.com"])
    )
    for name in names:
        for key in (f"{data_id}_{name}", name):
            text = previous_script(manager, exp_id, data_id, key, STEP_RUN_REFS[step])
            if text:
                return name, text
    # Converted segmented data retain their representative fid script in seg_001.
    for name in names:
        paths = [work / f"{data_id}_{name}", work / name]
        if step == "fid":
            paths += sorted(work.glob("seg_*/fid.com"))[:1]
        for path in paths:
            if path.is_file():
                return name, path.read_text(encoding="utf-8")
    raise ValueError(tr("Reference data {p0} has no saved script for {p1}", p0=data_id, p1=step))


def candidate_signature(manager, exp_id, data_id):
    """Read saved import metadata for menus; processing still validates the raw data."""
    import json

    path = manager.data_metadata_path(exp_id, data_id)
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))["dataset"]
        ndim = int(dataset["ndim"])
        mode = dataset["sampling"]["mode"]
        nuclei = tuple(dim["nucleus"] for dim in dataset["dimensions"])
        if ndim in (1, 2, 3) and mode in ("uniform", "nus", "uncertain") and len(nuclei) == ndim:
            return ndim, mode, nuclei
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return data_signature(manager, exp_id, data_id)


def reference_candidates(manager, exp_id, data_id, step):
    if not manager.project or not data_id:
        return []
    try:
        signature = candidate_signature(manager, exp_id, data_id)
    except (OSError, ValueError, RuntimeError, ProjectError):
        return []
    candidates = []
    for data in manager.project.experiment(exp_id).data:
        if data.id == data_id or getattr(data, "trashed", False):
            continue
        try:
            if candidate_signature(manager, exp_id, data.id) != signature:
                continue
            if step in ("fid", "spectrum"):
                work = manager.data_dir(exp_id, data.id, "process")
                names = ["fid.com"] if step == "fid" else ["process.com", "nus.com"]
                existing = any(
                    (work / name).is_file() or (work / f"{data.id}_{name}").is_file()
                    for name in names
                )
                snapshotted = any(
                    r.status == "success"
                    and r.experiment_id == exp_id
                    and (r.inputs or {}).get("data_id") == data.id
                    and r.snapshot_dir
                    and r.workflow_ref in STEP_RUN_REFS[step]
                    for r in manager.project.workflow_runs
                )
                if not existing and not snapshotted:
                    continue
            elif not any(
                r.status == "success"
                and r.experiment_id == exp_id
                and (r.inputs or {}).get("data_id") == data.id
                and r.workflow_ref in STEP_RUN_REFS["peaks"]
                for r in manager.project.workflow_runs
            ):
                continue
        except (OSError, ValueError, RuntimeError, ProjectError):
            continue
        candidates.append((data.id, data.title or data.id))
    return candidates


def retarget_script(text, source_work, target_work, source_id, target_id):
    text = text.replace(str(source_work), str(target_work))
    pattern = r"(?<![\w])" + re.escape(source_id) + r"(?=(?:%[0-9]+d)?\.(?:fid|ft[123])\b)"
    return re.sub(pattern, lambda _: target_id, text)


def _execute_reference_step(
    manager, exp_id, data_id, reference_data_id, step, backend, progress=None, overrides=None
):
    if data_signature(manager, exp_id, data_id) != data_signature(
        manager, exp_id, reference_data_id
    ):
        raise ValueError(
            tr("Reference and target must have the same dimensions, nuclei and sampling mode")
        )
    if step == "fid":
        from workflow.manual import run_manual_fid_com

        _, text = reference_script(manager, exp_id, reference_data_id, step)
        return run_manual_fid_com(
            manager, exp_id, data_id, text, backend=backend, progress=progress
        )
    if step == "spectrum":
        from workflow.manual import run_manual_spectrum

        if (overrides or {}).get("auto_phase"):
            phases, report = optimise_reference_phases(
                manager,
                exp_id,
                data_id,
                reference_data_id,
                backend,
                overrides=overrides,
                progress=progress,
            )
            overrides["phases"] = phases
            overrides["phase_search_report"] = report
        name, text = reference_script(manager, exp_id, reference_data_id, step)
        source = _read_experiment(manager, exp_id, reference_data_id)
        target = _read_experiment(manager, exp_id, data_id)
        text = retarget_script(
            text,
            manager.data_dir(exp_id, reference_data_id, "process"),
            manager.data_dir(exp_id, data_id, "process"),
            source.dataset_id,
            target.dataset_id,
        )
        direct = source.direct_dimension
        full_width = direct.sw / direct.sf if direct and direct.sf else None
        text = apply_direct_overrides(text, overrides or {}, full_width=full_width)
        if (overrides or {}).get("phases"):
            text = apply_phase_overrides(text, overrides["phases"], source.ndim)
        result = run_manual_spectrum(manager, exp_id, data_id, {name: text}, progress=progress)
        if target.ndim == 3:
            from pathlib import Path

            from workflow.stepwise import generate_3d_projections

            projections = generate_3d_projections(
                manager, exp_id, data_id, target, Path(result), backend, progress=progress
            )
            if projections.get("error") and progress:
                progress(tr("3D projection regeneration failed: {p0}", p0=projections["error"]))
        return result
    if step == "peaks":
        from workflow.pick_peaks import pick_peaks

        runs = [
            r
            for r in manager.project.workflow_runs
            if r.status == "success"
            and r.experiment_id == exp_id
            and (r.inputs or {}).get("data_id") == reference_data_id
            and r.workflow_ref in STEP_RUN_REFS["peaks"]
        ]
        params = (runs[-1].params or {}) if runs else {}
        if not runs and progress is not None:
            progress(tr("Reference has no peak-picking settings; application defaults are used"))
        detection = params.get("detection") or params
        return pick_peaks(
            manager,
            exp_id,
            data_id,
            backend,
            sigma_multiplier=detection.get("sigma_multiplier", detection.get("threshold_sigma")),
        )
    raise ValueError(step)


def apply_direct_overrides(text, overrides, *, full_width=None):
    """Change only the first (direct-axis) EXT/PS commands; retain all other lines."""
    import math

    if not any(key in overrides for key in ("range", "phase")):
        return text
    lines = text.splitlines(keepends=True)

    def command(kind):
        return next(
            (
                i
                for i, line in enumerate(lines)
                if not line.lstrip().startswith("#") and re.search(r"-fn\s+" + kind + r"\b", line)
            ),
            None,
        )

    ps = command("PS")
    if ps is None:
        raise ValueError(tr("Reference script has no direct-axis phase command"))
    tp = command("TP")
    if tp is not None and tp < ps:
        raise ValueError(tr("Cannot identify the direct axis in this reference script"))
    number = r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"

    def value(line, flag, suffix=""):
        match = re.search(
            r"(?<!\S)" + re.escape(flag) + r"\s+" + number + suffix + r"(?=\s|$)", line
        )
        if match is None:
            raise ValueError(tr("Reference script has an unsupported direct-axis setting"))
        return float(match.group(1))

    def replace(line, flag, value, suffix=""):
        return re.sub(
            r"(?<!\S)" + re.escape(flag) + r"\s+\S+",
            lambda _: f"{flag} {value:g}{suffix}",
            line,
            count=1,
        )

    p0, p1 = value(lines[ps], "-p0"), value(lines[ps], "-p1")
    if "range" in overrides:
        lo, hi = map(float, overrides["range"])
        if not all(math.isfinite(x) for x in (lo, hi)) or lo == hi:
            raise ValueError(tr("Invalid direct-axis range"))
        ext = command("EXT")
        if ext is not None and tp is not None and ext > tp:
            ext = None
        width = full_width
        phase_after_ext = ext is None or ext < ps
        old_start = None
        old_end = None
        if ext is not None:
            old_start = value(lines[ext], "-x1", "ppm")
            old_end = value(lines[ext], "-xn", "ppm")
            width = abs(old_start - old_end)
            lines[ext] = replace(replace(lines[ext], "-x1", lo, "ppm"), "-xn", hi, "ppm")
        else:
            lines.insert(ps, f"| nmrPipe -fn EXT -x1 {lo:g}ppm -xn {hi:g}ppm -sw -round 2 \\\n")
            ps += 1
        if not width or width <= 0:
            raise ValueError(tr("Cannot determine the reference direct-axis width"))
        if phase_after_ext:
            if old_start is not None and old_start != old_end:
                p0 += p1 * (old_start - lo) / (old_start - old_end)
            p1 *= abs(hi - lo) / width
    if "phase" in overrides:
        p0, p1 = map(float, overrides["phase"])
        if not all(math.isfinite(x) for x in (p0, p1)):
            raise ValueError(tr("Invalid direct-axis phase"))
    lines[ps] = replace(replace(lines[ps], "-p0", p0), "-p1", p1)
    return "".join(lines)


def run_reference_step(
    manager, exp_id, data_id, reference_data_id, step, backend, progress=None, overrides=None
):
    """Persist source scripts, effective changes, output and logs for each reference step."""
    import hashlib
    import json
    import uuid
    from pathlib import Path

    from core.logging_setup import append_run_log_line
    from core.project.manager import atomic_write_text
    from workflow.script_audit import script_change_report, script_changes

    report_dir = manager.data_dir(exp_id, data_id, "report") / "reference_runs" / uuid.uuid4().hex
    report_dir.mkdir(parents=True, exist_ok=True)
    reference = manager.data(exp_id, reference_data_id)
    record = {
        "reference_experiment_id": exp_id,
        "reference_data_id": reference_data_id,
        "reference_title": reference.title,
        "reference_spectrum": reference.spectrum_path,
        "target_data_id": data_id,
        "step": step,
        "requested_overrides": dict(overrides or {}),
        "overrides": dict(overrides or {}) if step == "spectrum" else {},
        "status": "running",
        "logs": [],
        "report_path": str(report_dir / "report.txt"),
    }
    before = {r.run_id for r in manager.project.workflow_runs}

    def log(message):
        record["logs"].append(str(message))
        if progress is not None:
            progress(str(message))

    title = tr(
        "Reference script processing: {p0} ({p1}), spectrum {p2}, step {p3}",
        p0=reference.title or reference_data_id,
        p1=reference_data_id,
        p2=reference.spectrum_path or "-",
        p3=step,
    )
    log(title)
    original = None
    try:
        if step in ("fid", "spectrum"):
            name, original = reference_script(manager, exp_id, reference_data_id, step)
            frozen = report_dir / name
            frozen.write_text(original, encoding="utf-8", newline="\n")
            record.update(
                script_name=name,
                reference_script=str(frozen),
                reference_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),
            )
            log(tr("Reference script: {p0}; SHA256: {p1}", p0=name, p1=record["reference_sha256"]))
        result = _execute_reference_step(
            manager, exp_id, data_id, reference_data_id, step, backend, log, overrides
        )
        record.update(status="success", output=str(result))
        output = result.get("peak_path", "") if isinstance(result, dict) else str(result)
        record["output_path"] = output
        if step == "peaks":
            for line in str(result).splitlines():
                log(line)
        log(tr("Result file: {p0}", p0=output))
        return result
    except Exception as exc:
        record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        log(record["error"])
        raise
    finally:
        runs = [
            r
            for r in manager.project.workflow_runs
            if r.run_id not in before
            and r.experiment_id == exp_id
            and (r.inputs or {}).get("data_id") == data_id
        ]
        run = runs[-1] if runs else None
        if run is None:
            refs = {"fid": "manual_fid", "spectrum": "manual_process", "peaks": "pick_peaks"}
            run = manager.start_run(exp_id, workflow_ref=refs[step], inputs={"data_id": data_id})
            manager.finish_run(run.run_id, record["status"], message=record.get("error", title))
        record["run_id"] = run.run_id
        actual = manager.data_dir(exp_id, data_id, "process") / record.get("script_name", "fid.com")
        if original is not None and actual.is_file():
            effective = actual.read_text(encoding="utf-8")
            (report_dir / "effective.com").write_text(effective, encoding="utf-8", newline="\n")
            audit = script_changes(record["script_name"], effective, original, "reference_data")
            record["script_changes"] = audit
            for line in script_change_report([audit], failed=record["status"] == "failed"):
                log(line)
        if step == "spectrum":
            record["overrides"] = dict(overrides or {})
        changes = record["overrides"]
        log(tr("Direct-axis range: {p0}", p0=changes.get("range", tr("Use reference"))))
        log(
            tr(
                "Dimension phases: {p0}",
                p0=changes.get("phases", changes.get("phase", tr("Use reference"))),
            )
        )
        if changes.get("phase_search_report"):
            log(tr("Phase-only search report: {p0}", p0=changes["phase_search_report"]))
        log(tr("Reference processing finished: {p0}", p0=record["status"]))
        text = "\n".join(record["logs"])
        atomic_write_text(
            report_dir / "report.json", json.dumps(record, ensure_ascii=False, indent=2)
        )
        atomic_write_text(report_dir / "report.txt", text)
        run.params["reference_processing"] = record
        run.params["reference_processing_report"] = text
        for line in record["logs"]:
            append_run_log_line(manager.run_log_path(run.run_id), line)
        if step == "spectrum" and record["status"] == "success":
            from workflow.optimization_report import write_quality_record

            quality = Path(str(record["output"]) + ".quality.json")
            if quality.is_file():
                cached = json.loads(quality.read_text(encoding="utf-8"))
                write_quality_record(str(record["output"]), run.params, cached.get("text", ""))
        manager.save()


def script_phases(text, ndim):
    """Production scripts process Fndim, ..., F1; reject ambiguous extra PS stages."""
    commands = [
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("#") and re.search(r"-fn\s+PS\b", line)
    ]
    if len(commands) != ndim:
        raise ValueError(tr("Cannot identify every phase dimension in the reference script"))
    result = {}
    for index, line in enumerate(commands):
        values = []
        for flag in ("-p0", "-p1"):
            match = re.search(re.escape(flag) + r"\s+([-+\d.eE]+)", line)
            if not match:
                raise ValueError(tr("Reference script is missing phase values"))
            values.append(float(match.group(1)))
        result[f"F{ndim - index}"] = tuple(values)
    return result


def apply_phase_overrides(text, phases, ndim):
    import math

    script_phases(text, ndim)
    lines = text.splitlines(keepends=True)
    index = 0
    for number, line in enumerate(lines):
        if line.lstrip().startswith("#") or not re.search(r"-fn\s+PS\b", line):
            continue
        axis = f"F{ndim - index}"
        index += 1
        if axis not in phases:
            continue
        p0, p1 = map(float, phases[axis])
        if not all(math.isfinite(v) for v in (p0, p1)):
            raise ValueError(tr("Invalid phase values"))
        for flag, value in (("-p0", p0), ("-p1", p1)):
            line = re.sub(re.escape(flag) + r"\s+\S+", lambda _: f"{flag} {value:g}", line, count=1)
        lines[number] = line
    for number, line in enumerate(lines):
        if line.lstrip().startswith("#") or "SMILE" not in line:
            continue
        mapping = {"x": f"F{ndim - 1}"}
        if ndim == 3:
            mapping["y"] = "F1"
        for prefix, axis in mapping.items():
            if axis not in phases:
                continue
            for order, value in enumerate(phases[axis]):
                flag = f"-{prefix}P{order}"
                line = re.sub(
                    re.escape(flag) + r"\s+\S+",
                    lambda _, flag=flag, value=value: f"{flag} {float(value):g}",
                    line,
                    count=1,
                )
        lines[number] = line
    return "".join(lines)


def optimise_reference_phases(
    manager, exp_id, data_id, reference_data_id, backend, overrides=None, progress=None
):
    """Use the automatic pipeline's phase stage after FID, without parameter optimisation."""
    import copy
    import hashlib
    import json
    import shutil
    import tempfile
    import uuid
    from pathlib import Path

    from core.planning.method_selector import select_method
    from core.project.manager import atomic_write_text
    from workflow.batch import _reference_spectrum_params
    from workflow.phase_routes import _DIRECT_PHASE_FP_KEYS, unified_route

    experiment = _read_experiment(manager, exp_id, data_id)
    data = manager.data(exp_id, data_id)
    fid = Path(data.fid_path) if data.fid_path else None
    if fid is not None and not fid.is_absolute():
        fid = manager.root / fid
    if fid is None or not fid.exists():
        raise ValueError(tr("Generate FID before automatic phase optimisation"))
    work = manager.data_dir(exp_id, data_id, "process")
    name, script = reference_script(manager, exp_id, reference_data_id, "spectrum")
    source_params = _reference_spectrum_params(manager, exp_id, reference_data_id)
    keys = set(_DIRECT_PHASE_FP_KEYS) | {"baseline", "smile_rank", "smile_niter", "smile_nthreads"}
    params = {key: value for key, value in source_params.items() if key in keys}
    bounds = re.search(r"-fn\s+EXT[^\n]*?-x1\s+([-+\d.eE]+)ppm\s+-xn\s+([-+\d.eE]+)ppm", script)
    if bounds:
        params["ext_lo"], params["ext_hi"] = bounds.groups()
    elif "-fn EXT" not in script:
        params["extract"] = False
    if (overrides or {}).get("range"):
        params["extract"] = True
        params["ext_lo"], params["ext_hi"] = map(str, overrides["range"])
    params["_phase_only"] = True
    logs = []

    def log(message):
        logs.append(str(message))
        if progress:
            progress(str(message))

    report = {
        "method": "automatic pipeline phase stage",
        "reference_data_id": reference_data_id,
        "reference_script": name,
        "reference_script_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "status": "running",
        "logs": logs,
        "parameters": params,
    }
    path = manager.data_dir(exp_id, data_id, "report") / f"phase_search_{uuid.uuid4().hex}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="phase-only-", dir=work) as folder:
            scratch = Path(folder)
            # Link only converted input artifacts; cache/diagnostic outputs stay in scratch.
            for item in work.iterdir():
                if item.suffix.lower() == ".fid" or item.name in ("fid", "merged"):
                    (scratch / item.name).symlink_to(
                        item.resolve(), target_is_directory=item.is_dir()
                    )
                elif item.name == "nuslist":
                    shutil.copyfile(item, scratch / item.name)
            local = copy.copy(backend)
            local.work_dir = str(scratch)
            log(
                tr(
                    "Automatic phase optimisation starts after FID; processing-parameter "
                    "optimisation is disabled"
                )
            )
            if experiment.ndim == 1:
                response = local.process(
                    experiment, select_method(experiment), params=params, progress=log
                )
                if not response.get("success"):
                    raise RuntimeError(response.get("message", "phase search failed"))
                values = response.get("effective_params", {}).get("direct_phase", {})
                if not values:
                    raise RuntimeError(tr("No phase result was produced"))
                phases = {"F1": tuple(next(iter(values.values())))}
            else:
                response = unified_route(
                    experiment, local, work_dir=scratch, base_params=params, progress=log
                )
                phases = response["phases"]
            report.update(status="success", phases=phases)
            return phases, str(path)
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        atomic_write_text(path, json.dumps(report, ensure_ascii=False, indent=2))


def phase_residual_to_script(text, axis, ndim, residual, fid_params, header, array):
    """Map a cropped preview correction back to a PS command before extraction."""
    import nmrglue as ng

    if axis != f"F{ndim}" or not residual[1]:
        return residual
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    ps = next(i for i, line in enumerate(lines) if re.search(r"-fn\s+PS\b", line))
    ext = next((i for i, line in enumerate(lines) if re.search(r"-fn\s+EXT\b", line)), None)
    if ext is None or ext < ps:
        return residual
    # NMRPipe PS uses p0 + p1*k/(N-1). Read the actual cropped coordinate endpoints.
    full_width = float(fid_params["xSW"]) / float(fid_params["xOBS"])
    full_start = float(fid_params["xCAR"]) + full_width / 2
    zf = re.findall(r"-fn\s+ZF[^\n]*?-size\s+(\d+)", "\n".join(lines[:ps]))
    full_size = int(zf[-1]) if zf else int(fid_params["xT"])
    full_span = full_width * (full_size - 1) / full_size
    start, end = ng.pipe.make_uc(header, array, dim=array.ndim - 1).ppm_limits()
    crop_span = float(start - end)
    if not crop_span or full_span <= 0:
        raise ValueError(tr("Cannot determine the phase coordinate span"))
    p1 = residual[1] * full_span / crop_span
    p0 = residual[0] - p1 * (full_start - start) / full_span
    return (p0, p1)


def reference_defaults(manager, exp_id, reference_data_id):
    from backend.bruker_workflow import parse_fid_com

    _, text = reference_script(manager, exp_id, reference_data_id, "spectrum")
    experiment = _read_experiment(manager, exp_id, reference_data_id)
    phases = script_phases(text, experiment.ndim)
    bounds = re.search(r"-fn\s+EXT[^\n]*?-x1\s+([-+\d.eE]+)ppm\s+-xn\s+([-+\d.eE]+)ppm", text)
    if bounds:
        ranges = tuple(float(value) for value in bounds.groups())
    else:
        _, fid = reference_script(manager, exp_id, reference_data_id, "fid")
        params = parse_fid_com(fid)
        direct = experiment.direct_dimension
        width = float(params.get("xSW", direct.sw)) / float(params.get("xOBS", direct.sf))
        centre = float(params.get("xCAR", direct.o1p))
        ranges = (centre + width / 2, centre - width / 2)
    return {"range": ranges, "phases": phases}
