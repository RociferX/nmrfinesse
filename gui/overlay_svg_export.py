"""SVG export and preview for the spectrum viewer's current overlay."""

from __future__ import annotations

import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path

from qtcompat.QtCore import QRectF, QSignalBlocker, QSize, Qt
from qtcompat.QtGui import QPainter, QPainterPath, QPainterPathStroker, QPixmap
from qtcompat.QtSvg import QSvgGenerator, QSvgRenderer
from qtcompat.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsPathItem,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui_support.i18n import tr
from ui_support.numeric_inputs import CommitDoubleSpinBox


class _SvgPreviewLabel(QLabel):
    """Fit a complete SVG preview into its viewport without changing its aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

    def set_source_pixmap(self, pixmap):
        self._source_pixmap = pixmap
        self._fit_pixmap()

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._fit_pixmap()

    def _fit_pixmap(self):
        if self._source_pixmap is None or self.width() < 1 or self.height() < 1:
            return
        ratio = self._source_pixmap.devicePixelRatioF()
        target = QSize(round(self.width() * ratio), round(self.height() * ratio))
        self.setPixmap(self._source_pixmap.scaled(
            target, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))


def _spectrum_and_axes(viewer):
    spectrum = viewer.displayed_spectrum
    if spectrum is None:
        raise ValueError(tr('No spectrum is available for SVG export.'))
    if getattr(viewer, '_mode_1d', False):
        return spectrum, spectrum.axis, None
    return spectrum, spectrum.x_axis, spectrum.y_axis


def _current_ppm_ranges(viewer):
    _spectrum, x_axis, y_axis = _spectrum_and_axes(viewer)
    ranges = viewer.plot.getViewBox().viewRange()
    if y_axis is None:  # 1D X is ppm, while Y is intensity.
        return tuple(ranges[0]), tuple(ranges[1])
    return (
        tuple(_ppm_at_index(x_axis, float(i)) for i in ranges[0]),
        tuple(_ppm_at_index(y_axis, float(i)) for i in ranges[1]),
    )


def _ppm_at_index(axis, index):
    """Map point-index to ppm, extending the axis slope beyond acquired endpoints."""
    if axis.size < 2 or 0 <= index <= axis.size - 1:
        return float(axis.ppm_at_f(index))
    endpoint, neighbor = (0, 1) if index < 0 else (axis.size - 1, axis.size - 2)
    return float(axis.ppm[endpoint] + (index - endpoint) *
                 (axis.ppm[neighbor] - axis.ppm[endpoint]) / (neighbor - endpoint))


def _data_ranges(viewer, ppm_ranges):
    _spectrum, x_axis, y_axis = _spectrum_and_axes(viewer)
    if ppm_ranges is None:
        return None
    x_range, y_range = ppm_ranges
    if x_range[0] == x_range[1] or y_range[0] == y_range[1]:
        raise ValueError(tr('Each axis range must have two different values.'))
    if y_axis is None:
        return (tuple(map(float, x_range)), tuple(map(float, y_range)))

    def ppm_to_index(axis, ppm):
        """Map ppm linearly, extending the axis slope beyond acquired endpoints."""
        ppm = float(ppm)
        if axis.size < 2:
            return float(axis.index_at_f(ppm))
        first, last = float(axis.ppm[0]), float(axis.ppm[-1])
        if min(first, last) <= ppm <= max(first, last):
            return float(axis.index_at_f(ppm))
        endpoint, neighbor = (
            (0, 1)
            if abs(ppm - first) < abs(ppm - last)
            else (axis.size - 1, axis.size - 2)
        )
        p0, p1 = float(axis.ppm[endpoint]), float(axis.ppm[neighbor])
        return float(endpoint + (ppm - p0) / (p1 - p0) * (neighbor - endpoint))

    # 2D images and contours are positioned in point-index coordinates.
    return (
        tuple(sorted(ppm_to_index(x_axis, ppm) for ppm in x_range)),
        tuple(sorted(ppm_to_index(y_axis, ppm) for ppm in y_range)),
    )


def _stroke_path_batches(path):
    """Bound each stroked SVG path below Qt SVG's 32,767-element parser limit."""
    batch = QPainterPath()
    # Viewer contours and traces are polylines. Split before stroking so the
    # inner and outer outlines of every stroke stay together in the SVG.
    for polygon in path.toSubpathPolygons():
        for start in range(0, len(polygon) - 1, 1023):
            part = polygon.mid(start, 1024)
            if batch.elementCount() + len(part) > 1024:
                yield batch
                batch = QPainterPath()
            batch.addPolygon(part)
    if not batch.isEmpty():
        yield batch


