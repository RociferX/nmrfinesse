"""Three-level notes feature tests (project / experiment type / sample data): structured field
helpers + the top note bar in the middle area.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtcompat.QtWidgets import QApplication

from core.project import ProjectManager
from gui.notes import (
    DATA_FIELDS,
    EXPERIMENT_FIELDS,
    SAMPLE_FIELDS,
    auto_fill_notes_from_metadata,
    data_note,
    data_note_fields,
    experiment_note,
    experiment_note_fields,
    experiment_type_options,
    format_fields,
    note_fields,
    sample_note,
    sample_note_fields,
    sampling_mode_text,
    set_data_note_fields,
    set_experiment_note_fields,
    set_sample_note_fields,
)


def _manager(tmp_path: Path) -> tuple[ProjectManager, str, str]:
    manager = ProjectManager.create_project(tmp_path / "proj", "demo")
    entry = manager.create_experiment("HSQC")
    data = manager.import_data(entry.id, "/fake/1")
    return manager, entry.id, data.id


def test_bruker_title_remark_and_tree_subtitle(tmp_path, qapp, monkeypatch):
    from qtcompat.QtCore import Qt

    from gui.project_tree import ProjectTreePanel

    manager, exp_id, data_id = _manager(tmp_path)
    source = tmp_path / 'sample_21'
    pdata = source / 'pdata' / '1'
    pdata.mkdir(parents=True)
    title = 'HSQC sample 21\nBuffer pH 6.5, 298 K'
    (pdata / 'title').write_text(title, encoding='utf-8')
    manager.data(exp_id, data_id).source = str(source)
    assert data_note_fields(manager.project, exp_id, data_id)['notes'] == title
    auto_fill_notes_from_metadata(manager, exp_id, data_id, {})
    manager.save()
    assert manager.project.experiment(exp_id).metadata['data_notes'][data_id]['notes'] == title
    monkeypatch.setattr(ProjectTreePanel, '_workspace_projects', lambda self: [manager.root])
    tree = ProjectTreePanel(manager)
    tree.resize(700, 900)
    tree.show()
    tree.tree.expandAll()
    qapp.processEvents()
    node = tree.tree.topLevelItem(0).child(0).child(0).child(0)
    assert node.data(0, Qt.ItemDataRole.UserRole + 1) == title
    from ui_support.title_layout import tooltip_title

    assert tooltip_title(title) in node.toolTip(0)
    assert str(source) in node.toolTip(0)
    assert node.text(1) == ''
    assert tree.tree.visualItemRect(node).height() >= tree.fontMetrics().height() * 2
    set_data_note_fields(manager.project, exp_id, data_id, {'notes': 'User remark'})
    auto_fill_notes_from_metadata(manager, exp_id, data_id, {})
    assert data_note_fields(manager.project, exp_id, data_id)['notes'] == 'User remark'
    raw_dir = manager.data_dir(exp_id, data_id, 'raw')
    (raw_dir / 'pdata' / '1').mkdir(parents=True, exist_ok=True)
    (raw_dir / 'pdata' / '1' / 'title').write_text(title, encoding='utf-8')
    manager.data(exp_id, data_id).raw_dir = raw_dir.relative_to(manager.root).as_posix()
    manager.data(exp_id, data_id).source = str(tmp_path / 'unavailable-source')
    tree.refresh()
    assert node.data(0, Qt.ItemDataRole.UserRole + 1) == title
    tree.close()


@pytest.mark.parametrize('font_size', [12, 18])
def test_tree_title_row_grows_when_column_narrows(tmp_path, qapp, monkeypatch, font_size):
    from qtcompat.QtGui import QFont
    from qtcompat.QtTest import QTest

    from gui.project_tree import ProjectTreePanel

    manager, exp_id, data_id = _manager(tmp_path)
    monkeypatch.setattr(ProjectTreePanel, '_workspace_projects', lambda self: [manager.root])
    tree = ProjectTreePanel(manager)
    font = QFont(tree.font())
    font.setPointSize(font_size)
    tree.setFont(font)
    tree.resize(900, 950)
    tree.show()
    tree.tree.expandAll()
    node = tree.tree.topLevelItem(0).child(0).child(0).child(0)
    from qtcompat.QtCore import Qt

    node.setData(0, Qt.ItemDataRole.UserRole + 1,
                 'Sample with a long title and buffer information that must remain readable\n'
                 '20 mM phosphate buffer at pH 6.5 and temperature 298 K\n'
                 'LAST LINE must remain visible after resizing')
    QTest.qWait(30)
    tree.tree.setColumnWidth(0, 760)
    QTest.qWait(30)
    wide = tree.tree.visualItemRect(node).height()
    tree.resize(390, 950)
    tree.tree.setColumnWidth(0, 260)
    QTest.qWait(30)
    narrow = tree.tree.visualItemRect(node).height()
    assert narrow > wide
    index = tree.tree.indexFromItem(node)
    from qtcompat.QtWidgets import QStyleOptionViewItem

    option = QStyleOptionViewItem()
    option.initFrom(tree.tree)
    option.widget = tree.tree
    tree.tree.itemDelegateForColumn(0).initStyleOption(option, index)
    required = tree.tree.itemDelegateForColumn(0)._note_bounds(option, index).height()
    assert narrow >= option.fontMetrics.height() + 9 + required + 6
    tree.resize(900, 950)
    tree.tree.setColumnWidth(0, 760)
    QTest.qWait(30)
    assert tree.tree.visualItemRect(node).height() == wide
    tree.close()


def test_note_fields_schemas_differ_per_level() -> None:
    """Experiment type = identification/dynamics; sample = repeat/condition/pH/temperature +
    dimension/data type/nucleus/peak sign.
    """
    assert [key for key, _ in SAMPLE_FIELDS] == [
        "protein_name",
        "expression_system",
        "concentration",
        "buffer",
        "notes",
    ]
    assert [key for key, _ in EXPERIMENT_FIELDS] == [
        "experiment_type",
        "sample_name",
        "instrument",
        "temperature",
        "notes",
    ]
    assert [key for key, _ in DATA_FIELDS] == [
        "repeat",
        "condition",
        "buffer_ph",
        "temperature",
        "dimension",
        "experiment_type",
        "nuclei",

        "sampling_mode",
        "peak_sign",
        "notes",
    ]
    assert note_fields("project") == SAMPLE_FIELDS
    assert note_fields("experiment") == EXPERIMENT_FIELDS
    assert note_fields("data") == DATA_FIELDS


def test_notes_helper_roundtrip(tmp_path: Path) -> None:
    """Three-level structured notes round-trip and are still readable after reopening post
    manager.save().
    """
    manager, exp_id, data_id = _manager(tmp_path)
    assert sample_note(manager.project) == ""
    assert experiment_note(manager.project, exp_id) == ""
    assert data_note(manager.project, exp_id, data_id) == ""
    set_sample_note_fields(
        manager.project,
        {"protein_name": "GB1", "concentration": "0.5 mM", "buffer": "PBS"},
    )
    set_experiment_note_fields(
        manager.project,
        exp_id,
        {"experiment_type": "指认实验"},
    )
    set_data_note_fields(
        manager.project,
        exp_id,
        data_id,
        {
            "repeat": "2",
            "condition": "pH 7.0",
            "buffer_ph": "7.0",
            "temperature": "25",
            "dimension": "2D",
            "experiment_type": "HSQC",
            "nuclei": "1H-15N",
        },
    )
    assert "蛋白名称: GB1" in sample_note(manager.project)
    assert "浓度: 0.5 mM" in sample_note(manager.project)
    assert "实验类型: 指认实验" in experiment_note(manager.project, exp_id)
    assert "重复号: 2" in data_note(manager.project, exp_id, data_id)
    assert "数据类型: HSQC" in data_note(manager.project, exp_id, data_id)
    assert "Buffer pH: 7.0" in data_note(manager.project, exp_id, data_id)
    manager.save()
    reopened = ProjectManager.open_project(tmp_path / "proj")
    assert sample_note_fields(reopened.project)["protein_name"] == "GB1"
    assert experiment_note_fields(reopened.project, exp_id)["experiment_type"] == "指认实验"
    assert data_note_fields(reopened.project, exp_id, data_id)["temperature"] == "25"
    assert data_note_fields(reopened.project, exp_id, data_id)["dimension"] == "2D"


def test_legacy_plain_text_notes_compat(tmp_path: Path) -> None:
    """Legacy plain-text notes (the protein.notes / entry.notes / data_notes strings) are still
    readable.
    """
    manager, exp_id, data_id = _manager(tmp_path)
    manager.project.protein.notes = "GB1, 0.5 mM, PBS"
    entry = manager.project.experiment(exp_id)
    entry.notes = "15N HSQC"
    meta = dict(entry.metadata or {})
    meta.setdefault("data_notes", {})[data_id] = "2026-08-13"
    entry.metadata = meta
    assert sample_note(manager.project) == "GB1, 0.5 mM, PBS"
    assert experiment_note(manager.project, exp_id) == "15N HSQC"
    assert data_note(manager.project, exp_id, data_id) == "2026-08-13"


def test_format_fields_skips_empty() -> None:
    assert format_fields({"protein_name": "GB1", "notes": ""}) == "蛋白名称: GB1"
    assert format_fields({}) == ""


def test_format_fields_compacts_short_values_and_keeps_remark_lines() -> None:
    fields = {
        "dimension": "2D", "nuclei": "1H-15N", "temperature": "25",
        "notes": "HSQC title\nBuffer <pH 7.0>",
    }
    text = format_fields(fields)
    assert text.splitlines() == [
        "维度: 2D  ·  核: 1H-15N  ·  温度(°C): 25",
        "备注: HSQC title", "Buffer <pH 7.0>",
    ]
    assert format_fields({"buffer": "PBS\n150 mM NaCl"}) == "Buffer: PBS\n150 mM NaCl"


@pytest.mark.parametrize("font_size", [12, 18])
def test_compact_fields_wrap_as_whole_units(qapp, font_size):
    from qtcompat.QtGui import QFont

    from gui.center_panel import _NotesLabel

    label = _NotesLabel()
    label.setFont(QFont("Sans Serif", font_size))
    label.setText("维度: 2D  ·  采样模式: uniform  ·  核: 1H-15N")
    # Each field fits by itself, but their combined length requires wrapping.
    width = label.fontMetrics().horizontalAdvance("·  采样模式: uniform") + 12
    label.resize(width, label.heightForWidth(width))
    label.show()
    qapp.processEvents()
    fields = [label._flow.itemAt(i).widget() for i in range(label._flow.count())]
    sampling = next(field for field in fields if '采样模式' in field.text())
    assert sampling.width() >= sampling.fontMetrics().horizontalAdvance(sampling.text())
    assert sampling.height() == sampling.fontMetrics().height()
    assert sampling.y() >= fields[0].y() + fields[0].height()
    label.close()


def test_center_panel_notes_bar(tmp_path: Path, qapp: QApplication) -> None:
    'The top of the middle area shows the note fields of each level for the selected level.'
    manager, exp_id, data_id = _manager(tmp_path)
    set_sample_note_fields(manager.project, {"protein_name": "样本A"})
    set_experiment_note_fields(manager.project, exp_id, {"experiment_type": "指认实验"})
    set_data_note_fields(manager.project, exp_id, data_id, {"repeat": "3"})
    manager.save()
    from gui.center_panel import CenterPanel

    panel = CenterPanel(manager)
    panel.set_selection("project", exp_id)
    assert "蛋白名称: 样本A" in panel.notes_label.text()
    panel.set_selection("experiment", exp_id)
    assert "实验类型: 指认实验" in panel.notes_label.text()
    panel.set_selection("data", exp_id, data_id)
    assert "重复号: 3" in panel.notes_label.text()
    from ui_support.i18n import tr

    source_line = tr("Source path: {p0}", p0=str(Path("/fake/1").resolve()))
    assert source_line in panel.notes_label.text()
    assert not panel.edit_notes_button.isHidden()
    seen: list[tuple[str, str, str]] = []
    panel.edit_notes_requested.connect(lambda k, e, d: seen.append((k, e, d)))
    panel.edit_notes_button.click()
    assert seen and seen[0] == ("data", exp_id, data_id)
    panel.close()


@pytest.mark.parametrize("font_size", [12, 18])
def test_center_notes_compact_and_wrap_without_losing_title(tmp_path, qapp, font_size):
    from qtcompat.QtCore import Qt
    from qtcompat.QtGui import QFont

    from gui.center_panel import CenterPanel

    manager, exp_id, data_id = _manager(tmp_path)
    title = "GB1 <HSQC>\nPBS pH 6.5, 150 mM NaCl"
    set_data_note_fields(manager.project, exp_id, data_id, {
        "repeat": "3", "temperature": "25", "dimension": "2D",
        "experiment_type": "HSQC", "nuclei": "1H-15N", "notes": title,
    })
    panel = CenterPanel(manager)
    panel.setFont(QFont("Sans Serif", font_size))
    panel.set_selection("data", exp_id, data_id)
    label = panel.notes_label
    assert "重复号: 3  ·  " in label.text()
    assert title in label.text()
    assert label.textFormat() == Qt.TextFormat.PlainText
    assert label.wordWrap()
    assert label.heightForWidth(330) > label.heightForWidth(900)
    panel.close()


def test_main_window_menu_experiment(
    tmp_path: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    'Top menu: "Project/experiment type"; sample management / add / delete sample removed.'
    from gui.main_window import MainWindow

    workspace = tmp_path / "ws"
    workspace.mkdir()

    class _Ws:
        def __init__(self, root):
            self.root = root

        def ensure(self):
            self.root.mkdir(parents=True, exist_ok=True)
            return self.root

        def list_projects(self):
            return sorted(
                p
                for p in self.root.iterdir()
                if p.is_dir() and (p / "project.json").is_file()
            )

    monkeypatch.setattr("gui.main_window.WorkspaceManager", lambda: _Ws(workspace))
    monkeypatch.setattr(
        "core.workspace.WorkspaceManager", lambda *a, **k: _Ws(workspace)
    )
    window = MainWindow()
    menus = [action.text() for action in window.menuBar().actions()]
    assert "实验(&E)" not in menus
    assert "样本(&S)" not in menus
    assert window.center_panel.welcome_page.new_button.text() == "新建项目..."
    window.close()


def test_edit_notes_saves(
    tmp_path: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"Edit notes" -> the main window saves the structured fields and refreshes the top note
    bar.
    """
    from gui.main_window import MainWindow

    manager, exp_id, _data_id = _manager(tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()

    class _Ws:
        def __init__(self, root):
            self.root = root

        def ensure(self):
            self.root.mkdir(parents=True, exist_ok=True)
            return self.root

        def list_projects(self):
            return sorted(
                p
                for p in self.root.iterdir()
                if p.is_dir() and (p / "project.json").is_file()
            )

    monkeypatch.setattr("gui.main_window.WorkspaceManager", lambda: _Ws(workspace))
    monkeypatch.setattr(
        "core.workspace.WorkspaceManager", lambda *a, **k: _Ws(workspace)
    )

    from qtcompat.QtWidgets import QDialog

    class _FakeNotesDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, parent, title, kind="", values=None):
            self._values = values or {}

        def exec(self):
            return self.DialogCode.Accepted

        def result_fields(self):
            return {"experiment_type": "指认实验"}

    monkeypatch.setattr("gui.main_window.NotesDialog", _FakeNotesDialog)
    window = MainWindow(manager=manager)
    window.center_panel.set_selection("experiment", exp_id)
    window._edit_notes("experiment", exp_id, "")
    fields = experiment_note_fields(manager.project, exp_id)
    assert fields["experiment_type"] == "指认实验"
    assert "指认实验" in window.center_panel.notes_label.text()
    window.close()
