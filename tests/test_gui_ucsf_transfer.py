"""Project UCSF selection, export destination settings, and simplified menus."""

import time
from pathlib import Path

from qtcompat.QtCore import Qt

from core.project import ProjectManager


def _project(tmp_path):
    manager = ProjectManager.create_project(tmp_path / 'project', 'demo')
    for title in ('HSQC', 'HNCO'):
        exp = manager.create_experiment(title)
        data = manager.import_data(exp.id, tmp_path / title)
        directory = manager.data_dir(exp.id, data.id, 'spectra')
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'{data.id}.ucsf').write_bytes(title.encode())
    manager.import_data(exp.id, tmp_path / 'missing')
    return manager


def test_hierarchical_selection_and_async_copy_uses_default_folder(tmp_path, qapp, monkeypatch):
    import gui.ucsf_export_dialog as module

    dialog = module.UcsfExportDialog(_project(tmp_path))
    assert dialog.tree.topLevelItemCount() == 2
    assert not dialog.export_button.isEnabled()
    first = dialog.tree.topLevelItem(0)
    first.setCheckState(0, Qt.CheckState.Checked)
    assert len(dialog.selected_entries()) == 1
    second = dialog.tree.topLevelItem(1)
    second.setCheckState(0, Qt.CheckState.Checked)
    assert len(dialog.selected_entries()) == 2
    assert second.child(1).isDisabled()
    assert dialog.export_button.isEnabled()
    default = tmp_path / 'Poky' / 'Spectra'
    default.mkdir(parents=True)
    monkeypatch.setattr(module, 'spectrum_directory_path', lambda: default)
    starts = []

    def choose(_parent, _title, start):
        starts.append(start)
        return str(default)

    monkeypatch.setattr(module, 'choose_directory', choose)
    monkeypatch.setattr(module.InfoDialog, 'show_info', lambda *_a: None)
    dialog._export()
    assert not dialog.buttons.isEnabled()
    dialog.reject()
    for _ in range(200):
        qapp.processEvents()
        if not dialog._busy:
            break
        time.sleep(.005)
    assert not dialog._busy
    assert starts == [str(default)]
    assert len(list(default.glob('*.ucsf'))) == 2
    assert dialog.buttons.isEnabled()
    dialog.close()


def test_spectrum_folder_auto_find_manual_override_and_settings_roundtrip(tmp_path, monkeypatch):
    import gui.settings as settings

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    for key in ('POKYHOME', 'SPARKYHOME'):
        monkeypatch.delenv(key, raising=False)
    assert settings.find_spectrum_directory() is None
    automatic = tmp_path / 'Poky' / 'Spectra'
    automatic.mkdir(parents=True)
    assert settings.find_spectrum_directory() == automatic
    assert settings.spectrum_directory_path() == automatic
    manual = tmp_path / 'my spectra'
    manual.mkdir()
    settings.save_settings({'spectrum_directory': str(manual)})
    assert settings.load_settings()['spectrum_directory'] == str(manual)
    assert settings.spectrum_directory_path() == manual
    settings.save_settings({'spectrum_directory': ''})
    assert settings.spectrum_directory_path() == automatic
    external = tmp_path / 'external disk' / 'custom working area'
    (external / 'Spectra').mkdir(parents=True)
    (tmp_path / '.poky.cfg').write_text(f'!POKY_HOMEDIRECTORY    {external}\n')
    assert settings.find_spectrum_directory() == external / 'Spectra'


def test_settings_spectra_controls_find_browse_and_save(tmp_path, qapp, monkeypatch):
    import gui.dialogs as dialogs
    import gui.settings as settings

    automatic = tmp_path / 'auto'
    automatic.mkdir()
    monkeypatch.setattr(settings, 'find_spectrum_directory', lambda: automatic)
    dialog = dialogs.SettingsDialog()
    assert dialog.spectrum_directory_edit.placeholderText() == str(automatic)
    dialog._find_spectrum_directory()
    assert dialog.spectrum_directory_edit.text() == str(automatic)
    manual = tmp_path / 'manual'
    monkeypatch.setattr(dialogs, 'choose_directory', lambda *_: str(manual))
    dialog._browse_spectrum_directory()
    assert dialog.spectrum_directory_edit.text() == str(manual)
    saved = {}
    monkeypatch.setattr(settings, 'save_settings', lambda data: saved.update(data))
    dialog._on_accept()
    assert saved['spectrum_directory'] == str(manual)
    dialog.close()


def test_project_page_exports_and_has_no_completion_metric_or_duplicate_menus(
    tmp_path, qapp, monkeypatch,
):
    from gui.dashboards import ProjectDashboard
    from gui.main_window import MainWindow
    from ui_support.i18n import tr

    manager = _project(tmp_path)
    page = ProjectDashboard()
    page.set_context(manager)
    assert not hasattr(page, "export_ucsf_button")
    assert not hasattr(page, 'progress_label')
    window = MainWindow(manager=manager)
    menus = window.menuBar().actions()
    file_menu = next(action.menu() for action in menus if action.text() == tr('&File'))
    assert tr('New project...') not in [action.text() for action in file_menu.actions()]
    assert tr('&experiment') not in [action.text() for action in menus]
    assert window.center_panel.welcome_page.new_button is not None
    tools = next(action.menu() for action in menus if action.text() == tr('&Tools'))
    action = next(action for action in tools.actions() if action.text() == tr('Export UCSF files…'))
    assert action.isEnabled() and action.toolTip()
    seen = []

    class ExportDialog:
        def __init__(self, selected_manager, parent):
            seen.append((selected_manager, parent))

        def exec(self):
            seen.append('opened')

    monkeypatch.setattr('gui.ucsf_export_dialog.UcsfExportDialog', ExportDialog)
    action.trigger()
    assert seen == [(manager, window), 'opened']
    window.manager = ProjectManager()
    tools.aboutToShow.emit()
    assert not action.isEnabled()
    window.manager = manager
    window.close()
    page.close()



def test_ucsf_export_updates_after_open_switch_and_close_without_opening_tools(
    tmp_path, qapp, monkeypatch,
):
    from core.project import JsonRecentProjectsStore
    from core.workspace import WorkspaceManager
    from gui.main_window import MainWindow

    manager = _project(tmp_path)
    manager.save()
    monkeypatch.setattr('gui.main_window.WorkspaceManager', lambda: WorkspaceManager(tmp_path))
    window = MainWindow(recent=JsonRecentProjectsStore(tmp_path / 'recent.json'))
    action = window.export_ucsf_action
    assert not action.isEnabled()
    opened = []

    class ExportDialog:
        def __init__(self, selected_manager, parent):
            assert parent is window
            opened.append(selected_manager.root)

        def exec(self):
            pass

    monkeypatch.setattr('gui.ucsf_export_dialog.UcsfExportDialog', ExportDialog)
    # The application starts with no project, then opens one through its real handler.
    # The action must work before any Tools aboutToShow signal is emitted.
    window._open_root(manager.root)
    assert len(window.manager.project.experiments) == 2
    assert action.isEnabled()
    action.trigger()
    assert opened == [manager.root]
    second = ProjectManager.create_project(tmp_path / 'second', 'second')
    window._open_root(second.root)
    assert action.isEnabled()
    action.trigger()
    assert opened == [manager.root, second.root]
    window.manager = ProjectManager()
    window._rebind_shared_manager()
    window.refresh()
    assert not action.isEnabled()
    action.trigger()
    assert opened == [manager.root, second.root]
    window.close()
