"""Batch processing engine tests: multiple data execution, continuing after a single failure,
WorkflowRun registration, stepwise reuse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.project import ProjectManager
from workflow.batch import BatchError, run_batch


class _FakeBackend:
    """Fake backend that records calls; convert_to_fid can be set to fail on call N."""

    def __init__(self, work_dir: Path, *, fail_fid_on: int = -1) -> None:
        self.work_dir = str(work_dir)
        self.fail_fid_on = fail_fid_on
        self.calls: list[tuple[str, str]] = []  # (method, dataset_id)
        self.fid_calls = 0

    def _touch(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    def convert_to_fid(self, experiment, data_dir, progress=None,
        params=None) -> dict:
        self.fid_calls += 1
        self.calls.append(("convert_to_fid", experiment.dataset_id))
        if self.fid_calls == self.fail_fid_on:
            return {"success": False, "message": "转换失败", "logs": []}
        fid_path = Path(self.work_dir) / f"{experiment.dataset_id}.fid"
        self._touch(fid_path)
        return {
            "success": True,
            "fid_path": str(fid_path),
            "message": "ok",
            "logs": [],
        }

    def process(
        self,
        experiment,
        plan,
        direct_phase_override=None,
        params=None,
        progress=None,
    ) -> dict:
        self.calls.append(("process", experiment.dataset_id))
        spectrum = Path(self.work_dir) / f"{experiment.dataset_id}.ft2"
        self._touch(spectrum)
        return {
            "success": True,
            "spectrum_path": str(spectrum),
            "message": "ok",
            "logs": [],
        }

    def reconstruct_nus(self, experiment, params, progress=None) -> dict:
        self.calls.append(("reconstruct_nus", experiment.dataset_id))
        spectrum = Path(self.work_dir) / f"{experiment.dataset_id}.ft2"
        self._touch(spectrum)
        return {
            "success": True,
            "spectrum_path": str(spectrum),
            "message": "ok",
            "logs": [],
        }


def _manager_with_data(
    tmp_path: Path, source: Path, n: int = 2
) -> tuple[ProjectManager, str, list[str]]:
    manager = ProjectManager.create_project(tmp_path / "proj", "demo")
    entry = manager.create_experiment(title="batch")
    data_ids = [
        manager.import_data(entry.id, str(source)).id for _ in range(n)
    ]
    manager.save()
    return manager, entry.id, data_ids


def _set_batch(manager, exp_id: str, data_ids: list[str], batch: str) -> None:
    """Write the batch key in the GUI-side .pipeline_state.json (emulates a batch group tag)."""
    for data_id in data_ids:
        path = manager.data_base(exp_id, data_id) / ".pipeline_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {"version": 1, "steps": {}, "batch": batch}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _runs_for(manager, data_id: str, refs: set[str]) -> list:
    return [
        r
        for r in manager.project.workflow_runs
        if (r.inputs or {}).get("data_id") == data_id and r.workflow_ref in refs
    ]


def test_run_batch_multiple_data(tmp_path: Path, bruker_dir: Path) -> None:
    """Multi-data batch: fid→spectrum per data, all succeed and WorkflowRun is registered."""
    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=2
    )
    backend = _FakeBackend(tmp_path / "work")
    events: list[str] = []
    result = run_batch(
        manager,
        exp_id,
        data_ids,
        ["fid", "spectrum"],
        backend,
        params={"phase_route": "none"},
        progress=events.append,
    )
    assert result["summary"] == {"total": 2, "success": 2, "failed": 0}
    assert result["failed"] == []

    assert events[0].startswith(f"[1/2] 开始处理数据 {data_ids[0]}")
    assert events[1].startswith(f"{data_ids[0]}: 开始 fid")
    assert events[2].startswith(f"{data_ids[0]}: 开始 spectrum")
    assert events[-1] == f"{data_ids[1]}: 成功"

    assert [m for m, _ in backend.calls] == [
        "convert_to_fid",
        "process",
        "convert_to_fid",
        "process",
    ]
    for data_id in data_ids:
        per = result["results"][data_id]
        assert per["status"] == "success"
        fid = per["steps"]["fid"]
        spectrum = per["steps"]["spectrum"]
        assert fid.endswith(".fid")
        assert spectrum.endswith(".ft2")

        assert Path(spectrum).parent == manager.data_dir(
            exp_id, data_id, "spectra"
        )
        refs = {
            r.workflow_ref
            for r in _runs_for(
                manager, data_id, {"convert_to_fid", "process"}
            )
        }
        assert refs == {"convert_to_fid", "process"}


def test_run_batch_single_failure_continues(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """One failure does not stop the group: the second data fails to convert, the first succeeds."""
    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=2
    )
    backend = _FakeBackend(tmp_path / "work", fail_fid_on=2)
    result = run_batch(
        manager,
        exp_id,
        data_ids,
        ["fid", "spectrum"],
        backend,
        params={"phase_route": "none"},
    )
    assert result["summary"] == {"total": 2, "success": 1, "failed": 1}
    assert result["failed"] == [data_ids[1]]
    assert result["results"][data_ids[0]]["status"] == "success"
    failed = result["results"][data_ids[1]]
    assert failed["status"] == "failed"
    assert failed["failed_step"] == "fid"
    assert "转换失败" in failed["error"]

    assert [m for m, _ in backend.calls] == [
        "convert_to_fid",
        "process",
        "convert_to_fid",
    ]

    assert _runs_for(manager, data_ids[1], {"process"}) == []
    assert (
        len(
            _runs_for(
                manager, data_ids[0], {"convert_to_fid", "process"}
            )
        )
        == 2
    )


def test_run_batch_resolves_batch_id(tmp_path: Path, bruker_dir: Path) -> None:
    """batch_id resolution: the group's data comes from the batch key of .pipeline_state.json."""
    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=3
    )
    _set_batch(manager, exp_id, data_ids[:2], "B1")
    _set_batch(manager, exp_id, [data_ids[2]], "B2")
    backend = _FakeBackend(tmp_path / "work")
    result = run_batch(manager, exp_id, "B1", ["fid"], backend)
    assert result["batch_id"] == "B1"
    assert result["data_ids"] == data_ids[:2]
    assert set(result["results"]) == set(data_ids[:2])