def _screen_space_data(viewer, plot, view_box):
    """Bake fixed-width vector strokes and clip them before the SVG paint engine sees them."""
    clip = QPainterPath()
    clip.addRect(view_box.sceneBoundingRect())
    originals, proxies = [], []
    if viewer.displayed_spectrum.data.ndim == 1:
        from pyqtgraph import PlotDataItem

        entries = [(item, [(item.curve.getPath(), item.opts['pen'])])
                   for item in viewer.plot.listDataItems()
                   if isinstance(item, PlotDataItem) and item.isVisible()]
    else:
        entries = [(layer, layer.vector_paths()) for layer in viewer.layers if layer.isVisible()]
    try:
        for item, paths in entries:
            for path, pen in paths:
                if path.isEmpty() or pen is None or pen.style() == Qt.PenStyle.NoPen:
                    continue
                mapped = item.mapToScene(path)
                stroker = QPainterPathStroker()
                width = pen.widthF() or 1.0
                if pen.isCosmetic():
                    width /= viewer.plot.devicePixelRatioF()
                stroker.setWidth(width)
                stroker.setCapStyle(pen.capStyle())
                stroker.setJoinStyle(pen.joinStyle())
                stroker.setMiterLimit(pen.miterLimit())
                if pen.style() != Qt.PenStyle.SolidLine:
                    stroker.setDashPattern(pen.dashPattern())
                    stroker.setDashOffset(pen.dashOffset())
                for batch in _stroke_path_batches(mapped):
                    outline = stroker.createStroke(batch)
                    if not clip.boundingRect().contains(outline.boundingRect()):
                        outline = outline.intersected(clip)
                    if outline.isEmpty():
                        continue
                    proxy = QGraphicsPathItem(plot.mapFromScene(outline), plot)
                    proxy.setPen(Qt.PenStyle.NoPen)
                    proxy.setBrush(pen.brush())
                    proxy.setOpacity(item.opacity())
                    proxy.setZValue(1000)
                    proxies.append(proxy)
            originals.append(item)
            item.hide()
        return originals, proxies
    except Exception:
        _restore_data_items(originals, proxies)
        raise


def _restore_data_items(originals, proxies):
    for proxy in proxies:
        proxy.scene().removeItem(proxy)
    for item in originals:
        item.show()


