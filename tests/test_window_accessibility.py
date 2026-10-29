"""Screen/font matrices, native ownership, and visible operation feedback."""
from __future__ import annotations

import pytest
from qtcompat.QtCore import QPoint, QRect, Qt
from qtcompat.QtGui import QFont
from qtcompat.QtTest import QTest
from qtcompat.QtWidgets import QDialogButtonBox, QPushButton, QWidget

from ui_support import window_layout


@pytest.fixture
def original_font(qapp):
    font = QFont(qapp.font())
    stylesheet = qapp.styleSheet()
    yield
    qapp.setFont(font)
    qapp.setStyleSheet(stylesheet)


@pytest.fixture(params=['en', 'zh'])
def ui_language(request):
    from ui_support import i18n

    previous = i18n._language
    i18n.set_language(request.param)
    yield
    i18n.set_language(previous)


@pytest.mark.parametrize('size', [8, 12, 18])
@pytest.mark.parametrize('dimensions', [(1024, 768), (1366, 768), (1920, 1080), (2560, 1440)])
def test_main_pages_fit_logical_desktop(qapp, tmp_path, monkeypatch, original_font, ui_language,
                                      size, dimensions):
    from gui.main_window import MainWindow
    from tests.test_gui_layout import _manager_with_experiment
    from ui_support.typography import apply_interface_font

    apply_interface_font(qapp, size)
    manager = _manager_with_experiment(tmp_path, monkeypatch)
    window = MainWindow(manager=manager)
    area = QRect(0, 0, *dimensions)
    window.resize(window_layout.initial_window_size(area))
    window.show()
    window._show_feedback('Settings saved', 'success')
    QTest.qWait(20)
    assert window.context_header.parentWidget() is window.center_panel
    assert window.context_bar.parentWidget() is window.project_tree
    assert window.feedback_widget.parentWidget() is window.context_header
    assert not window.context_bar.wordWrap()
    assert not window.feedback_label.wordWrap()
    assert window.project_tree.layout().indexOf(window.context_bar) == 0
    assert window.center_panel.layout().indexOf(window.context_header) == 0
    assert window.feedback_label.height() >= window.feedback_label.fontMetrics().height()
    assert window.width() <= area.width()
    assert window.height() <= area.height()
    assert window.main_splitter.count() == 3
    if dimensions[0] < 1920:
        assert window.workspace_scroll.horizontalScrollBar().maximum() > 0
        assert window.workspace_scroll.verticalScrollBar().maximum() > 0
    for kind, exp_id, data_id in [('workspace', '', ''), ('project', '', ''),
                                  ('experiment', 'exp_001', ''), ('data', 'exp_001', 'd_001')]:
        window.center_panel.set_selection(kind, exp_id, data_id)
        qapp.processEvents()
        assert sum(window.main_splitter.sizes()) <= window.main_splitter.width()
        page = window.center_panel.stack.currentWidget()
        for button in page.findChildren(QPushButton):
            if button.isVisible():
                assert button.font().pointSize() == size
                assert button.height() >= button.fontMetrics().height()
        assert window.spectrum_panel.width() > 0
        viewer = window.spectrum_panel.viewer
        for button in (viewer.hide_positive, viewer.hide_negative):
            assert viewer.level_controls.rect().contains(QRect(
                button.mapTo(viewer.level_controls, QPoint()), button.size(),
            ))
        if kind == 'project':
            assert window.center_panel.notes_label.height() <= (
                window.center_panel.notes_label.fontMetrics().height() * 2 + 20
            )
    # Expanding the plot must preserve a user's decision to hide the log.
    window.log_panel.hide()
    window._toggle_spectrum_expand(True)
    assert window.workflow_splitter.isHidden()
    window._toggle_spectrum_expand(False)
    assert window.log_panel.isHidden()
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_header_messages_remain_single_line_when_font_changes(
    qapp, tmp_path, monkeypatch, original_font, ui_language,
):
    from qtcompat.QtWidgets import QLabel

    from gui.main_window import MainWindow
    from tests.test_gui_layout import _manager_with_experiment
    from ui_support.theme import apply_dark_theme
    from ui_support.typography import apply_interface_font

    apply_dark_theme(qapp)
    window = MainWindow(manager=_manager_with_experiment(tmp_path, monkeypatch))
    window.show()
    message = 'Settings saved. ' * 30
    window._show_feedback(message, 'success')
    for size in (18, 8, 16):
        apply_interface_font(qapp, size)
        qapp.processEvents()
        label = window.feedback_label
        assert label.font().pointSize() == size
        assert label.text().endswith(message)
        assert label.toolTip() == message
        assert '…' in QLabel.text(label)
        assert label.height() >= label.fontMetrics().height()
        assert window.context_header.height() < label.fontMetrics().height() * 2 + 20
        before = label.text()
        window.refresh()
        assert label.text() == before
    window.close()
    window.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize('kind', ['info', 'confirm', 'settings', 'script', 'fid'])