def test_run_batch_reuses_stepwise(
    tmp_path: Path, bruker_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fid/spectrum reuse workflow.stepwise (monkeypatch verifies pass-through of the call)."""
    import workflow.stepwise as stepwise_mod

    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=1
    )
    calls: list[tuple] = []
    original_fid = stepwise_mod.generate_fid
    original_spectrum = stepwise_mod.generate_spectrum

    def fake_fid(manager_, exp_id_, data_id_, backend_, **kw):
        calls.append(("fid", data_id_))
        return original_fid(manager_, exp_id_, data_id_, backend_, **kw)

    def fake_spectrum(manager_, exp_id_, data_id_, backend_, **kw):
        calls.append(("spectrum", data_id_, kw.get("params")))
        return original_spectrum(manager_, exp_id_, data_id_, backend_, **kw)

    monkeypatch.setattr(stepwise_mod, "generate_fid", fake_fid)
    monkeypatch.setattr(stepwise_mod, "generate_spectrum", fake_spectrum)
    backend = _FakeBackend(tmp_path / "work")
    result = run_batch(
        manager,
        exp_id,
        data_ids,
        ["fid", "spectrum"],
        backend,
        params={"phase_route": "none", "extract": False},
    )
    assert calls == [
        ("fid", data_ids[0]),
        ("spectrum", data_ids[0], {"phase_route": "none", "extract": False}),
    ]
    assert result["summary"]["success"] == 1


def test_run_batch_import_step_idempotent(
    tmp_path: Path, bruker_dir: Path
) -> None:
    """The import step is idempotent: no duplicate data entries, the imported state is returned."""
    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=1
    )
    backend = _FakeBackend(tmp_path / "work")
    result = run_batch(manager, exp_id, data_ids, ["import", "fid"], backend)
    imp = result["results"][data_ids[0]]["steps"]["import"]
    assert imp["status"] == "already_imported"
    assert imp["data_id"] == data_ids[0]
    assert len(manager.project.experiment(exp_id).data) == 1


def _write_ft2(path: Path) -> None:
    """Write a minimal readable 2D ft2 (one peak, for pick_peaks to detect)."""
    import numpy as np
    from nmrglue.fileio import pipe

    data = np.zeros((32, 64), dtype=np.float32)
    data[16, 30] = 500.0
    dic = {k: "0" for k in pipe.fdata_dic}
    dic["FDMAGIC"] = 9.2330230000000007e14
    dic["FDDIMCOUNT"] = 2
    dic["FDSIZE"] = 64
    dic["FDSPECNUM"] = 32
    dic["FDQUADFLAG"] = 1
    dic["FDF1QUADFLAG"] = 1
    dic["FDF2QUADFLAG"] = 1
    for prefix in ("FDF1", "FDF2"):
        dic[prefix + "SW"] = "6000.0"
        dic[prefix + "OBS"] = "600.0"
        dic[prefix + "CAR"] = "4.7"
        dic[prefix + "ORIG"] = "1000.0"
    pipe.write(str(path), dic, data, overwrite=True)


class _Ft2Backend(_FakeBackend):
    """process produces a readable ft2 (for real detection by the peaks step)."""

    def process(
        self,
        experiment,
        plan,
        direct_phase_override=None,
        params=None,
        progress=None,
    ) -> dict:
        self.calls.append(("process", experiment.dataset_id))
        spectrum = Path(self.work_dir) / f"{experiment.dataset_id}.ft2"
        _write_ft2(spectrum)
        return {
            "success": True,
            "spectrum_path": str(spectrum),
            "message": "ok",
            "logs": [],
        }


def test_run_batch_full_pipeline(tmp_path: Path, bruker_dir: Path) -> None:
    """Full GUI flow (analysis hidden): import→fid→spectrum→peaks, succeeding per data."""
    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=1
    )
    backend = _Ft2Backend(tmp_path / "work")
    result = run_batch(
        manager,
        exp_id,
        data_ids,
        ["import", "fid", "spectrum", "peaks"],
        backend,
        params={"phase_route": "none"},
    )
    per = result["results"][data_ids[0]]
    assert per["status"] == "success"
    assert per["steps"]["import"]["status"] == "already_imported"
    assert per["steps"]["peaks"]["status"] == "success"
    assert per["steps"]["peaks"]["peak_count"] >= 1
    peak_path = Path(per["steps"]["peaks"]["peak_path"])
    assert peak_path.parent == manager.data_dir(exp_id, data_ids[0], "peaks")
    assert "analysis" not in per["steps"]
    assert any(r.workflow_ref == "pick_peaks" for r in manager.project.workflow_runs)


def test_run_batch_unknown_step_raises(
    tmp_path: Path, bruker_dir: Path
) -> None:
    manager, exp_id, data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=1
    )
    with pytest.raises(BatchError, match="不支持的批处理步骤"):
        run_batch(
            manager,
            exp_id,
            data_ids,
            ["smile"],
            _FakeBackend(tmp_path / "work"),
        )


def test_run_batch_empty_batch_raises(
    tmp_path: Path, bruker_dir: Path
) -> None:
    manager, exp_id, _data_ids = _manager_with_data(
        tmp_path, bruker_dir / "hsqc_2d", n=1
    )
    with pytest.raises(BatchError, match="没有数据"):
        run_batch(
            manager, exp_id, "B9", ["fid"], _FakeBackend(tmp_path / "work")
        )


def test_reference_direct_overrides_preserve_other_commands():
    from workflow.reference_scripts import apply_direct_overrides, retarget_script

    text = (
        "#!/bin/csh\nnmrPipe -in 1.fid \\\n"
        "| nmrPipe -fn EXT -x1 10ppm -xn 6ppm -sw \\\n"
        "| nmrPipe -fn PS -p0 15 -p1 80 -di \\\n"
        "| nmrPipe -fn TP \\\n"
        "| nmrPipe -fn SP -off 0.5 -end 0.98 -pow 1 \\\n"
        "| nmrPipe -fn PS -p0 30 -p1 120 -di -out 1.ft2 -ov\n"
    )
    assert apply_direct_overrides(text, {}) == text
    narrowed = apply_direct_overrides(text, {"range": (9, 7)})
    assert "PS -p0 35 -p1 40 -di" in narrowed
    changed = apply_direct_overrides(text, {"range": (9, 7), "phase": (20, 25)})
    assert "PS -p0 20 -p1 25 -di" in changed
    assert changed.split("-fn TP", 1)[1] == text.split("-fn TP", 1)[1]
    target = retarget_script(text, Path("/ref"), Path("/target"), "1", "2")
    assert "-in 2.fid" in target and "-out 2.ft2" in target
    assert "-pow 1" in target and "-p1 120" in target


def test_reference_route_does_not_call_automatic_runner(tmp_path, bruker_dir, monkeypatch):
    from workflow import batch, reference_scripts

    manager, exp, data = _manager_with_data(tmp_path, bruker_dir / "hsqc_2d", n=2)
    calls = []

    def direct(*args, **kwargs):
        calls.append(args[4])
        assert kwargs["overrides"] == {"phase": (5, 10)}
        return "direct"

    monkeypatch.setattr(reference_scripts, "run_reference_step", direct)
    monkeypatch.setattr(batch, "_run_step", lambda *a, **k: pytest.fail("automatic runner called"))
    monkeypatch.setattr(batch, "_step_already_done", lambda *a: True)
    result = run_batch(
        manager,
        exp,
        [data[1]],
        ["fid", "spectrum"],
        object(),
        reference_data_id=data[0],
        params={"phase": (5, 10)},
    )
    assert result["results"][data[1]]["status"] == "success"
    assert calls == ["fid", "spectrum"]


def test_reference_candidates_filter_dimension_and_sampling(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from workflow import reference_scripts as ref

    manager = ProjectManager.create_project(tmp_path / "p", "test")
    exp = manager.create_experiment()
    data = [manager.import_data(exp.id, "/fake/" + str(i)).id for i in range(4)]
    signatures = {
        data[0]: (3, "nus"),
        data[1]: (3, "nus"),
        data[2]: (3, "uniform"),
        data[3]: (2, "nus"),
    }

    def read(manager, exp, item):
        ndim, mode = signatures[item]
        return SimpleNamespace(ndim=ndim, sampling=SimpleNamespace(mode=mode), dimensions=[])

    monkeypatch.setattr(ref, "_read_experiment", read)
    for key in data:
        work = manager.data_dir(exp.id, key, "process")
        work.mkdir(parents=True, exist_ok=True)
        (work / "nus.com").write_text("saved script")
    assert [key for key, _ in ref.reference_candidates(manager, exp.id, data[0], "spectrum")] == [
        data[1]
    ]


def test_reference_missing_script_cannot_fall_back(tmp_path, bruker_dir):
    from workflow.reference_scripts import run_reference_step

    manager, exp, data = _manager_with_data(tmp_path, bruker_dir / "hsqc_2d", n=2)
    with pytest.raises(ValueError, match=".+"):
        run_reference_step(manager, exp, data[1], data[0], "spectrum", object())


def test_reference_report_records_source_and_changes(tmp_path, bruker_dir, monkeypatch):
    import hashlib

    from workflow import reference_scripts as ref

    manager, exp, data = _manager_with_data(tmp_path, bruker_dir / "hsqc_2d", n=2)
    original = "nmrPipe -fn PS -p0 0 -p1 0 -di\n"
    monkeypatch.setattr(ref, "reference_script", lambda *a: ("process.com", original))

    def execute(manager, exp, target, reference, step, backend, progress, overrides):
        work = manager.data_dir(exp, target, "process")
        work.mkdir(parents=True, exist_ok=True)
        (work / "process.com").write_text("nmrPipe -fn PS -p0 20 -p1 0 -di\n")
        progress("engine stdout complete")
        run = manager.start_run(exp, workflow_ref="manual_process", inputs={"data_id": target})
        manager.finish_run(run.run_id, "success")
        return "/candidate.ft2"

    monkeypatch.setattr(ref, "_execute_reference_step", execute)
    ref.run_reference_step(
        manager, exp, data[1], data[0], "spectrum", object(), overrides={"phases": {"F2": (20, 0)}}
    )
    run = manager.project.workflow_runs[-1]
    audit = run.params["reference_processing"]
    assert audit["reference_data_id"] == data[0] and audit["status"] == "success"
    assert audit["reference_sha256"] == hashlib.sha256(original.encode()).hexdigest()
    assert audit["script_changes"]["changes"][0]["parameter"] == "-p0"
    assert "engine stdout complete" in Path(audit["report_path"]).read_text("utf-8")
    assert "engine stdout complete" in manager.run_log_path(run.run_id).read_text("utf-8")


def test_reference_failure_has_report(tmp_path, bruker_dir, monkeypatch):
    from workflow import reference_scripts as ref

    manager, exp, data = _manager_with_data(tmp_path, bruker_dir / "hsqc_2d", n=2)
    monkeypatch.setattr(ref, "reference_script", lambda *a: ("process.com", "saved script"))

    def fail(*args, **kwargs):
        raise RuntimeError("engine failed with output")

    monkeypatch.setattr(ref, "_execute_reference_step", fail)
    with pytest.raises(RuntimeError, match="engine failed"):
        ref.run_reference_step(manager, exp, data[1], data[0], "spectrum", object())
    run = manager.project.workflow_runs[-1]
    assert run.status == "failed"
    assert "engine failed" in Path(run.params["reference_processing"]["report_path"]).read_text(
        "utf-8"
    )


def test_all_phase_overrides_preserve_nonphase_settings():
    from workflow.reference_scripts import apply_phase_overrides

    script = (
        "nmrPipe -fn PS -p0 1 -p1 2 -di \\\n"
        "| SMILE -nDim 3 -xP0 3 -xP1 4 -yP0 5 -yP1 6 -nIter 99 \\\n"
        "| nmrPipe -fn PS -p0 3 -p1 4 -di \\\n"
        "| nmrPipe -fn PS -p0 5 -p1 6 -di\n"
    )
    result = apply_phase_overrides(script, {"F3": (10, 20), "F2": (30, 40), "F1": (50, 60)}, 3)
    assert "-xP0 30 -xP1 40 -yP0 50 -yP1 60 -nIter 99" in result
    assert "-p0 10 -p1 20" in result and "-p0 50 -p1 60" in result
    assert "-nDim 3" in result


def test_phase_only_preview_does_not_register_or_optimise_other_settings(
    tmp_path, bruker_dir, monkeypatch
):
    from workflow import reference_scripts as ref

    manager, exp, data = _manager_with_data(tmp_path, bruker_dir / "hsqc_2d", n=2)
    work = manager.data_dir(exp, data[1], "process")
    work.mkdir(parents=True, exist_ok=True)
    fid = work / f"{data[1]}.fid"
    fid.write_bytes(b"converted")
    manager.set_data_fid(exp, data[1], fid)
    monkeypatch.setattr(ref, "reference_script", lambda *a: ("process.com", "saved script"))
    class Backend:
        work_dir = "unchanged"
        def convert_to_fid(self, *args, **kwargs):
            pytest.fail("FID was already converted")
    def phase_route(experiment, backend, work_dir, base_params, progress):
        assert base_params["_phase_only"] is True
        assert (work_dir / fid.name).read_bytes() == b"converted"
        assert backend.work_dir == str(work_dir)
        return {"phases": {"F2": (15, 22), "F1": (35, 42)}}
    monkeypatch.setattr("workflow.phase_routes.unified_route", phase_route)
    before = list(manager.project.workflow_runs)
    backend = Backend()
    phases, report = ref.optimise_reference_phases(manager, exp, data[1], data[0], backend)
    assert phases == {"F2": (15, 22), "F1": (35, 42)}
    assert backend.work_dir == "unchanged" and manager.project.workflow_runs == before
    assert json.loads(Path(report).read_text())["status"] == "success"


def test_phase_coordinate_mapping_before_extraction(monkeypatch):
    from types import SimpleNamespace

    import numpy as np
    import pytest

    from workflow.reference_scripts import apply_direct_overrides, phase_residual_to_script
    script = ("nmrPipe -fn ZF -size 100\n"
              "| nmrPipe -fn PS -p0 10 -p1 20 -di\n"
              "| nmrPipe -fn EXT -x1 8ppm -xn 6ppm -sw\n")
    changed = apply_direct_overrides(script, {"range": (7.5,6.5)}, full_width=10)
    assert "PS -p0 10 -p1 20 -di" in changed
    monkeypatch.setattr("nmrglue.pipe.make_uc",lambda *a,**k:
                        SimpleNamespace(ppm_limits=lambda:(8,6)))
    p0,p1 = phase_residual_to_script(script,"F2",2,(5,20),
        {"xSW":"6000","xOBS":"600","xCAR":"5","xT":"50"},{},np.ones((2,20)))
    assert p0 == pytest.approx(-15) and p1 == pytest.approx(99)



def test_reference_picking_without_reference_peak_table(tmp_path, bruker_dir, monkeypatch):
    from workflow.reference_scripts import _execute_reference_step
    manager, exp, data = _manager_with_data(tmp_path, bruker_dir / "hsqc_2d", n=2)
    calls = []
    def pick(*args, **kwargs):
        calls.append(kwargs["sigma_multiplier"])
        return "picked"
    monkeypatch.setattr("workflow.pick_peaks.pick_peaks", pick)
    assert _execute_reference_step(manager, exp, data[1], data[0], "peaks", object()) == "picked"
    assert calls == [None]



def test_reference_menu_uses_import_metadata_without_auto_probes(tmp_path, monkeypatch):
    from workflow import reference_scripts as ref

    manager = ProjectManager.create_project(tmp_path / "menu", "test")
    exp = manager.create_experiment()
    data = [manager.import_data(exp.id, "/missing/" + str(i)).id for i in range(3)]
    for key, mode in zip(data, ["uniform", "uniform", "nus"]):
        metadata = manager.data_metadata_path(exp.id, key)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(
            json.dumps(
                {
                    "dataset": {
                        "ndim": 2,
                        "sampling": {"mode": mode},
                        "dimensions": [{"nucleus": "15N"}, {"nucleus": "1H"}],
                    }
                }
            )
        )
        work = manager.data_dir(exp.id, key, "process")
        work.mkdir(parents=True, exist_ok=True)
        (work / "process.com").write_text("saved script")

    def forbidden(*args):
        pytest.fail("Reference menu must not parse raw data or invoke bruker -AUTO")

    monkeypatch.setattr(ref, "_read_experiment", forbidden)
    assert [key for key, _ in ref.reference_candidates(manager, exp.id, data[0], "spectrum")] == [
        data[1]
    ]
    # Actual execution keeps the raw-data validation boundary.
    with pytest.raises(pytest.fail.Exception):
        ref.data_signature(manager, exp.id, data[0])