def _render_svg(viewer, path, ppm_ranges=None, aspect_ratio=None):
    """Render the current plot with temporary view/legend changes, restoring both."""
    plot = viewer.plot.plotItem
    view_box = viewer.plot.getViewBox()
    old_view_state = view_box.getState()
    old_view_state['linkedViews'] = list(view_box.state['linkedViews'])
    old_min_rect = deepcopy(getattr(view_box, '_min_rect', None))
    bottom_axis = viewer.plot.getAxis('bottom')
    left_axis = viewer.plot.getAxis('left')
    axis_size_constraints = (
        (left_axis.minimumWidth(), left_axis.maximumWidth()),
        (bottom_axis.minimumHeight(), bottom_axis.maximumHeight()),
    )
    old_axis_ticks = (
        deepcopy(getattr(bottom_axis, '_tickLevels', None)),
        deepcopy(getattr(left_axis, '_tickLevels', None)),
    )
    refresh_ticks_connected = bool(getattr(viewer, '_axis_refresh_connected', False))
    old_geometry = QRectF(plot.geometry())
    source = plot.sceneBoundingRect()
    width, height = max(1, round(source.width())), max(1, round(source.height()))
    if aspect_ratio is not None:
        height = max(1, round(width / float(aspect_ratio)))
    size = QSize(width, height)
    scene = viewer.plot.scene()
    legend = plot.legend
    legend_visible = legend.isVisible() if legend is not None else None
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(size)
    generator.setResolution(viewer.plot.logicalDpiX())
    generator.setViewBox(QRectF(0, 0, size.width(), size.height()))
    generator.setTitle(tr('Overlay comparison'))
    painter = QPainter()
    originals, proxies = [], []
    if not painter.begin(generator):
        raise OSError(tr('Unable to write the SVG image.'))
    try:
        # Keep the ViewBox pixel rectangle fixed while temporary tick labels are measured.
        left_axis.setMinimumWidth(left_axis.width())
        left_axis.setMaximumWidth(left_axis.width())
        bottom_axis.setMinimumHeight(bottom_axis.height())
        bottom_axis.setMaximumHeight(bottom_axis.height())
        if aspect_ratio is not None:
            plot.setGeometry(QRectF(old_geometry.x(), old_geometry.y(), width, height))
            plot.layout.activate()
            source = plot.sceneBoundingRect()
        if legend is not None:
            legend.hide()
        ranges = _data_ranges(viewer, ppm_ranges)
        if ranges is not None:
            # A locked aspect ratio can silently expand one axis beyond the requested ppm range.
            view_box.setAspectLocked(False)
            view_box.enableAutoRange(enable=False)
            view_box.setLimits(
                xMin=None, xMax=None, yMin=None, yMax=None,
                minXRange=None, maxXRange=None, minYRange=None, maxYRange=None,
            )
            if hasattr(view_box, '_min_rect'):
                view_box._min_rect = None
            view_box.setRange(xRange=ranges[0], yRange=ranges[1], padding=0)
        view_box.enableAutoRange(enable=False)
        view_box.updateMatrix()
        originals, proxies = _screen_space_data(viewer, plot, view_box)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(QRectF(0, 0, size.width(), size.height()), viewer.plot.backgroundBrush())
        scene.render(painter, QRectF(0, 0, size.width(), size.height()), source)
    finally:
        painter.end()
        _restore_data_items(originals, proxies)
        if refresh_ticks_connected:
            view_box.sigRangeChanged.disconnect(viewer._refresh_visible_ticks)
        bottom_axis.setTicks(old_axis_ticks[0])
        left_axis.setTicks(old_axis_ticks[1])
        if legend is not None:
            legend.setVisible(legend_visible)
        plot.setGeometry(old_geometry)
        left_axis.setMinimumWidth(axis_size_constraints[0][0])
        left_axis.setMaximumWidth(axis_size_constraints[0][1])
        bottom_axis.setMinimumHeight(axis_size_constraints[1][0])
        bottom_axis.setMaximumHeight(axis_size_constraints[1][1])
        plot.layout.activate()
        view_box.setState(old_view_state)
        if hasattr(view_box, '_min_rect'):
            view_box._min_rect = old_min_rect
        if refresh_ticks_connected:
            view_box.sigRangeChanged.connect(viewer._refresh_visible_ticks)


def export_svg(viewer, path, ppm_ranges=None, aspect_ratio=None):
    """Export the active viewer plot as SVG using optional ``((xmin,xmax),(ymin,ymax))``.

    2D ranges are ppm and are mapped to point-index plot coordinates. In 1D, X is ppm
    and Y is intensity. The viewer's ranges and legend visibility are restored afterward.
    """
    _spectrum_and_axes(viewer)
    _render_svg(viewer, path, ppm_ranges, aspect_ratio)


def _spectrum_color_labels(spectra):
    color_names = {'#1f77b4': tr('Blue'), '#d62728': tr('Red'), '#2ca02c': tr('Green')}
    return [f'{name}_{color_names.get(color.lower(), "")}({color})'
            for name, color in spectra]