def test_edit_notes_only_applies_changed_data_type(
    tmp_path: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """META-002: saving unchanged values does not masquerade as a user choice, while a real
    change is still written back authoritatively.
    """
    from qtcompat.QtWidgets import QDialog

    from gui.main_window import MainWindow

    manager, exp_id, data_id = _manager(tmp_path)
    set_data_note_fields(
        manager.project,
        exp_id,
        data_id,
        {"dimension": "2D", "experiment_type": "HSQC"},
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()

    class _Ws:
        def __init__(self, root):
            self.root = root

        def ensure(self):
            return self.root

        def list_projects(self):
            return []

    class _FakeNotesDialog:
        DialogCode = QDialog.DialogCode
        result = {"dimension": "2D", "experiment_type": "HSQC"}

        def __init__(self, parent, title, kind="", values=None):
            pass

        def exec(self):
            return self.DialogCode.Accepted

        def result_fields(self):
            return dict(self.result)

    applied: list[str] = []
    monkeypatch.setattr("gui.main_window.WorkspaceManager", lambda: _Ws(workspace))
    monkeypatch.setattr("core.workspace.WorkspaceManager", lambda *a, **k: _Ws(workspace))
    monkeypatch.setattr("gui.main_window.NotesDialog", _FakeNotesDialog)
    monkeypatch.setattr(
        "workflow.import_workflow.apply_user_experiment_type",
        lambda manager, exp_id, data_id, name: applied.append(name) or True,
    )

    window = MainWindow(manager=manager)
    window._edit_notes("data", exp_id, data_id)
    assert applied == []

    _FakeNotesDialog.result = {"dimension": "2D", "experiment_type": "COSY"}
    window._edit_notes("data", exp_id, data_id)
    assert applied == ["COSY"]
    window.close()


def test_experiment_type_options_from_presets() -> None:
    """0.2.85: data type options come from presets, filtered by dimension (the Generic fallback is
    excluded).
    """
    options_1d = experiment_type_options("1D")
    options_2d = experiment_type_options("2D")
    options_3d = experiment_type_options("3D")
    assert "1H-1D" in options_1d and "13C-1D" in options_1d
    assert "HSQC" in options_2d and "COSY" in options_2d
    assert "HNCA" in options_3d and "HNCACB" in options_3d
    assert "HNCA" not in options_2d
    assert "HSQC" not in options_3d
    assert "Generic2D" not in options_2d
    assert "Generic3D" not in options_3d
    assert (
        set(options_1d) | set(options_2d) | set(options_3d)
        == set(experiment_type_options())
    )


def test_temperature_from_acqus_detects_celsius_and_kelvin(
    tmp_path: Path,
) -> None:
    '0.2.87: temperature detection for 0.1K (2980->24.9°C), K (298.0->24.9), °C (25->25.0).'
    from gui.notes import temperature_from_acqus

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "acqus").write_text("##$TE= 2980\n", encoding="latin-1")
    assert temperature_from_acqus(raw) == "24.9"
    (raw / "acqus").write_text("##$TE= 298.0\n", encoding="latin-1")
    assert temperature_from_acqus(raw) == "24.9"
    (raw / "acqus").write_text("##$TE= 25\n", encoding="latin-1")
    assert temperature_from_acqus(raw) == "25.0"


def test_auto_fill_notes_from_metadata(tmp_path: Path) -> None:
    """0.2.86: after import, auto-fill notes from metadata/acqus (existing values are not
    overwritten).
    """
    manager, exp_id, data_id = _manager(tmp_path)
    set_data_note_fields(
        manager.project, exp_id, data_id, {"experiment_type": "HSQC"}
    )
    raw = manager.data_dir(exp_id, data_id, "raw")
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "acqus").write_text(
        "##$NUC1= 1H\n##$NUC2= 15N\n##$TE= 2980\n",
        encoding="latin-1",
    )
    metadata = {
        "dataset": {
            "ndim": 2,
            "dimensions": [{"nucleus": "1H"}, {"nucleus": "15N"}],
            "experiment_type": {"name": "HSQC"},
        }
    }
    filled = auto_fill_notes_from_metadata(
        manager, exp_id, data_id, metadata
    )
    exp_fields = experiment_note_fields(manager.project, exp_id)
    assert exp_fields == {}
    data_fields = data_note_fields(manager.project, exp_id, data_id)
    assert data_fields["dimension"] == "2D"
    assert data_fields["experiment_type"] == "HSQC"
    assert data_fields["nuclei"] == "1H-15N"
    assert data_fields["temperature"].startswith("24")
    assert "data.dimension" in filled
    assert "data.experiment_type" in filled
    assert "data.nuclei" in filled
    assert "data.temperature" in filled