def test_large_font_dialog_fits_small_screen(qapp, monkeypatch, original_font, kind):
    from gui.dialogs import ConfirmDialog, InfoDialog, ScriptEditorDialog, SettingsDialog

    font = QFont(qapp.font())
    font.setPointSize(18)
    qapp.setFont(font)
    area = QRect(0, 0, 800, 600)
    monkeypatch.setattr(window_layout, 'available_geometry', lambda *_: area)
    parent = QWidget()
    constructors = {
        'info': lambda: InfoDialog(parent, 'Information', ('Long message\n' * 50)),
        'confirm': lambda: ConfirmDialog(parent, 'Confirm', ('Long question\n' * 50)),
        'settings': lambda: SettingsDialog(parent),
        'script': lambda: ScriptEditorDialog(parent, 'Example', content='echo example'),
        'fid': lambda: ScriptEditorDialog(
            parent, 'Example', script_name='fid.com', content='echo example',
            carrier_choices=[], carrier_read=lambda *_: {}, carrier_write=lambda *args: args[0],
        ),
    }
    dialog = constructors[kind]()
    window_layout.fit_dialog(dialog)
    dialog.show()
    qapp.processEvents()
    assert dialog.width() <= area.width()
    assert dialog.height() <= area.height()
    for button in dialog.findChildren(QPushButton):
        if button.isVisible():
            assert button.height() >= button.fontMetrics().height()
    for box in dialog.findChildren(QDialogButtonBox):
        for button in box.buttons():
            assert dialog.rect().contains(QRect(button.mapTo(dialog, QPoint()), button.size()))
    dialog.close()
    parent.close()


def test_wayland_prepares_transient_parent_without_absolute_move(qapp, monkeypatch):
    from gui.dialogs import InfoDialog

    parent = QWidget()
    parent.show()
    dialog = InfoDialog(parent, 'Info', 'Done')
    assert dialog.windowType() == Qt.WindowType.Dialog
    monkeypatch.setattr(window_layout.QApplication, 'platformName', lambda: 'wayland')
    monkeypatch.setattr(dialog, 'move', lambda *_: pytest.fail('Wayland must not use global move'))
    window_layout.place_dialog(dialog)
    assert dialog.windowHandle().transientParent() is parent.windowHandle()
    assert not dialog.isModal()  # Merely preparing it must not make modeless editors modal.
    dialog.close()
    parent.close()


def test_font_setting_save_applies_and_cancel_leaves_font(
    qapp, monkeypatch, tmp_path, original_font,
):
    from qtcompat.QtCore import QTimer

    from gui import settings
    from gui.dialogs import ScriptEditorDialog, SettingsDialog
    from gui.main_window import MainWindow
    from tests.test_gui_layout import _manager_with_experiment
    from ui_support.theme import apply_dark_theme
    from ui_support.typography import apply_interface_font

    monkeypatch.setattr(settings, '_settings_path', lambda: tmp_path / 'local.yaml')
    apply_dark_theme(qapp)
    apply_interface_font(qapp, 10)
    manager = _manager_with_experiment(tmp_path, monkeypatch)
    window = MainWindow(manager=manager)
    window.resize(1280, 750)
    window.show()
    editor = ScriptEditorDialog(window, 'Live editor', content='echo example')
    editor.show()
    controls = [window.project_tree.tree, window.context_bar, window.menuBar(),
                window.statusBar(), window.log_panel.text, editor.editor,
                window.center_panel.welcome_page.new_button,
                window.center_panel.project_page.create_button,
                window.pipeline._rows['fid'].run_button,
                window.spectrum_panel.viewer.level_label]
    assert all(control.font().pointSize() == 10 for control in controls), [
        (type(control).__name__, control.font().pointSize()) for control in controls
    ]
    editor_family = editor.editor.font().family()

    def save_size(size):
        dialog = qapp.activeModalWidget()
        assert isinstance(dialog, SettingsDialog)
        dialog.font_size_combo.setCurrentIndex(dialog.font_size_combo.findData(size))
        dialog._on_accept()

    for size in (18, 8, 16):
        QTimer.singleShot(0, lambda size=size: save_size(size))
        window._open_settings()
        qapp.processEvents()
        assert qapp.font().pointSize() == size
        assert all(control.font().pointSize() == size for control in controls)
        assert editor.editor.font().family() == editor_family
        assert window.workspace_scroll.horizontalScrollBar().maximum() > 0
    # Cancel must leave both the saved setting and every existing control intact.
    assert settings.load_settings()['interface_font_size'] == 16
    other = SettingsDialog(window)
    other.font_size_combo.setCurrentIndex(other.font_size_combo.findData(8))
    other.reject()
    assert qapp.font().pointSize() == 16
    assert settings.load_settings()['interface_font_size'] == 16
    assert all(control.font().pointSize() == 16 for control in controls)
    other.close()
    editor.close()
    window.close()


