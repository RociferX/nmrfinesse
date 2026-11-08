'Dialog widget tests: import experiment type / project form / info / confirm (offscreen).'

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from qtcompat.QtWidgets import QApplication

from gui.dialogs import ConfirmDialog, ImportExperimentDialog, InfoDialog


def test_import_dialog_result_data(qapp: QApplication) -> None:
    dialog = ImportExperimentDialog(None, samples=[("S001", "sample A")])
    dialog.source_edit.setText(str(Path.home()))
    dialog.title_edit.setText("HSQC")
    dialog.sample_combo.setCurrentIndex(1)
    data = dialog.result_data()
    assert data["source"] == str(Path.home())
    assert data["title"] == "HSQC"
    assert data["sample_id"] == "S001"
    dialog.close()


def test_import_dialog_validation_empty(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        "gui.dialogs.InfoDialog.show_info",
        staticmethod(lambda parent, title, text: messages.append(text)),
    )
    dialog = ImportExperimentDialog(None)
    dialog._validate_and_accept()
    assert messages and "目录" in messages[0]
    assert dialog.result() != 1
    dialog.close()


def test_import_dialog_copy_defaults_checked(qapp: QApplication) -> None:
    dialog = ImportExperimentDialog(None)
    assert dialog.copy_check.isChecked() is True
    dialog.copy_check.setChecked(False)
    dialog.source_edit.setText(str(Path.home()))
    assert dialog.result_data()["copy"] is False
    dialog.close()