def test_sampling_mode_text_formats_nus_and_uniform() -> None:
    'Regression coverage: test sampling mode text formats nus and uniform.'
    assert (
        sampling_mode_text(
            {"sampling": {"mode": "nus", "sampling_fraction": 0.25}}
        )
        == "NUS(fraction 25%)"
    )
    assert (
        sampling_mode_text(
            {"sampling": {"mode": "nus", "sampling_fraction": 0.5}}
        )
        == "NUS(fraction 50%)"
    )
    assert sampling_mode_text({"sampling": {"mode": "uniform"}}) == "uniform"
    assert sampling_mode_text({"sampling": {"mode": "uncertain"}}) == "uncertain"


def test_sampling_mode_text_never_invents_a_fraction() -> None:
    'Regression coverage: test sampling mode text never invents a fraction.'
    assert (
        sampling_mode_text({"sampling": {"mode": "nus", "sampling_fraction": 0.0}})
        == "NUS"
    )


def test_sampling_mode_text_is_empty_without_sampling_info() -> None:
    'Regression coverage: test sampling mode text is empty without sampling info.'
    assert sampling_mode_text({}) == ""
    assert sampling_mode_text({"sampling": {}}) == ""


def test_auto_fill_notes_fills_sampling_mode(tmp_path: Path) -> None:
    'Regression coverage: test auto fill notes fills sampling mode.'
    manager, exp_id, data_id = _manager(tmp_path)
    metadata = {
        "dataset": {
            "ndim": 3,
            "dimensions": [{"nucleus": "1H"}, {"nucleus": "13C"}],
            "experiment_type": {"name": "HNCACB"},
            "sampling": {
                "mode": "nus",
                "sampling_fraction": 0.25,
                "schedule_type": "nuslist",
            },
        }
    }

    filled = auto_fill_notes_from_metadata(manager, exp_id, data_id, metadata)

    assert filled["data.sampling_mode"] == "NUS(fraction 25%)"
    data_fields = data_note_fields(manager.project, exp_id, data_id)
    assert data_fields["sampling_mode"] == "NUS(fraction 25%)"


