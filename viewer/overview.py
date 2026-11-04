"""Cached full-spectrum thumbnail with the current viewport outlined."""

from __future__ import annotations

import pyqtgraph as pg
from qtcompat.QtCore import QPointF, QRectF, Qt
from qtcompat.QtGui import QColor, QPainter, QPen, QPixmap, QTransform
from qtcompat.QtWidgets import QWidget


class SpectrumOverview(QWidget):
    """Show above 150% zoom; clicking or dragging recentres the main view."""

    def __init__(self, parent, viewer):
        super().__init__(parent)
        self.viewer = viewer
        self._signature = None
        self._image = None
        self.hide()

    def refresh(self, *_args):
        vb = self.viewer.plot.getViewBox()
        bounds = vb._min_rect
        loaded = self.viewer._primary_1d is not None or bool(self.viewer.layers)
        if not loaded or bounds is None:
            self.hide()
            return
        ranges = vb.viewRange()
        zoom = max((hi - lo) / max(ranges[i][1] - ranges[i][0], 1e-30)
                   for i, (lo, hi) in enumerate(bounds)
                   if i == 0 or not self.viewer._mode_1d)
        if zoom <= 1.5 + 1e-6:
            self.hide()
            return
        top_left = self.viewer.plot.mapFromScene(vb.sceneBoundingRect().topLeft())
        width = min(190, max(80, int(vb.width() / 3)))
        height = min(125, max(60, int(vb.height() / 3)))
        self.setGeometry(top_left.x() + 8, top_left.y() + 8, width, height)
        self.show()
        self.raise_()
        self.update()

    def _mapping(self):
        vb = self.viewer.plot.getViewBox()
        (x0, x1), (y0, y1) = vb._min_rect
        area = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        sx = area.width() / max(x1 - x0, 1e-30)
        sy = area.height() / max(y1 - y0, 1e-30)
        if vb.state['xInverted']:
            sx = -sx
        if not vb.state['yInverted']:
            sy = -sy
        tx = area.right() - x0 * sx if sx < 0 else area.left() - x0 * sx
        ty = area.bottom() - y0 * sy if sy < 0 else area.top() - y0 * sy
        return area, QTransform(sx, 0, 0, sy, tx, ty)

    def _paths(self):
        if self.viewer._mode_1d:
            return tuple((item.curve.getPath(), item.opts['pen'], QTransform())
                         for item in self.viewer.plot.listDataItems()
                         if isinstance(item, pg.PlotDataItem) and item.isVisible())
        return tuple((path, pen, layer.transform())
                     for layer in self.viewer.layers if layer.isVisible()
                     for path, pen in layer.vector_paths())

    def paintEvent(self, event):
        area, mapping = self._mapping()
        paths = self._paths()
        signature = (self.size(), mapping, paths)
        if signature != self._signature:
            self._image = QPixmap(self.size())
            self._image.fill(QColor('white'))
            painter = QPainter(self._image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipRect(area)
            for path, pen, transform in paths:
                thumbnail_pen = QPen(pen)
                thumbnail_pen.setWidthF(.8)
                painter.setPen(thumbnail_pen)
                painter.drawPath((transform * mapping).map(path))
            painter.end()
            self._signature = signature
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._image)
        painter.setPen(QPen(QColor('#7a8794'), 1))
        painter.drawRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5))
        (x0, x1), (y0, y1) = self.viewer.plot.getViewBox().viewRange()
        viewport = mapping.mapRect(QRectF(x0, y0, x1 - x0, y1 - y0)).intersected(area)
        painter.setPen(QPen(QColor('#1769aa'), 1.5))
        painter.setBrush(QColor(23, 105, 170, 35))
        painter.drawRect(viewport)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._recenter(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton):
            self._recenter(event.position())
            event.accept()

    def _recenter(self, point):
        _area, mapping = self._mapping()
        center = mapping.inverted()[0].map(QPointF(point))
        vb = self.viewer.plot.getViewBox()
        (x0, x1), (y0, y1) = vb.viewRange()
        hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
        vb.setRange(xRange=(center.x() - hx, center.x() + hx),
                    yRange=(center.y() - hy, center.y() + hy), padding=0)