class OverlaySvgExportDialog(QDialog):
    """Range controls, SVG preview, and save action for overlay export."""

    def __init__(self, viewer, parent=None, *, directory=None, spectra=None):
        super().__init__(parent)
        self.viewer = viewer
        self.setProperty('wideDialog', True)
        self.export_directory = Path(directory) if directory is not None else None
        labels = _spectrum_color_labels(spectra or [])
        filename = '_vs_'.join(labels) or 'overlay'
        self.default_filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename) + '.svg'
        self.setWindowTitle(tr('Export overlay SVG'))
        x_range, y_range = _current_ppm_ranges(viewer)
        self.x_min, self.x_max = self._range_fields(x_range)
        self.y_min, self.y_max = self._range_fields(y_range)
        form = QFormLayout()
        spectrum, x_axis, y_axis = _spectrum_and_axes(viewer)
        x_unit = tr('ppm') if y_axis is not None or spectrum.ppm_valid else tr('points')
        y_unit = tr('ppm') if y_axis is not None else tr('intensity')
        range_title = QLabel(tr('Export range'))
        range_title.setObjectName('SectionTitle')
        form.addRow(range_title)
        form.addRow(tr('X range ({p0}; {p1})', p0=x_axis.label, p1=x_unit),
                    self._row(self.x_min, self.x_max))
        y_label = y_axis.label if y_axis is not None else tr('Y')
        form.addRow(tr('Y range ({p0}; {p1})', p0=y_label, p1=y_unit),
                    self._row(self.y_min, self.y_max))
        self.aspect_spin = CommitDoubleSpinBox()
        self.aspect_spin.setRange(.25, 4)
        self.aspect_spin.setDecimals(2)
        self.aspect_spin.setSingleStep(.05)
        plot_rect = viewer.plot.plotItem.sceneBoundingRect()
        self.aspect_spin.setValue(plot_rect.width() / max(1, plot_rect.height()))
        self.aspect_spin.setToolTip(tr(
            'Image width divided by height. Changing it keeps the selected ppm ranges.'
        ))
        self.aspect_slider = QSlider(Qt.Orientation.Horizontal)
        self.aspect_slider.setRange(25, 400)
        self.aspect_slider.setPageStep(25)
        self.aspect_slider.setTracking(False)
        self.aspect_slider.setValue(round(self.aspect_spin.value() * 100))
        aspect_row = QHBoxLayout()
        aspect_row.addWidget(self.aspect_spin)
        aspect_row.addWidget(self.aspect_slider, 1)
        form.addRow(tr('Aspect (width / height)'), aspect_row)
        self.range_description = QLabel(tr('Ranges default to the current displayed view.'))
        self.range_description.setObjectName('MutedText')
        layout = QVBoxLayout(self)
        layout.addWidget(self.range_description)
        if labels:
            self.spectrum_description = QLabel(tr('Spectra and colors: {p0}', p0='; '.join(labels)))
            self.spectrum_description.setWordWrap(True)
            self.spectrum_description.setObjectName('PanelSubtitle')
            layout.addWidget(self.spectrum_description)
        layout.addLayout(form)
        preview_title = QLabel(tr('SVG preview'))
        preview_title.setObjectName('SectionTitle')
        layout.addWidget(preview_title)
        self.preview_button = QPushButton(tr('Preview'))
        self.preview_button.clicked.connect(self.update_preview)
        layout.addWidget(self.preview_button, 0, Qt.AlignmentFlag.AlignRight)
        self.preview = _SvgPreviewLabel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr('Close'))
        self.export_button = buttons.addButton(
            tr('Export SVG'), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.export_button.setObjectName('PrimaryAction')
        self.export_button.setAutoDefault(False)
        self.export_button.setDefault(False)
        self.export_button.clicked.connect(self.save_svg)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.aspect_spin.valueChanged.connect(self._aspect_changed)
        self.aspect_slider.valueChanged.connect(
            lambda value: self.aspect_spin.setValue(value / 100)
        )
        self.update_preview()

    def _aspect_changed(self, value):
        with QSignalBlocker(self.aspect_slider):
            self.aspect_slider.setValue(round(value * 100))
        self.update_preview()

    @staticmethod
    def _range_fields(values):
        result = []
        for value in values:
            spin = CommitDoubleSpinBox()
            spin.setDecimals(6)
            spin.setRange(-1e9, 1e9)
            spin.setValue(float(value))
            result.append(spin)
        return result

    @staticmethod
    def _row(first, second):
        row = QHBoxLayout()
        row.addWidget(first)
        row.addWidget(second)
        container = QWidget()
        container.setLayout(row)
        return container

    def ppm_ranges(self):
        return ((self.x_min.value(), self.x_max.value()),
                (self.y_min.value(), self.y_max.value()))

    def update_preview(self):
        try:
            with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as temp:
                temp_path = temp.name
            _render_svg(self.viewer, temp_path, self.ppm_ranges(), self.aspect_spin.value())
            renderer = QSvgRenderer(temp_path)
            if not renderer.isValid():
                raise OSError(tr('Unable to render the SVG preview.'))
            size = renderer.defaultSize()
            ratio = self.viewer.plot.devicePixelRatioF()
            pixmap = QPixmap(QSize(round(size.width() * ratio), round(size.height() * ratio)))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill()
            painter = QPainter(pixmap)
            renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
            painter.end()
            self.preview.set_source_pixmap(pixmap)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr('SVG preview'), str(exc))
        finally:
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def save_svg(self):
        default_path = Path(self.default_filename)
        if self.export_directory is not None:
            try:
                self.export_directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.warning(self, tr('Export overlay SVG'), str(exc))
                return
            default_path = self.export_directory / default_path
        path, _filter = QFileDialog.getSaveFileName(
            self, tr('Export overlay SVG'), str(default_path), 'SVG (*.svg)'
        )
        if not path:
            return
        if not Path(path).suffix:
            path += '.svg'
        try:
            export_svg(self.viewer, path, self.ppm_ranges(), self.aspect_spin.value())
            self.accept()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr('Export overlay SVG'), str(exc))