def test_auto_fill_notes_sampling_mode_not_overwritten(tmp_path: Path) -> None:
    'Regression coverage: test auto fill notes sampling mode not overwritten.'
    manager, exp_id, data_id = _manager(tmp_path)
    set_data_note_fields(
        manager.project, exp_id, data_id, {"sampling_mode": "手工写的"}
    )

    auto_fill_notes_from_metadata(
        manager,
        exp_id,
        data_id,
        {"dataset": {"sampling": {"mode": "nus", "sampling_fraction": 0.25}}},
    )

    data_fields = data_note_fields(manager.project, exp_id, data_id)
    assert data_fields["sampling_mode"] == "手工写的"


def test_auto_fill_notes_without_sampling_info_leaves_field_empty(
    tmp_path: Path,
) -> None:
    'Regression coverage: test auto fill notes without sampling info leaves field empty.'
    manager, exp_id, data_id = _manager(tmp_path)

    auto_fill_notes_from_metadata(
        manager, exp_id, data_id, {"dataset": {"ndim": 2}}
    )

    data_fields = data_note_fields(manager.project, exp_id, data_id)
    assert not data_fields.get("sampling_mode")


def test_notes_dialog_combos_dimension_then_type(
    qapp: QApplication,
) -> None:
    """0.2.85: sample-data notes use drop-downs; pick the dimension first, then filter the data
    type by presets.
    """
    from gui.dialogs import NotesDialog

    dialog = NotesDialog(
        None,
        "样品数据注释",
        "data",
        {"dimension": "2D", "experiment_type": "HSQC"},
    )
    assert dialog._combos["dimension"].currentText() == "2D"
    type_combo = dialog._combos["experiment_type"]
    assert type_combo.currentText() == "HSQC"
    items = [type_combo.itemText(i) for i in range(type_combo.count())]
    assert "HNCA" not in items

    dialog._combos["dimension"].setCurrentText("3D")
    items = [type_combo.itemText(i) for i in range(type_combo.count())]
    assert "HNCA" in items
    assert "HSQC" not in items
    type_combo.setCurrentText("HNCA")
    dialog._combos["nuclei"].setCurrentText("1H-15N-13C")
    fields = dialog.result_fields()
    assert fields["dimension"] == "3D"
    assert fields["experiment_type"] == "HNCA"
    assert fields["nuclei"] == "1H-15N-13C"
    dialog.close()


