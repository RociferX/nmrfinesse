"""Large-font and narrow-layout coverage for spectrum controls."""

from __future__ import annotations

from qtcompat.QtCore import QPoint, QRect
from qtcompat.QtGui import QFont
from qtcompat.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget

from gui.carrier_editor import FidCarrierPanel
from gui.spectrum_panel import SpectrumPanel, _AssignmentCell
from ui_support.typography import apply_interface_font
from viewer.phase_panel import PhasePanel
from viewer.spectrum3d_panel import Spectrum3DPanel
from viewer.spectrum_viewer import SpectrumViewer


def test_contour_controls_reflow_and_numeric_inputs_keep_their_hint(qapp: QApplication) -> None:
    original_font = qapp.font()
    small_font = QFont(original_font)
    small_font.setPointSize(10)
    large_font = QFont(original_font)
    large_font.setPointSize(18)
    apply_interface_font(qapp, small_font.pointSize())
    viewer = SpectrumViewer()
    viewer.resize(1200, 800)
    viewer.show()
    qapp.processEvents()

    controls = viewer.contour_controls
    controls.setParent(None)
    host = QWidget()
    host_layout = QVBoxLayout(host)
    host_layout.addWidget(controls)
    host.resize(600, 600)
    host.show()
    qapp.processEvents()
    small_widths = [
        spin.minimumWidth()
        for spin in (viewer.level_label, viewer.count_label, viewer.aspect_label)
    ]
    assert controls._compact is False

    apply_interface_font(qapp, large_font.pointSize())
    qapp.processEvents()
    assert controls._compact is True
    large_widths = [
        spin.minimumWidth()
        for spin in (viewer.level_label, viewer.count_label, viewer.aspect_label)
    ]
    assert all(large >= small for large, small in zip(large_widths, small_widths))
    for spin in (viewer.level_label, viewer.count_label, viewer.aspect_label):
        assert spin.width() >= spin.minimumWidth()
    for button in (viewer.hide_positive, viewer.hide_negative):
        assert button.height() >= button.fontMetrics().height()
        assert button.mapTo(viewer.level_controls, QPoint()).y() > (
            viewer.level_slider.mapTo(viewer.level_controls, QPoint()).y()
            + viewer.level_slider.height() - 1
        )
        assert viewer.level_controls.rect().contains(QRect(
            button.mapTo(viewer.level_controls, QPoint()), button.size(),
        ))

    host.resize(1800, 600)
    qapp.processEvents()
    assert controls._compact is False
    qapp.setFont(original_font)
    qapp.processEvents()
    host.close()
    viewer.close()


def test_3d_and_phase_inputs_resize_after_runtime_font_change(
    qapp: QApplication,
) -> None:
    original_font = qapp.font()
    small_font = QFont(original_font)
    small_font.setPointSize(10)
    large_font = QFont(original_font)
    large_font.setPointSize(18)
    apply_interface_font(qapp, small_font.pointSize())
    panel3d = Spectrum3DPanel()
    phase = PhasePanel()
    panel3d.show()
    phase.show()
    qapp.processEvents()

    small_widths = (
        panel3d.point_spin.minimumWidth(),
        panel3d.ppm_spin.minimumWidth(),
        phase.p0_label.minimumWidth(),
        phase.p1_label.minimumWidth(),
    )
    apply_interface_font(qapp, large_font.pointSize())
    qapp.processEvents()
    qapp.processEvents()
    large_widths = (
        panel3d.point_spin.minimumWidth(),
        panel3d.ppm_spin.minimumWidth(),
        phase.p0_label.minimumWidth(),
        phase.p1_label.minimumWidth(),
    )
    assert all(large >= small for large, small in zip(large_widths, small_widths))
    assert all(
        widget.width() >= widget.minimumWidth()
        for widget in (
            panel3d.point_spin,
            panel3d.ppm_spin,
            phase.p0_label,
            phase.p1_label,
        )
    )
    qapp.setFont(original_font)
    qapp.processEvents()
    panel3d.close()
    phase.close()


def test_spectrum_panel_keeps_top_actions_and_peak_controls_visible(
    qapp: QApplication, tmp_path, monkeypatch,
) -> None:
    from tests.test_gui_layout import _manager_with_experiment

    panel = SpectrumPanel(_manager_with_experiment(tmp_path, monkeypatch))
    panel.set_context('exp_001', 'd_001')
    panel.peaks_section.set_expanded(True)
    font = panel.font()
    font.setPointSize(18)
    panel.setFont(font)
    panel.resize(1800, 1000)
    panel.show()
    qapp.processEvents()

    assert panel.file_list.maximumWidth() > 1000
    assert panel.peak_toolbar_widget.height() >= panel.peak_toolbar_widget.sizeHint().height()
    assert panel.lists_row_widget.height() >= panel.loading_indicator.sizeHint().height()
    panel.close()


def test_assignment_cells_and_carrier_choices_fit_large_font(qapp: QApplication) -> None:
    cell = _AssignmentCell(3, 0, "G1H-G1N-G1CA")
    font = cell.font()
    font.setPointSize(18)
    cell.setFont(font)
    cell.resize(360, cell.sizeHint().height())
    cell.show()
    qapp.processEvents()
    for line in cell.lines:
        assert line.width() >= line.fontMetrics().horizontalAdvance("G1CA")
        assert line.width() < 180

    editor = QTextEdit()
    editor.setPlainText("script")
    values = {"CAR1": "117.000000", "CAR2": "32.000000", "CAR3": "175.000000"}
    choices = [
        {"key": key, "axis": key, "nucleus": "1H", "options": []}
        for key in values
    ]
    carrier = FidCarrierPanel(
        editor, choices, lambda _text: values, lambda text, _key, _value: text
    )
    carrier.setFont(font)
    carrier.resize(1000, 300)
    carrier.show()
    qapp.processEvents()
    assert 1 <= carrier._carrier_columns <= len(carrier._carrier_boxes)
    assert all(box.width() >= box.minimumSizeHint().width() for box in carrier._carrier_boxes)
    cell.close()
    carrier.close()