def test_pipeline_has_visible_report_action(qapp, tmp_path, monkeypatch):
    from gui.main_window import MainWindow
    from tests.test_gui_layout import _manager_with_experiment

    window = MainWindow(manager=_manager_with_experiment(tmp_path, monkeypatch))
    panel = window.pipeline
    panel.set_selection('data', 'exp_001', 'd_001')
    row = panel._rows['fid']
    assert row.report_button.text()
    assert not row.report_button.isHidden()
    row.report_button.click()
    assert not row.detail_frame.isHidden()
    assert row.detail_label.text()
    row.report_button.click()
    assert row.detail_frame.isHidden()
    window.close()


@pytest.mark.parametrize('fails', [False, True])
def test_running_and_result_feedback_are_visible_and_keep_log_scope(
    qapp, tmp_path, monkeypatch, fails,
):
    from gui.main_window import MainWindow
    from tests.test_gui_layout import (
        DeferredThread,
        FakeProcessingController,
        _manager_with_experiment,
    )

    manager = _manager_with_experiment(tmp_path, monkeypatch)
    controller = FakeProcessingController()
    if fails:
        def fail(*_args, **_kwargs):
            raise RuntimeError('Example failure')
        controller.generate_fid = fail
    window = MainWindow(manager=manager, controller=controller)
    window.pipeline.set_selection('data', 'exp_001', 'd_001')
    DeferredThread.pending.clear()
    monkeypatch.setattr('threading.Thread', DeferredThread)
    scope = window.log_panel._current_scope
    window.pipeline._on_run_requested('fid')
    assert not window.feedback_widget.isHidden()
    assert 'd_001' in window.feedback_label.text()
    assert len(DeferredThread.pending) == 1
    DeferredThread.pending.pop()()
    qapp.processEvents()
    assert ('Example failure' in window.feedback_label.text()) == fails
    assert not window.feedback_progress.isVisible()
    assert window.log_panel._current_scope == scope
    window.close()


@pytest.mark.parametrize('size', [8, 12, 18])
def test_maximized_scrollbars_stay_inside_desktop_edge(
    qapp, tmp_path, monkeypatch, original_font, size,
):
    from gui.main_window import MainWindow
    from tests.test_gui_layout import _manager_with_experiment
    from ui_support.typography import apply_interface_font

    apply_interface_font(qapp, size)
    monkeypatch.setattr(MainWindow, '_resolve_environment_on_startup', lambda *_: None)
    window = MainWindow(manager=_manager_with_experiment(tmp_path, monkeypatch))
    window.showMaximized()
    QTest.qWait(20)
    scroll = window.workspace_scroll
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    qapp.processEvents()
    vertical = scroll.verticalScrollBar()
    horizontal = scroll.horizontalScrollBar()
    assert vertical.isVisible()
    assert horizontal.isVisible()
    right = vertical.mapTo(window, QPoint(vertical.width(), 0)).x()
    bottom = horizontal.mapTo(window, QPoint(0, horizontal.height())).y()
    assert window.width() - right >= 20
    assert window.height() - bottom >= 20
    for bar in (vertical, horizontal):
        bar.setValue(bar.maximum())
        assert bar.value() == bar.maximum()
    window.close()
    window.deleteLater()
    qapp.processEvents()