def test_notes_dialog_blank_does_not_invent_values(qapp: QApplication) -> None:
    """META-002: a blank form round-trip must not invent the first drop-down item as a default
    value.
    """
    from gui.dialogs import NotesDialog

    data_dialog = NotesDialog(None, "样品数据注释", "data", {})
    assert data_dialog.result_fields() == {}
    dimension_items = [
        data_dialog._combos["dimension"].itemText(i)
        for i in range(data_dialog._combos["dimension"].count())
    ]
    assert "1D" in dimension_items
    data_dialog.close()

    experiment_dialog = NotesDialog(None, "实验类型注释", "experiment", {})
    assert experiment_dialog.result_fields() == {}
    experiment_dialog.close()


def test_notes_dialog_preserves_1d_without_inventing_nuclei(
    qapp: QApplication,
) -> None:
    """META-002: opening and saving 1D notes unchanged must not lose the dimension or add a
    two-dimensional nucleus combination.
    """
    from gui.dialogs import NotesDialog

    dialog = NotesDialog(
        None,
        "样品数据注释",
        "data",
        {"dimension": "1D", "experiment_type": "1H-1D"},
    )
    assert dialog.result_fields() == {
        "dimension": "1D",
        "experiment_type": "1H-1D",
    }
    dialog.close()


