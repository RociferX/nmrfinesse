"""Focused contracts for the revised group/reference processing UI."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.project import ProjectError, ProjectManager


def make_data(tmp_path, dimensions):
    manager = ProjectManager.create_project(tmp_path / "project", "test")
    exp = manager.create_experiment()
    entries = []
    for i, ndim in enumerate(dimensions):
        raw = tmp_path / f"raw{i}"
        raw.mkdir()
        (raw / "acqus").touch()
        if ndim >= 2:
            (raw / "acqu2s").touch()
        if ndim >= 3:
            (raw / "acqu3s").touch()
        entries.append(manager.import_data(exp.id, str(raw)))
    return manager, exp.id, entries


def test_groups_require_same_dimension(tmp_path):
    manager, exp, data = make_data(tmp_path, [2, 3, 3])
    with pytest.raises(ProjectError):
        manager.create_data_group(exp, data_ids=[d.id for d in data])
    group = manager.create_data_group(exp, data_ids=[d.id for d in data[1:]])
    with pytest.raises(ProjectError):
        manager.add_to_group(exp, group.id, data[0].id)
    assert group.data_ids == [d.id for d in data[1:]]


@pytest.mark.parametrize(
    "index,expected",
    [(0, {1, 2, 3}), (1, {1}), (2, {2}), (3, {3}), (4, {1, 2}), (5, {2, 3}), (6, {1, 3})],
)
def test_batch_filters_all_supported_dimensions(tmp_path, qapp, index, expected):
    from gui.dashboards import ExperimentImportPanel

    manager, exp, entries = make_data(tmp_path, [1, 2, 3])
    panel = ExperimentImportPanel()
    for entry in entries:
        panel._add_batch_path(entry.source)
    panel.dimension_filter.setCurrentIndex(index)
    assert panel.batch_list.item(0).text() == "All"
    assert {
        int(Path(panel.batch_list.item(i).text()).name[-1]) + 1
        for i in range(1, panel.batch_list.count())
    } == expected
    assert panel.batch_add_button.menu() is None
    panel.close()


@pytest.mark.parametrize("ndim,limit,expected", [(2, 2, 2), (2, 30, 4), (3, 5, 1)])
def test_batch_worker_limit_and_3d_serial(tmp_path, monkeypatch, ndim, limit, expected):
    from workflow import batch

    manager, exp, entries = make_data(tmp_path, [ndim] * 4)
    group = manager.create_data_group(exp, data_ids=[d.id for d in entries])
    monkeypatch.setattr("workflow.stepwise._read_experiment", lambda *a: SimpleNamespace(ndim=ndim))
    monkeypatch.setattr(batch, "BATCH_COOLDOWN_SECONDS", 0)
    running = peak = 0
    lock = threading.Lock()

    def execute(manager, exp, key, step, backend, params, progress):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.04)
        with lock:
            running -= 1
        if key == entries[1].id:
            raise RuntimeError("one failed")
        return key

    monkeypatch.setattr(batch, "_run_step", execute)
    result = batch.run_batch(manager, exp, group.id, ["fid"], object(), max_workers=limit)
    assert peak == expected
    assert result["summary"] == {"total": 4, "success": 3, "failed": 1}
    assert result["failed"] == [entries[1].id]


def test_deleted_member_hidden_and_not_processed(tmp_path, qapp):
    from gui.group_panel import GroupBatchPanel
    from gui.notes import set_data_note_fields
    from ui_support.i18n import tr
    from workflow.batch import _resolve_data_ids

    manager, exp, entries = make_data(tmp_path, [3, 3])
    entries[0].title = "kept"
    entries[1].title = "removed"
    for data in entries:
        set_data_note_fields(manager.project, exp, data.id, {"notes": data.title})
    group = manager.create_data_group(exp, data_ids=[d.id for d in entries])
    panel = GroupBatchPanel()
    context = []
    panel.context_changed.connect(context.append)
    panel.set_context(manager, exp, group.id)
    entries[1].trashed = True
    panel.refresh()
    assert tr("Group members: {p0}", p0=1) in context[-1]
    assert panel.notes_scroll.widget().layout().itemAtPosition(0, 2) is None
    assert _resolve_data_ids(manager, exp, group.id)[0] == [entries[0].id]
    entries[1].trashed = False
    panel.refresh()
    assert tr("Group members: {p0}", p0=2) in context[-1]
    assert "removed" in panel.notes_scroll.widget().layout().itemAtPosition(0, 2).widget().text()
    panel.close()


def test_reference_table_values_and_auto_all(qapp):
    from qtcompat.QtCore import Qt

    from gui.reference_phase_dialog import ReferenceOptionsDialog

    defaults = {"range": (10.5, 6.5), "phases": {"F1": (10, 20), "F2": (30, 40)}}
    rows = [("a", "first"), ("b", "second")]
    dialog = ReferenceOptionsDialog(None, rows, defaults, {}, "range")
    assert dialog.values() == {"a": {}, "b": {}}
    dialog.table.item(1, 1).setText("11")
    assert dialog.values()["b"] == {"range": (11, 6.5)}
    dialog.close()
    dialog = ReferenceOptionsDialog(None, rows, defaults, {}, "phases")
    assert not dialog.auto_all.isChecked()
    assert all(not value["auto_phase"] for value in dialog.values().values())
    assert dialog.table.item(0, dialog.table.columnCount() - 1).toolTip() == dialog.note.text()
    dialog.table.item(1, 1).setText("50")
    assert dialog.values()["b"]["phases"]["F1"] == (50, 20)
    dialog.auto_all.setChecked(True)
    assert all(value["auto_phase"] for value in dialog.values().values())
    assert not dialog.table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable
    dialog.auto_all.setChecked(False)
    assert dialog.table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable
    dialog.close()


def test_default_3d_projection_and_explicit_full_load(tmp_path, qapp, monkeypatch):
    from gui.spectrum_panel import SpectrumPanel

    manager, exp, entries = make_data(tmp_path, [3])
    panel = SpectrumPanel(manager)
    panel._current_exp_id, panel._current_data_id = exp, entries[0].id
    paths = [tmp_path / "d_001.ft3", tmp_path / "d_001_15N-1H.ft2"]
    for path in paths:
        path.touch()
    monkeypatch.setattr(panel, "_spectrum_paths", lambda: paths)
    opened = []
    monkeypatch.setattr(panel, "open_spectrum", lambda path: opened.append(path) or True)
    monkeypatch.setattr(panel, "_load_peaks", lambda path: None)
    panel.load_default_spectrum()
    panel.load_current_spectrum()
    assert opened == [paths[1], paths[0]]
    panel.close()


def test_parallel_setting_clamped():
    from gui.settings import DEFAULTS, normalize_workers

    assert DEFAULTS["pipeline"]["parallel_workers"] == 5
    assert normalize_workers(100) == 10
    assert normalize_workers(0) == 1
    assert normalize_workers("invalid") == 5


def test_signature_cache_reuses_and_invalidates_named_schedule(tmp_path, monkeypatch):
    from workflow import reference_scripts as ref

    manager, exp, entries = make_data(tmp_path, [3])
    raw = Path(entries[0].source)
    schedule = raw / "CANH"
    schedule.write_text("0 0\n")
    calls = []

    def read(*args):
        calls.append(1)
        return SimpleNamespace(
            ndim=3, dimensions=[], sampling=SimpleNamespace(mode="nus", schedule_file="CANH")
        )

    monkeypatch.setattr(ref, "_read_experiment", read)
    for _ in range(5):
        assert ref.data_signature(manager, exp, entries[0].id) == (3, "nus", ())
    assert len(calls) <= 2
    schedule.write_text("0 0\n1 1\n")
    ref.data_signature(manager, exp, entries[0].id)
    assert len(calls) == 3


def test_mixed_batch_import_creates_homogeneous_groups(tmp_path, monkeypatch):
    from gui.processing import ProcessingController

    manager, exp, entries = make_data(tmp_path, [1, 2, 3, 3])
    controller = ProcessingController(manager)
    by_source = {entry.source: entry.id for entry in entries}
    monkeypatch.setattr(
        controller, "import_data", lambda entry, folder: {"data_id": by_source[folder]}
    )
    for entry in entries:
        (Path(entry.source) / ("fid" if entry is entries[0] else "ser")).touch()
    result = controller.batch_import(exp, [entry.source for entry in entries], group=True)
    assert all(item["ok"] for item in result["results"])
    assert len(result["batch_ids"]) == 3
    assert result["results"][2]["group_id"] == result["results"][3]["group_id"]


def test_reference_3d_run_regenerates_projection(tmp_path, monkeypatch):
    from workflow import reference_scripts as ref

    manager, exp, entries = make_data(tmp_path, [3, 3])
    experiment = SimpleNamespace(ndim=3, dataset_id="d_001", direct_dimension=None)
    monkeypatch.setattr(ref, "data_signature", lambda *a: (3, "uniform", ()))
    monkeypatch.setattr(ref, "_read_experiment", lambda *a: experiment)
    monkeypatch.setattr(ref, "reference_script", lambda *a: ("process.com", "saved script"))
    calls = []
    monkeypatch.setattr("workflow.manual.run_manual_spectrum", lambda *a, **k: "new.ft3")

    def project(*args, **kwargs):
        calls.append(args[4])
        return {"F1": "new-projection.ft2"}

    monkeypatch.setattr("workflow.stepwise.generate_3d_projections", project)
    result = ref._execute_reference_step(
        manager, exp, entries[1].id, entries[0].id, "spectrum", object()
    )
    assert result == "new.ft3" and calls == [Path("new.ft3")]


def test_group_dimension_uses_saved_metadata_when_source_is_unavailable(tmp_path):
    import json

    from core.project.grouping import data_ndim

    manager, exp, entries = make_data(tmp_path, [3])
    entry = entries[0]
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"dataset": {"ndim": 3}}))
    entry.source = entry.raw_dir = str(tmp_path / "missing")
    entry.metadata_path = str(metadata)
    assert data_ndim(manager, exp, entry.id) == 3
