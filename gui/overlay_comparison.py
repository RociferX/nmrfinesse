"""Controls and a shared-coordinate viewer for two or three result spectra."""
from __future__ import annotations

import threading

import numpy as np
import pyqtgraph as pg
from qtcompat.QtCore import QSignalBlocker, Qt
from qtcompat.QtGui import QColor, QTransform
from qtcompat.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from qtcompat import Signal
from ui_support.collapsible import CollapsibleSection
from ui_support.i18n import tr
from ui_support.numeric_inputs import CommitDoubleSpinBox, CommitSpinBox
from viewer.spectrum_overlay import (
    fit_translation,
    spectrum_axes,
    validate_spectra,
)
from viewer.spectrum_viewer import SpectrumViewer, _ContourSigns


class _SpectrumControls(QWidget):
    changed = Signal()
    contours_changed = Signal()

    def __init__(self):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(4, 4, 4, 4)
        self.visible = QCheckBox(tr('Show spectrum'))
        self.visible.setChecked(True)
        self.visible.toggled.connect(self.changed)
        box.addWidget(self.visible)
        self.start = CommitDoubleSpinBox()
        self.start.setRange(.0001, 100)
        self.start.setDecimals(4)
        self.start.setSuffix(' %')
        self.start.setValue(2.9791)
        self.start.setSingleStep(.1)
        self.levels = CommitSpinBox()
        self.levels.setRange(5, 60)
        self.levels.setValue(8)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(31)
        header = QHBoxLayout()
        header.addWidget(QLabel(tr('Contour start')))
        header.addWidget(self.start)
        header.addStretch(1)
        box.addLayout(header)
        self.sign_controls = _ContourSigns()
        self.hide_positive = self.sign_controls.hide_positive
        self.hide_negative = self.sign_controls.hide_negative
        self.hide_positive.toggled.connect(self.changed)
        self.hide_negative.toggled.connect(self.changed)
        box.addWidget(self.slider)
        box.addWidget(self.sign_controls)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Levels')))
        row.addWidget(self.levels)
        self.count_slider = QSlider(Qt.Orientation.Horizontal)
        self.count_slider.setRange(5, 60)
        self.count_slider.setValue(8)
        self.count_slider.valueChanged.connect(self.levels.setValue)
        self.levels.valueChanged.connect(self.count_slider.setValue)
        row.addWidget(self.count_slider, 1)
        box.addLayout(row)
        self.start.valueChanged.connect(self._start_changed)
        self.levels.valueChanged.connect(self.contours_changed)
        self.slider.valueChanged.connect(self._slider_label)
        self.slider.sliderReleased.connect(self.contours_changed)

    def _slider_label(self, value):
        with QSignalBlocker(self.start):
            self.start.setValue(100 * (value / 100) ** 3)

    def _start_changed(self, value):
        with QSignalBlocker(self.slider):
            self.slider.setValue(round(100 * (value / 100) ** (1 / 3)))
        self.contours_changed.emit()