def test_notes_dialog_experiment_category_options(qapp: QApplication) -> None:
    """IMPORT-007 A: the experiment category no longer lists dynamics (import forbidden) as a
    selectable capability.
    """
    from gui.dialogs import NotesDialog

    dialog = NotesDialog(
        None,
        "实验类型注释",
        "experiment",
        {"experiment_type": "指认实验"},
    )
    type_combo = dialog._combos["experiment_type"]
    assert type_combo.currentText() == "指认实验"
    items = [type_combo.itemText(i) for i in range(type_combo.count())]
    assert "指认实验" in items
    assert "动力学实验" not in items
    assert "dimension" not in dialog._combos
    assert dialog.result_fields() == {"experiment_type": "指认实验"}
    dialog.close()



def test_title_rows_join_and_wrap_at_original_line_boundaries():
    from ui_support.title_layout import title_rows

    title = 'AAAA BBBB\nCCCC DDDD\nEEEE FFFF'
    assert title_rows(title, 40, len) == ['AAAA BBBB | CCCC DDDD | EEEE FFFF']
    assert title_rows(title, 22, len) == ['AAAA BBBB | CCCC DDDD', 'EEEE FFFF']
    assert title_rows(title, 9, len) == title.splitlines()
    assert title_rows(title, 3, len) == title.splitlines()  # Long parts stay intact here.