def test_import_dialog_validation_requires_acqus(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []
    monkeypatch.setattr(
        "gui.dialogs.InfoDialog.show_info",
        staticmethod(lambda parent, title, text: messages.append(text)),
    )
    dialog = ImportExperimentDialog(None)
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    dialog.source_edit.setText(str(dataset))
    dialog._validate_and_accept()
    assert messages and "acqus" in messages[0]
    assert dialog.result() != 1
    (dataset / "acqus").write_text("##SIMPLE 1\n", encoding="utf-8")
    dialog._validate_and_accept()
    assert dialog.result() == 1
    dialog.close()


def test_import_dialog_segmented_container(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    '0.2.108: the container-directory import validates and auto-checks segmented acquisition.'
    container = tmp_path / "container"
    container.mkdir()
    for seg in ("seg1", "seg2"):
        (container / seg).mkdir()
        (container / seg / "acqus").write_text("x", encoding="utf-8")
    dialog = ImportExperimentDialog(None)
    dialog.source_edit.setText(str(container))

    assert not dialog.segmented_check.isChecked()

    assert dialog.segmented_check.toolTip().strip()
    monkeypatch.setattr(
        "gui.dialogs.InfoDialog.show_info",
        staticmethod(lambda *args, **kwargs: None),
    )
    dialog._validate_and_accept()
    assert dialog.result() == dialog.DialogCode.Accepted

    dialog.segmented_check.setChecked(True)
    assert dialog.result_data()["segmented"] is True
    dialog.close()


def test_confirm_dialog_returns_exec(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ConfirmDialog, "exec", lambda self: 1)
    assert ConfirmDialog.confirm(None, "t", "x") is True
    monkeypatch.setattr(ConfirmDialog, "exec", lambda self: 0)
    assert ConfirmDialog.confirm(None, "t", "x") is False


def test_info_dialog_constructs(qapp: QApplication) -> None:
    dialog = InfoDialog(None, "标题", "内容")
    assert dialog.windowTitle() == "标题"
    dialog.accept()
    assert dialog.result() == 1


def test_dialogs_stay_modal_above_main_and_nested_dialogs(qapp):
    from qtcompat.QtCore import QEvent, Qt
    from qtcompat.QtWidgets import QDialog, QWidget

    from ui_support.window_layout import install_dialog_layout

    class Main(QWidget):
        blocked = False

        def event(self, event):
            if event.type() == QEvent.Type.WindowBlocked:
                self.blocked = True
            elif event.type() == QEvent.Type.WindowUnblocked:
                self.blocked = False
            return super().event(event)

    install_dialog_layout(qapp)
    owner = Main()
    owner.show()
    dialog = QDialog(owner)
    dialog.show()
    qapp.processEvents()
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert owner.blocked
    assert qapp.activeModalWidget() is dialog
    nested = QDialog(dialog)
    nested.show()
    qapp.processEvents()
    assert nested.windowModality() == Qt.WindowModality.ApplicationModal
    assert qapp.activeModalWidget() is nested
    nested.close()
    qapp.processEvents()
    assert qapp.activeModalWidget() is dialog and owner.blocked
    dialog.close()
    qapp.processEvents()
    assert not owner.blocked
    owner.close()


def test_settings_dialog_trimmed_and_linewidth_saved(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    '0.2.112: the settings dialog drops SMILE threads/zero-fill, keeps line width and saves.'
    from gui.dialogs import SettingsDialog

    monkeypatch.setattr(
        "gui.settings.load_settings",
        lambda: {"linewidth_hz": {"1H": 8, "15N": 15, "13C": 20}, "pipeline": {}},
    )
    dialog = SettingsDialog(None)
    assert set(dialog.linewidth_spins) == {"1H", "15N", "13C"}
    dialog.resize(560, 360)
    dialog.show()
    qapp.processEvents()
    assert dialog.data_root_edit.height() >= dialog.data_root_edit.sizeHint().height()
    assert dialog.settings_scroll.verticalScrollBar().maximum() > 0
    assert dialog.data_root_edit.toolTip()
    assert set(dialog.tolerance_spins) == {"1H", "15N", "13C"}
    assert not hasattr(dialog, "ppl_spin")
    assert not hasattr(dialog, "smile_spin")

    assert [dialog.language_combo.itemData(i) for i in range(dialog.language_combo.count())] == [
        "auto",
        "zh",
        "en",
    ]
    assert dialog.language_combo.currentData() == "auto"
    saved: dict = {}

    def fake_save(settings: dict) -> None:
        saved.update(settings)

    monkeypatch.setattr("gui.settings.save_settings", fake_save)
    dialog._on_accept()
    assert saved["language"] == "auto"
    assert "linewidth_hz" in saved
    assert "alignment_tolerance_ppm" in saved
    assert saved["alignment_tolerance_ppm"]["1H"] == 0.02
    assert "data_root" in saved
    assert "points_per_line" not in saved
    assert "smile_thread_cap" not in saved
    dialog.close()


def test_settings_dialog_preselects_the_saved_language(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    'When the config says zh/en, the settings dialog preselects that entry.'
    from gui.dialogs import SettingsDialog

    monkeypatch.setattr(
        "gui.settings.load_settings",
        lambda: {"language": "en", "linewidth_hz": {"1H": 8, "15N": 15, "13C": 20}, "pipeline": {}},
    )
    dialog = SettingsDialog(None)
    assert dialog.language_combo.currentData() == "en"
    dialog.close()


def test_settings_dialog_persists_the_chosen_language(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The settings dialog writes the UI language into the config file (user-verified path:
    switch language → restart → takes effect).

    Regression: ``gui.settings._merged_view`` used to drop the scalar key language, so
    saving wrote the old value back: the dialog looked successful but the language never
    changed after a restart.
    """
    import yaml

    from gui import settings as gui_settings
    from gui.dialogs import SettingsDialog

    local = tmp_path / "nmrfinesse.local.yaml"
    local.write_text("language: zh\n", encoding="utf-8")
    monkeypatch.setattr(gui_settings, "_settings_path", lambda: local)

    monkeypatch.setattr("ui_support.i18n.read_user_preference", lambda path=None: None)

    dialog = SettingsDialog(None)
    assert dialog.language_combo.currentData() == "zh"
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
    dialog._on_accept()

    assert yaml.safe_load(local.read_text(encoding="utf-8"))["language"] == "en"
    assert gui_settings.load_settings()["language"] == "en"
    dialog.close()


def test_settings_dialog_preselects_locale_style_language(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    'When the config says zh_CN, the combo preselects the Chinese entry, not "follow system".'
    from gui import settings as gui_settings
    from gui.dialogs import SettingsDialog

    local = tmp_path / "nmrfinesse.local.yaml"
    local.write_text("language: zh_CN\n", encoding="utf-8")
    monkeypatch.setattr(gui_settings, "_settings_path", lambda: local)
    dialog = SettingsDialog(None)
    assert dialog.language_combo.currentData() == "zh"
    dialog.close()


def test_dialog_centered_on_screen(qapp: QApplication) -> None:
    '0.2.112: an application-level filter moves popups to the centre of their screen.'
    from qtcompat.QtCore import QEventLoop, QTimer
    from qtcompat.QtWidgets import QDialog

    from gui.dialogs import install_dialog_centering

    app = QApplication.instance()
    install_dialog_centering(app)
    dialog = QDialog()
    dialog.show()
    center: tuple[int, int] | None = None
    loop = QEventLoop()

    def _check() -> None:
        nonlocal center
        c = dialog.frameGeometry().center()
        center = (c.x(), c.y())
        loop.quit()

    QTimer.singleShot(60, _check)
    loop.exec()
    geo = app.primaryScreen().availableGeometry()
    assert center is not None
    assert abs(center[0] - geo.center().x()) <= 2
    assert abs(center[1] - geo.center().y()) <= 2
    dialog.close()


def test_import_dialog_browse_starts_at_data_root(
    tmp_path: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    '0.2.199-patch29gg: the import "Browse..." dialog starts in the data root directory.'
    from gui import dialogs as dialogs_module
    from gui import settings as settings_module
    from gui.dialogs import ImportExperimentDialog

    monkeypatch.setattr(
        settings_module,
        "load_settings",
        lambda: {"data_root": str(tmp_path)},
    )
    starts: list[str] = []

    def fake_existing(parent, title, start="", *_a, **_k):
        starts.append(str(start))
        return str(tmp_path)

    monkeypatch.setattr(dialogs_module, "choose_directory", fake_existing)
    dialog = ImportExperimentDialog(None)
    dialog._browse()
    assert starts == [str(tmp_path)]
    assert dialog.source_edit.text() == str(tmp_path)
    dialog.close()


def test_choose_directory_is_parented_modal_and_native(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from qtcompat.QtCore import Qt
    from qtcompat.QtWidgets import QFileDialog, QWidget

    from gui.file_dialogs import choose_directory

    owner = QWidget()
    child = QWidget(owner)
    seen: list[QFileDialog] = []

    def fake_exec(dialog: QFileDialog) -> QFileDialog.DialogCode:
        seen.append(dialog)
        return QFileDialog.DialogCode.Accepted

    monkeypatch.setattr(QFileDialog, "exec", fake_exec)
    monkeypatch.setattr(QFileDialog, "selectedFiles", lambda _self: [str(tmp_path)])

    assert choose_directory(child, "Choose a folder", str(tmp_path)) == str(tmp_path)
    assert len(seen) == 1
    dialog = seen[0]
    assert dialog.parentWidget() is owner
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert not dialog.testOption(QFileDialog.Option.DontUseNativeDialog)
    assert dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    owner.close()


def test_blocked_window_click_keeps_modal_dialog_without_flashing(qapp, monkeypatch):
    from qtcompat.QtCore import QPoint, Qt
    from qtcompat.QtTest import QTest
    from qtcompat.QtWidgets import QDialog, QPushButton, QVBoxLayout, QWidget

    from ui_support.window_layout import install_dialog_layout

    install_dialog_layout(qapp)
    owner = QWidget()
    owner.resize(600, 400)
    button = QPushButton("Background action", owner)
    clicked = []
    button.clicked.connect(lambda: clicked.append(True))
    owner.show()
    dialog = QDialog(owner)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QPushButton("Dialog action"))
    dialog.show()
    qapp.processEvents()
    alerts = []
    monkeypatch.setattr(QApplication, "alert", lambda *_: alerts.append(True))
    # QWindow input passes through Qt's modal blocking, unlike sending a QWidget
    # mouse event directly. The button state still exposes the blocked press.
    QTest.mousePress(owner.windowHandle(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(20, 20))
    QTest.qWait(40)
    assert not clicked
    assert not dialog.property('attentionFlashing')
    assert alerts == []
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    QTest.mouseRelease(owner.windowHandle(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, QPoint(20, 20))
    assert not dialog.property('attentionFlashing')
    dialog.close()
    owner.close()


def test_wayland_native_picker_uses_portal_without_overriding_explicit_theme(monkeypatch):
    import ui_support.window_layout as layout

    monkeypatch.setattr(layout.sys, 'platform', 'linux')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-0')
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'KDE')
    monkeypatch.delenv('QT_QPA_PLATFORM', raising=False)
    monkeypatch.delenv('QT_QPA_PLATFORMTHEME', raising=False)
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_QPA_PLATFORMTHEME'] == 'xdgdesktopportal'
    monkeypatch.setenv('QT_QPA_PLATFORMTHEME', 'explicit-theme')
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_QPA_PLATFORMTHEME'] == 'explicit-theme'


def test_gnome_native_picker_uses_xwayland_owner_without_overriding_platform(monkeypatch):
    import ui_support.window_layout as layout

    monkeypatch.setattr(layout.sys, 'platform', 'linux')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-0')
    monkeypatch.setenv('DISPLAY', ':0')
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'ubuntu:GNOME')
    monkeypatch.delenv('QT_QPA_PLATFORM', raising=False)
    monkeypatch.delenv('QT_QPA_PLATFORMTHEME', raising=False)
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_QPA_PLATFORM'] == 'xcb'
    assert layout.os.environ['QT_QPA_PLATFORMTHEME'] == 'gtk3'
    monkeypatch.setenv('QT_QPA_PLATFORM', 'wayland')
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_QPA_PLATFORM'] == 'wayland'


def test_gnome_x11_native_picker_uses_gtk_without_changing_explicit_theme(monkeypatch):
    import ui_support.window_layout as layout

    monkeypatch.setattr(layout.sys, 'platform', 'linux')
    monkeypatch.setenv('DISPLAY', ':0')
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')
    monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    monkeypatch.delenv('QT_QPA_PLATFORM', raising=False)
    monkeypatch.delenv('QT_QPA_PLATFORMTHEME', raising=False)
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_QPA_PLATFORMTHEME'] == 'gtk3'
    assert 'QT_QPA_PLATFORM' not in layout.os.environ
    monkeypatch.setenv('QT_QPA_PLATFORMTHEME', 'explicit-theme')
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_QPA_PLATFORMTHEME'] == 'explicit-theme'


def test_picker_start_resolves_file_missing_folder_and_empty_path(tmp_path, monkeypatch):
    from gui.file_dialogs import browse_start_directory

    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: home)
    file = tmp_path / 'tool'
    file.write_text('tool')
    assert browse_start_directory(str(file)) == str(tmp_path)
    assert browse_start_directory(str(tmp_path / 'not-yet-created' / 'folder')) == str(tmp_path)
    assert browse_start_directory('') == str(home)
    assert browse_start_directory('~/') == str(Path('~/').expanduser())


def test_each_settings_tool_path_has_working_browse_button(tmp_path, qapp, monkeypatch):
    import gui.dialogs as dialogs

    seen = []

    def choose(_parent, title, start, filters):
        seen.append((title, start, filters))
        return str(tmp_path / 'selected tool')

    monkeypatch.setattr(dialogs, 'choose_file', choose)
    dialog = dialogs.SettingsDialog()
    for tool, edit in [('nmrPipe', dialog.nmrpipe_edit), ('bruker', dialog.bruker_edit),
                       ('proj3D.tcl', dialog.proj3d_edit), ('pipe2ucsf', dialog.pipe2ucsf_edit)]:
        initial = str(tmp_path / tool)
        edit.setText(initial)
        dialog.tool_browse_buttons[tool].click()
        assert seen[-1][1] == initial
        assert edit.text() == str(tmp_path / 'selected tool')
    assert len(seen) == 4
    dialog.close()


def _dialog_for_centering(kind, parent, tmp_path):
    from qtcompat.QtWidgets import QDialog, QMessageBox, QProgressDialog

    from core.project import ProjectManager
    from gui import dialogs
    from gui.overlay_svg_export import OverlaySvgExportDialog
    from gui.tutorial import TutorialDialog
    from gui.ucsf_export_dialog import UcsfExportDialog
    from tests.test_viewer import _synthetic_spectrum
    from viewer.app import InfoDialog as ViewerInfoDialog
    from viewer.spectrum_viewer import SpectrumViewer

    factories = {
        'info': lambda: dialogs.InfoDialog(parent, 'Information', 'Done'),
        'about': lambda: dialogs.AboutDialog(parent),
        'viewer_info': lambda: ViewerInfoDialog(parent, 'Information', 'Done'),
        'confirm': lambda: dialogs.ConfirmDialog(parent, 'Confirm', 'Continue?'),
        'multi_select': lambda: dialogs.MultiSelectDataDialog(parent, 'Select', [('d1', 'Data')]),
        'import': lambda: dialogs.ImportExperimentDialog(parent),
        'notes_project': lambda: dialogs.NotesDialog(parent, 'Notes', 'project'),
        'notes_experiment': lambda: dialogs.NotesDialog(parent, 'Notes', 'experiment'),
        'notes_data': lambda: dialogs.NotesDialog(parent, 'Notes', 'data'),
        'script': lambda: dialogs.ScriptEditorDialog(parent, 'HSQC', content='echo test'),
        'history': lambda: dialogs.RunHistoryDialog(parent, [], 'Demo'),
        'batch': lambda: dialogs.BatchSummaryDialog(parent, {'items': []}, 'Demo'),
        'settings': lambda: dialogs.SettingsDialog(parent),
        'tutorial': lambda: TutorialDialog(parent),
        'generic_form': lambda: QDialog(parent),
        'message': lambda: QMessageBox(QMessageBox.Icon.Warning, 'Warning', 'Example',
                                     QMessageBox.StandardButton.Ok, parent),
        'progress': lambda: QProgressDialog('Working', '', 0, 0, parent),
    }
    if kind == 'ucsf':
        manager = ProjectManager.create_project(tmp_path / 'project', 'Demo')
        return UcsfExportDialog(manager, parent)
    if kind == 'svg':
        viewer = SpectrumViewer(parent)
        viewer.add_spectrum(_synthetic_spectrum())
        return OverlaySvgExportDialog(viewer, parent)
    return factories[kind]()


@pytest.mark.parametrize('kind', [
    'info', 'viewer_info', 'confirm', 'multi_select', 'import', 'notes_project',
    'notes_experiment', 'notes_data', 'script', 'history', 'batch', 'settings',
    'tutorial', 'about', 'ucsf', 'svg', 'generic_form', 'message', 'progress',
])
def test_secondary_dialogs_center_on_owner_and_remain_topmost(tmp_path, qapp, kind):
    from qtcompat.QtCore import Qt
    from qtcompat.QtTest import QTest
    from qtcompat.QtWidgets import QWidget

    from ui_support.window_layout import install_dialog_layout

    install_dialog_layout(qapp)
    area = qapp.primaryScreen().availableGeometry()
    owner = QWidget()
    owner.resize(round(area.width() * .7), round(area.height() * .7))
    owner.show()
    qapp.processEvents()
    owner.move(owner.pos() + area.center() - owner.frameGeometry().center())
    dialog = _dialog_for_centering(kind, owner, tmp_path)
    dialog.show()
    QTest.qWait(30)
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert dialog.windowHandle().flags() & Qt.WindowType.WindowStaysOnTopHint
    assert dialog.windowHandle().transientParent() is owner.windowHandle()
    offset = dialog.frameGeometry().center() - owner.frameGeometry().center()
    assert abs(offset.x()) <= 3 and abs(offset.y()) <= 3, (kind, offset)
    dialog.close()
    owner.close()


@pytest.mark.parametrize('name, expected', [
    ('VirtualPS/2 VMware VMMouse', True),
    ('VMware VMware Virtual USB Mouse', True),
    ('VMware DnD UInput pointer', False),
    ('Logitech USB Mouse', False),
])
def test_vmware_pointer_detection_uses_current_machine_names(tmp_path, name, expected):
    from ui_support.window_layout import _vmware_virtual_mouse

    path = tmp_path / 'event4' / 'device' / 'name'
    path.parent.mkdir(parents=True)
    path.write_text(name)
    assert _vmware_virtual_mouse(tmp_path) is expected
    path.unlink()
    assert not _vmware_virtual_mouse(tmp_path)


@pytest.mark.parametrize('platform, session, mouse, expected', [
    ('xcb', 'wayland', True, True),
    ('', 'wayland', True, True),
    ('xcb', 'x11', True, True),
    ('', 'x11', True, True),
    ('xcb', 'x11', False, False),
    ('wayland', 'wayland', True, False),
    ('offscreen', 'x11', True, False),
])
def test_vmware_compatibility_is_limited_to_xcb(monkeypatch, platform, session, mouse, expected):
    import ui_support.window_layout as layout

    monkeypatch.setattr(layout.sys, 'platform', 'linux')
    monkeypatch.setattr(layout, '_vmware_virtual_mouse', lambda: mouse)
    monkeypatch.setenv('DISPLAY', ':0')
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')
    monkeypatch.setenv('QT_QPA_PLATFORM', platform)
    monkeypatch.delenv('QT_XCB_NO_XI2', raising=False)
    if session == 'wayland':
        monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-0')
    else:
        monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    layout.configure_native_file_dialogs()
    assert ('QT_XCB_NO_XI2' in layout.os.environ) is expected


def test_vmware_input_keeps_explicit_qt_override(monkeypatch):
    import ui_support.window_layout as layout

    monkeypatch.setattr(layout.sys, 'platform', 'linux')
    monkeypatch.setattr(layout, '_vmware_virtual_mouse', lambda: True)
    monkeypatch.setenv('DISPLAY', ':0')
    monkeypatch.setenv('QT_QPA_PLATFORM', 'xcb')
    monkeypatch.setenv('QT_XCB_NO_XI2', 'user-value')
    layout.configure_native_file_dialogs()
    assert layout.os.environ['QT_XCB_NO_XI2'] == 'user-value'


def test_settings_defaults_are_staged_and_cancel_does_not_save(qapp, monkeypatch):
    import gui.settings as settings
    from gui.dialogs import SettingsDialog
    saved = []
    monkeypatch.setattr(settings, "save_settings", lambda value: saved.append(value))
    dialog = SettingsDialog()
    dialog.nmrpipe_edit.setText("custom")
    dialog.linewidth_spins["1H"].setValue(99)
    dialog._restore_defaults()
    assert dialog.nmrpipe_edit.text() == ""
    assert dialog.linewidth_spins["1H"].value() == settings.DEFAULTS["linewidth_hz"]["1H"]
    assert dialog.font_size_combo.currentData() == 0
    assert not saved
    dialog.reject()
    assert not saved


def test_settings_menu_action_opens_directly(qapp, monkeypatch):
    from gui.main_window import MainWindow
    opened = []
    monkeypatch.setattr(MainWindow, "_open_settings", lambda self: opened.append(self))
    window = MainWindow()
    assert window.settings_action.menu() is None
    window.settings_action.trigger()
    assert opened == [window]
    window.close()