class OverlayComparison(QWidget):
    changed = Signal()
    fitted = Signal(int, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spectra = []
        self.names = []
        self.tooltips = []
        self.export_directory = None
        self.colors = ['#1f77b4', '#d62728', '#2ca02c']
        self.shifts = []
        self.generation = 0
        self.fit_running = False
        self.curves = []
        self._viewer = None
        self.controls = CollapsibleSection(tr('Comparison controls'))
        layout = QVBoxLayout(self.controls.body)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QGridLayout()
        layout.addLayout(row)
        self.toggle = QPushButton(tr('Overlay comparison'))
        self.toggle.setObjectName('PrimaryAction')
        self.toggle.setCheckable(True)
        self.toggle.toggled.connect(lambda _checked: self.changed.emit())
        row.addWidget(self.toggle, 0, 0)
        self.use_reference = QPushButton(tr('Use comparison as reference'))
        self.use_reference.setObjectName('SubtleAction')
        self.use_reference.setCheckable(True)
        self.use_reference.setToolTip(tr(
            'Unchecked: keep the current spectrum fixed. Checked: keep the selected comparison '
            'spectrum fixed and move the others.'
        ))
        self.use_reference.toggled.connect(self._reference_changed)
        row.addWidget(self.use_reference, 0, 1)
        self.reference_choice = QComboBox()
        self.reference_choice.currentIndexChanged.connect(self._reference_changed)
        self.fit_button = QPushButton(tr('Auto-fit overlay'))
        self.fit_button.setObjectName('PrimaryAction')
        self.fit_button.clicked.connect(self.auto_fit)
        self.fit_button.setToolTip(tr(
            'Detect temporary signed peak tables and fit the common ppm translation from '
            'one-to-one peak matches. Spectral data and headers stay unchanged.'
        ))
        row.addWidget(self.fit_button, 1, 0, 1, 2)
        self.reference_row = QWidget()
        reference_layout = QHBoxLayout(self.reference_row)
        reference_layout.setContentsMargins(0, 0, 0, 0)
        reference_layout.addWidget(QLabel(tr('Fixed reference')))
        reference_layout.addWidget(self.reference_choice, 1)
        layout.addWidget(self.reference_row)
        self.export_button = QPushButton(tr('Export overlay SVG'))
        self.export_button.setObjectName('SubtleAction')
        self.export_button.setToolTip(tr(
            'Export the displayed overlay, coordinates and colors as an SVG vector image.'
        ))
        self.export_button.clicked.connect(self._export)
        layout.addWidget(self.export_button)
        self.manual = QWidget()
        manual_layout = QVBoxLayout(self.manual)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_title = QLabel(tr('Manual adjustment'))
        manual_title.setObjectName('SectionTitle')
        manual_layout.addWidget(manual_title)
        edit_row = QHBoxLayout()
        manual_layout.addLayout(edit_row)
        edit_row.addWidget(QLabel(tr('Move spectrum')))
        self.moving = QComboBox()
        edit_row.addWidget(self.moving, 1)
        self.moving.currentIndexChanged.connect(self._sync_editors)
        self.color_row = QHBoxLayout()
        layout.addLayout(self.color_row)
        self.color_buttons = []
        for index in range(3):
            button = QPushButton()
            button.setObjectName('SubtleAction')
            button.clicked.connect(lambda _checked=False, i=index: self.choose_color(i))
            self.color_row.addWidget(button)
            self.color_buttons.append(button)
        self.spectrum_tabs = QTabWidget()
        self.spectrum_tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        self.spectrum_controls = []
        for _index in range(3):
            controls = _SpectrumControls()
            controls.changed.connect(self._apply_display_visibility)
            controls.contours_changed.connect(self._apply_display_settings)
            self.spectrum_controls.append(controls)
        self.display_title = QLabel(tr('Spectrum display'))
        self.display_title.setObjectName('SectionTitle')
        layout.addWidget(self.display_title)
        layout.addWidget(self.spectrum_tabs)
        self.aspect_row = QWidget()
        aspect_layout = QHBoxLayout(self.aspect_row)
        aspect_layout.setContentsMargins(0, 0, 0, 0)
        aspect_layout.addWidget(QLabel(tr('Plot aspect')))
        self.aspect = CommitDoubleSpinBox()
        self.aspect.setRange(0, 10)
        self.aspect.setDecimals(2)
        self.aspect.setSingleStep(.1)
        self.aspect.setToolTip(tr('Shared coordinate aspect; zero uses a free aspect.'))
        self.aspect.valueChanged.connect(lambda value: self.viewer.aspect_label.setValue(value))
        aspect_layout.addWidget(self.aspect)
        layout.addWidget(self.aspect_row)
        self.spins, self.sliders, self.fine_sliders, self.axis_labels = [], [], [], []
        self.axis_groups = []
        self._fine_origins = [0.0, 0.0]
        for axis in range(2):
            axis_group = QWidget()
            axis_box = QVBoxLayout(axis_group)
            axis_box.setContentsMargins(0, 0, 0, 0)
            manual_layout.addWidget(axis_group)
            self.axis_groups.append(axis_group)
            controls = QHBoxLayout()
            label = QLabel()
            spin = CommitDoubleSpinBox()
            spin.setDecimals(6)
            spin.setSuffix(' ppm')
            controls.addWidget(label)
            controls.addWidget(spin)
            controls.addStretch(1)
            axis_box.addLayout(controls)
            slider = QSlider(Qt.Orientation.Horizontal)
            fine = QSlider(Qt.Orientation.Horizontal)
            for title, bar in ((tr('Coarse'), slider), (tr('Fine'), fine)):
                bar.setRange(-1000, 1000)
                bar.setInvertedAppearance(axis == 0)
                bar.setInvertedControls(axis == 0)
                bar_row = QHBoxLayout()
                bar_row.addWidget(QLabel(title))
                bar_row.addWidget(bar, 1)
                axis_box.addLayout(bar_row)
            self.spins.append(spin)
            self.sliders.append(slider)
            self.fine_sliders.append(fine)
            self.axis_labels.append(label)
            spin.valueChanged.connect(lambda value, a=axis: self._spin_changed(a, value))
            slider.valueChanged.connect(lambda value, a=axis: self._slider_changed(a, value))
            fine.valueChanged.connect(lambda value, a=axis: self._fine_changed(a, value))
            fine.sliderReleased.connect(self._sync_editors)
        layout.insertWidget(2, self.manual)
        self.slice_controls = QWidget()
        self.slice_layout = QVBoxLayout(self.slice_controls)
        self.slice_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slice_controls)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.fitted.connect(self._apply_fit)
        self.toggle.toggled.connect(self._mode_controls)
        self._mode_controls(False)

    @property
    def viewer(self):
        if self._viewer is None:
            self._viewer = SpectrumViewer(self)
            self._viewer.extend_axis_ticks = True
            self._viewer.set_data_bounds_visible(False)
            self._viewer.contour_controls.hide()
        return self._viewer

    @property
    def reference_index(self):
        if self.use_reference.isChecked() and self.reference_choice.currentData() is not None:
            return int(self.reference_choice.currentData())
        return 0

    def _mode_controls(self, enabled):
        self.generation += 1
        for widget in (self.use_reference, self.fit_button, self.manual, self.export_button,
                       self.display_title, self.spectrum_tabs, self.aspect_row):
            widget.setVisible(enabled)
        self.reference_row.setVisible(
            enabled and len(self.spectra) == 3 and self.use_reference.isChecked()
        )
        self.slice_controls.setVisible(enabled)

    def set_spectra(self, spectra, names, tooltips=None, display_settings=None):
        self.generation += 1
        self.fit_button.setEnabled(not self.fit_running)
        tips = list(tooltips or names)
        retained = [i < len(self.spectra) and name == self.names[i]
                    and tips[i] == self.tooltips[i]
                    and [a.label for a in spectrum_axes(spectrum)]
                    == [a.label for a in spectrum_axes(self.spectra[i])]
                    for i, (name, spectrum) in enumerate(zip(names, spectra))]
        old_reference = self.use_reference.isChecked() if all(retained[:2]) else False
        old_choice = self.reference_choice.currentData() if old_reference else 1
        self.shifts = [self.shifts[i].copy() if keep else np.zeros(spectrum.data.ndim)
                       for i, (keep, spectrum) in enumerate(zip(retained, spectra))]
        self.spectra, self.names, self.tooltips = list(spectra), list(names), tips
        for index, keep in enumerate(retained):
            if not keep:
                settings = display_settings[index] if display_settings else (2.9791, 8)
                start, count = settings[:2]
                hide_positive, hide_negative = (
                    settings[2:4] if len(settings) >= 4 else (False, False)
                )
                controls = self.spectrum_controls[index]
                with QSignalBlocker(controls):
                    controls.start.setValue(start)
                    controls.levels.setValue(count)
                    controls.visible.setChecked(True)
                    controls.hide_positive.setChecked(hide_positive)
                    controls.hide_negative.setChecked(hide_negative)
        for combo in (self.moving, self.reference_choice):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.spectrum_tabs.clear()
        for index, (name, controls) in enumerate(zip(names, self.spectrum_controls)):
            self.spectrum_tabs.addTab(controls, tr('Spectrum {p0}', p0=index + 1))
            self.spectrum_tabs.setTabToolTip(index, self.tooltips[index])
            controls.setToolTip(self.tooltips[index])
            controls.start.setEnabled(spectra[index].data.ndim == 2)
            controls.slider.setEnabled(spectra[index].data.ndim == 2)
            controls.levels.setEnabled(spectra[index].data.ndim == 2)
            controls.count_slider.setEnabled(spectra[index].data.ndim == 2)
            controls.hide_positive.setEnabled(spectra[index].data.ndim == 2)
            controls.hide_negative.setEnabled(spectra[index].data.ndim == 2)
        self.status.clear()
        try:
            validate_spectra(spectra)
            self.toggle.setEnabled(True)
        except ValueError as exc:
            self.toggle.setChecked(False)
            self.toggle.setEnabled(False)
            self.status.setText(str(exc))
        with QSignalBlocker(self.reference_choice):
            self.reference_choice.clear()
            for index, name in enumerate(names[1:], 1):
                self.reference_choice.addItem(name, index)
                self.reference_choice.setItemData(
                    index - 1, self.tooltips[index], Qt.ItemDataRole.ToolTipRole,
                )
            selected = self.reference_choice.findData(old_choice)
            self.reference_choice.setCurrentIndex(max(0, selected))
        with QSignalBlocker(self.use_reference):
            self.use_reference.setChecked(old_reference)
        self._reference_changed()
        for index, button in enumerate(self.color_buttons):
            button.setVisible(index < len(names))
            if index < len(names):
                button.setText(tr('Color {p0}', p0=index + 1))
                button.setToolTip(self.tooltips[index])
                self._color_style(index)
        self._mode_controls(self.toggle.isChecked())

    def _reference_changed(self, *_args):
        self.generation += 1
        if not self.spectra:
            return
        anchor = self.reference_index
        if any(s.data.ndim != self.spectra[anchor].data.ndim for s in self.spectra):
            return
        # Rebase all display offsets so the selected reference stays at its native coordinates.
        origin = self.shifts[anchor].copy()
        self.shifts = [shift - origin for shift in self.shifts]
        previous_moving = self.moving.currentData()
        with QSignalBlocker(self.moving):
            self.moving.clear()
            for index, name in enumerate(self.names):
                if index != anchor:
                    self.moving.addItem(name, index)
                    self.moving.setItemData(self.moving.count() - 1, self.tooltips[index],
                                            Qt.ItemDataRole.ToolTipRole)
            selected = self.moving.findData(previous_moving)
            if selected >= 0:
                self.moving.setCurrentIndex(selected)
        self._mode_controls(self.toggle.isChecked())
        self._sync_editors()
        if self.toggle.isChecked():
            self.render()

    def _sync_editors(self, *_args, reset_fine=True):
        if not self.spectra or self.moving.currentData() is None:
            return
        axes = spectrum_axes(self.spectra[self.reference_index])
        index = int(self.moving.currentData())
        ndim = len(axes)
        for position in range(2):
            self.axis_groups[position].setVisible(position < ndim)
            for widget in (self.axis_labels[position], self.spins[position],
                           self.sliders[position], self.fine_sliders[position]):
                widget.setVisible(position < ndim)
            if position >= ndim:
                continue
            axis = axes[ndim - 1 - position]
            self.axis_labels[position].setText(('X ' if position == 0 else 'Y ') + axis.label)
            extent = abs(float(axis.ppm[-1] - axis.ppm[0]))
            spin, slider = self.spins[position], self.sliders[position]
            with QSignalBlocker(spin), QSignalBlocker(slider):
                spin.setRange(-extent, extent)
                spin.setSingleStep(abs(float(axis.ppm[1] - axis.ppm[0])) / 10)
                value = float(self.shifts[index][ndim - 1 - position])
                spin.setValue(value)
                slider.setValue(round(value / extent * 1000))
            if reset_fine:
                self._fine_origins[position] = value
                with QSignalBlocker(self.fine_sliders[position]):
                    self.fine_sliders[position].setValue(0)
            span = 5 * abs(float(axis.ppm[1] - axis.ppm[0]))
            self.fine_sliders[position].setToolTip(tr(
                'Fine range: ±{p0:.6f} ppm (five data points); release to recenter.', p0=span,
            ))

    def _spin_changed(self, position, value):
        index = self.moving.currentData()
        if index is None:
            return
        self.generation += 1
        ndim = self.spectra[int(index)].data.ndim
        self.shifts[int(index)][ndim - 1 - position] = value
        self._sync_editors()
        self.apply_transforms()

    def _slider_changed(self, position, value):
        self.spins[position].setValue(value / 1000 * self.spins[position].maximum())

    def _fine_changed(self, position, value):
        index = self.moving.currentData()
        if index is None:
            return
        self.generation += 1
        ndim = self.spectra[int(index)].data.ndim
        axis = spectrum_axes(self.spectra[self.reference_index])[ndim - 1 - position]
        span = 5 * abs(float(axis.ppm[1] - axis.ppm[0]))
        self.shifts[int(index)][ndim - 1 - position] = (
            self._fine_origins[position] + value / 1000 * span
        )
        self._sync_editors(reset_fine=False)
        self.apply_transforms()

    def choose_color(self, index):
        color = QColorDialog.getColor(QColor(self.colors[index]), self,
                                      tr('Spectrum color'))
        if color.isValid():
            self.set_color(index, color.name())

    def set_color(self, index, color):
        self.colors[index] = color
        self._color_style(index)
        self.apply_transforms()
        self.changed.emit()

    def _color_style(self, index):
        self.color_buttons[index].setStyleSheet(
            'QPushButton { border-bottom: 3px solid ' + self.colors[index] + '; }'
        )

    def render(self):
        validate_spectra(self.spectra)
        old_ranges = self.viewer.plot.getViewBox().viewRange()
        for curve in self.curves:
            self.viewer.plot.removeItem(curve)
        self.viewer.clear()
        self.curves = []
        anchor = self.reference_index
        base = self.spectra[anchor]
        if base.data.ndim == 1:
            self.viewer.add_spectrum(base, name=self.names[anchor])
            for item in self.viewer.plot.listDataItems():
                item.setVisible(False)
            for spectrum in self.spectra:
                curve = pg.PlotDataItem()
                self.viewer.plot.addItem(curve)
                self.curves.append(curve)
        else:
            order = [anchor] + [i for i in range(len(self.spectra)) if i != anchor]
            for index in order:
                self.viewer.add_spectrum(self.spectra[index], name=self.names[index],
                                         color=self.colors[index])
        self.viewer.contour_controls.hide()
        self.apply_transforms()
        self._apply_display_settings()
        if self.viewer.plot.plotItem.legend is not None:
            self.viewer.plot.plotItem.legend.clear()
        legend = self.viewer.plot.addLegend()
        for index, name in enumerate(self.names):
            legend.addItem(pg.PlotDataItem(pen=pg.mkPen(self.colors[index], width=1)), name)
        key = (tuple(self.names), anchor, tuple(
            tuple((a.label, len(a.ppm), float(a.ppm[0]), float(a.ppm[-1]))
                  for a in spectrum_axes(spectrum))
            for spectrum in self.spectra
        ))
        self.viewer.reset_view()
        if getattr(self, '_render_key', None) == key:
            self.viewer.plot.getViewBox().setRange(
                xRange=old_ranges[0], yRange=old_ranges[1], padding=0,
            )
        self._render_key = key

    def apply_transforms(self):
        if not self.spectra or not self.toggle.isChecked():
            return
        anchor = self.reference_index
        base = self.spectra[anchor]
        if base.data.ndim == 1:
            if len(self.curves) != len(self.spectra):
                return
            for index, (spectrum, curve) in enumerate(zip(self.spectra, self.curves)):
                curve.setData(spectrum.axis.ppm + self.shifts[index][0], spectrum.data,
                              pen=pg.mkPen(self.colors[index], width=1))
        else:
            order = [anchor] + [i for i in range(len(self.spectra)) if i != anchor]
            if len(self.viewer.layers) != len(order):
                return
            for layer, index in zip(self.viewer.layers, order):
                source = self.spectra[index]
                scale, offset = [], []
                for ref, axis, shift in zip(base.axes, source.axes, self.shifts[index]):
                    rp, sp = ref.ppm, axis.ppm
                    step = rp[1] - rp[0]
                    scale.append((sp[1] - sp[0]) / step)
                    offset.append((sp[0] + shift - rp[0]) / step)
                layer.setTransform(QTransform(scale[1], 0, 0, scale[0], offset[1], offset[0]))
                layer.setPen(
                    pg.mkPen(self.colors[index], width=1),
                    neg_pen=pg.mkPen(self.colors[index], width=1),
                )

    def _apply_display_settings(self):
        if self._viewer is None or not self.spectra or not self.toggle.isChecked():
            return
        anchor = self.reference_index
        if self.spectra[anchor].data.ndim == 1:
            for index, curve in enumerate(self.curves):
                curve.setVisible(self.spectrum_controls[index].visible.isChecked())
        else:
            order = [anchor] + [i for i in range(len(self.spectra)) if i != anchor]
            for layer_index, index in enumerate(order):
                if layer_index >= len(self.viewer.layers):
                    continue
                controls = self.spectrum_controls[index]
                self.viewer.set_layer_contours(layer_index, controls.start.value(),
                                               controls.levels.value())
        self._apply_display_visibility()

    def _apply_display_visibility(self):
        if self._viewer is None or not self.spectra or not self.toggle.isChecked():
            return
        anchor = self.reference_index
        if self.spectra[anchor].data.ndim == 1:
            for index, curve in enumerate(self.curves):
                curve.setVisible(self.spectrum_controls[index].visible.isChecked())
        else:
            order = [anchor] + [i for i in range(len(self.spectra)) if i != anchor]
            for layer_index, index in enumerate(order):
                if layer_index >= len(self.viewer.layers):
                    continue
                controls = self.spectrum_controls[index]
                layer = self.viewer.layers[layer_index]
                layer.setVisible(controls.visible.isChecked())
                layer.set_sign_visibility(
                    not controls.hide_positive.isChecked(),
                    not controls.hide_negative.isChecked(),
                )

    def auto_fit(self):
        if self.fit_running:
            return
        self.fit_running = True
        self.fit_button.setEnabled(False)
        self.fit_button.setText(tr('Fitting spectra…'))
        self.status.setText(tr('Fitting spectra…'))
        generation = self.generation
        anchor = self.reference_index
        spectra = list(self.spectra)
        def work():
            try:
                results = {i: fit_translation(spectra[anchor], spectrum)
                           for i, spectrum in enumerate(spectra) if i != anchor}
                self.fitted.emit(generation, results, None)
            except Exception as exc:  # Worker failures must restore the UI's fit action.
                self.fitted.emit(generation, None, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _apply_fit(self, generation, results, error):
        self.fit_running = False
        self.fit_button.setEnabled(True)
        self.fit_button.setText(tr('Auto-fit overlay'))
        if generation != self.generation or not self.toggle.isChecked():
            if self.status.text() == tr('Fitting spectra…'):
                self.status.clear()
            return
        if error:
            self.status.setText(error)
            return
        for index, (shift, _score) in results.items():
            self.shifts[index] = np.array(shift)
        self.generation += 1
        self._sync_editors()
        self.apply_transforms()
        text = '; '.join(tr('{p0}: peak match {p1:.1%}', p0=self.names[i], p1=score)
                         for i, (_shift, score) in results.items())
        self.status.setText(text)

    def export_svg(self, path, ppm_ranges=None, aspect_ratio=None):
        from gui.overlay_svg_export import export_svg

        export_svg(self.viewer, path, ppm_ranges, aspect_ratio)

    def _export(self):
        from gui.overlay_svg_export import OverlaySvgExportDialog

        dialog = OverlaySvgExportDialog(
            self.viewer, self, directory=self.export_directory,
            spectra=list(zip(self.names, self.colors)),
        )
        dialog.exec()
