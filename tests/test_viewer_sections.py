"""Viewer section order, explicit collapsed state, and retained control state."""

from __future__ import annotations

import pytest
from qtcompat.QtCore import QPoint, Qt
from qtcompat.QtGui import QFont
from qtcompat.QtTest import QTest
from qtcompat.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout

from ui_support.collapsible import CollapsibleSection
from ui_support.i18n import tr


@pytest.mark.parametrize('size', [8, 18])
def test_section_header_stays_visible_and_preserves_hidden_children(qapp, size):
    section = CollapsibleSection('Display controls')
    font = QFont(section.font())
    font.setPointSize(size)
    section.setFont(font)
    layout = QVBoxLayout(section.body)
    field = QLineEdit('kept value')
    hidden_button = QPushButton('Mode-specific action')
    layout.addWidget(field)
    layout.addWidget(hidden_button)
    hidden_button.hide()
    section.resize(300, 200)
    section.show()
    qapp.processEvents()
    section.header.click()
    qapp.processEvents()
    assert not section.is_expanded()
    assert section.body.isHidden()
    assert section.header.isVisible()
    assert section.header.findChild(QLabel, 'ViewerSectionState').text() == tr('Collapsed')
    assert section.maximumHeight() == section.natural_height()
    section.header.setFocus()
    QTest.keyClick(section.header, Qt.Key.Key_Space)
    qapp.processEvents()
    assert section.is_expanded()
    assert field.text() == 'kept value'
    assert hidden_button.isHidden()
    assert section.header.findChild(QLabel, 'ViewerSectionState').text() == tr('Expanded')
    section.close()
    section.deleteLater()
    qapp.processEvents()


def _panel(tmp_path, monkeypatch):
    from gui.spectrum_panel import SpectrumPanel
    from tests.test_gui_layout import _manager_with_experiment, _write_ft2

    manager = _manager_with_experiment(tmp_path, monkeypatch)
    path = manager.data_dir('exp_001', 'd_001', 'spectra') / 'current.ft2'
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_ft2(path)
    panel = SpectrumPanel(manager)
    panel.set_context('exp_001', 'd_001')
    panel.resize(1200, 1000)
    panel.show()
    return panel


def test_four_viewer_regions_and_default_collapsed_peaks(qapp, tmp_path, monkeypatch):
    panel = _panel(tmp_path, monkeypatch)
    qapp.processEvents()
    qapp.processEvents()
    sections = (panel.files_section, panel.viewer.plot_area,
                panel.viewer.controls_section, panel.peaks_section)
    tops = [widget.mapTo(panel, QPoint()).y() for widget in sections]
    assert tops == sorted(tops)
    assert len(set(tops)) == 4
    assert panel.files_section.is_expanded()
    assert panel.viewer.controls_section.is_expanded()
    assert not panel.peaks_section.is_expanded()
    assert not panel.peak_toolbar_widget.isVisible()
    assert not panel.peak_table.isVisible()
    assert panel.peaks_section.header.isVisible()
    plot_before = panel.viewer.plot_area.height()
    panel.viewer.controls_section.header.click()
    qapp.processEvents()
    qapp.processEvents()
    assert not panel.viewer.controls_section.is_expanded()
    assert panel.viewer.plot_area.height() > plot_before
    panel.peaks_section.header.click()
    qapp.processEvents()
    assert panel.peak_table.isVisible()
    assert panel.peak_toolbar_widget.isVisible()
    panel.close()
    panel.deleteLater()
    qapp.processEvents()


def test_fold_state_survives_expand_and_restore(qapp, tmp_path, monkeypatch):
    panel = _panel(tmp_path, monkeypatch)
    panel.files_section.set_expanded(False)
    panel.viewer.controls_section.set_expanded(False)
    panel.peaks_section.set_expanded(True)
    panel.expand_button.setChecked(True)
    qapp.processEvents()
    assert panel.files_section.parentWidget() is panel._expand_controls
    assert panel.peaks_section.parentWidget() is panel._expand_controls
    assert panel.viewer.controls_section.parentWidget() is panel._expand_controls
    panel.expand_button.setChecked(False)
    qapp.processEvents()
    assert not panel.files_section.is_expanded()
    assert not panel.viewer.controls_section.is_expanded()
    assert panel.peaks_section.is_expanded()
    assert panel.viewer.controls_section.parentWidget() is panel.viewer.view_splitter
    assert panel.files_section.parentWidget() is panel._panel_splitter
    panel.close()
    panel.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize('size', [12, 18])
def test_expanded_peak_table_fills_sidebar(qapp, tmp_path, monkeypatch, size):
    panel = _panel(tmp_path, monkeypatch)
    font = QFont(panel.font())
    font.setPointSize(size)
    panel.setFont(font)
    panel.peaks_section.set_expanded(True)
    panel.expand_button.setChecked(True)
    for _ in range(3):
        qapp.processEvents()
    column = panel._expand_controls
    bottom = panel.peak_table.mapTo(column, QPoint(0, panel.peak_table.height())).y()
    assert bottom >= column.height() - 3
    assert panel.peak_table.maximumHeight() == 16_777_215
    panel.expand_button.setChecked(False)
    qapp.processEvents()
    assert panel.peak_table.maximumHeight() < 600
    panel.close()
    panel.deleteLater()
    qapp.processEvents()


def test_overlay_hides_peak_section_and_restores_fold_state(qapp, tmp_path, monkeypatch):
    from tests.test_gui_layout import _write_ft2

    panel = _panel(tmp_path, monkeypatch)
    panel.peaks_section.set_expanded(True)
    panel.expand_button.setChecked(True)
    path = panel._current_spectrum.with_name('comparison.ft2')
    _write_ft2(path)
    assert panel._load_compare_spectrum(path)
    panel._activate_comparison(path)
    panel.overlay.toggle.setChecked(True)
    qapp.processEvents()
    assert panel.peaks_section.isHidden()
    assert panel.peak_table.isHidden()
    assert panel.peak_toolbar_widget.isHidden()
    panel._sync_peak_ui_visibility()
    assert panel.peaks_section.isHidden()
    panel.overlay.toggle.setChecked(False)
    qapp.processEvents()
    assert not panel.peaks_section.isHidden()
    assert panel.peaks_section.is_expanded()
    panel.close()
    panel.deleteLater()
    qapp.processEvents()