def test_title_label_reflows_from_original_lines_when_resized(qapp):
    from qtcompat.QtTest import QTest

    from ui_support.title_layout import TitleLabel

    title = 'First original line\nSecond original line\nThird original line'
    label = TitleLabel(title)
    parts = title.splitlines()
    wide = label.fontMetrics().horizontalAdvance(' | '.join(parts)) + 20
    narrow = max(label.fontMetrics().horizontalAdvance(part) for part in parts) + 2
    label.resize(wide, label.heightForWidth(wide))
    label.show()
    QTest.qWait(20)
    assert label.text() == ' | '.join(parts)
    wide_height = label.height()
    label.resize(narrow, label.heightForWidth(narrow))
    QTest.qWait(20)
    assert label.text().splitlines() == parts
    assert label.height() > wide_height
    assert label.original_title == title
    label.resize(wide, label.heightForWidth(wide))
    QTest.qWait(20)
    assert label.text() == ' | '.join(parts)
    label.close()


def test_center_notes_remove_heading_and_keep_title_content(tmp_path, qapp):
    from gui.center_panel import CenterPanel
    from ui_support.title_layout import TitleLabel

    manager, exp_id, data_id = _manager(tmp_path)
    title = 'Sample HSQC\nBuffer pH 6.5\n298 K'
    set_data_note_fields(manager.project, exp_id, data_id, {'notes': title})
    panel = CenterPanel(manager)
    panel.set_selection('data', exp_id, data_id)
    assert not panel.notes_label.text().startswith(('Note:', '注释:', '注释：'))
    assert title in panel.notes_label.text()
    assert not panel.edit_notes_button.isHidden()
    labels = panel.notes_label.findChildren(TitleLabel)
    assert len(labels) == 1
    assert labels[0].original_title.endswith(title)
    panel.close()
