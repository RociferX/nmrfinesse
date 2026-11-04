"""NMR ViewBox dedicated to the viewer: frame selection zoom (RectMode) + middle-click drag pan +
wheel zoom. pyqtgraph's RectMode will treat the middle button as a frame selection zoom; and its
pan branch ``QPointF * numpy array `` will cause TypeError (PyQt6 measured), so the pan is
calculated by itself. 0.2.133: The right click no longer responds to any behaviour; the view
range is limited to the complete data range (reset_view Within the smallest rectangle obtained)
-- zooming out cannot shrink the complete spectrum out of the field of view.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

_MIN_VIEW_RANGE = 8.0


class NMRViewBox(pg.ViewBox):
    'Keep the "middle-click drag pan" gesture under RectMode and limit the view boundaries.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_rect: list[tuple[float, float]] | None = None
        self._min_span = (_MIN_VIEW_RANGE, _MIN_VIEW_RANGE)
        self.wheel_y_exponent = 1.0
        self._wheel_zoom = False



    def mouseDragEvent(self, ev, axis=None) -> None:
        if ev.button() == QtCore.Qt.MouseButton.RightButton:
            ev.accept()
            return
        # 1D mode/PanMode: left button is for crosshair tracking, not panning (0.2.150)
        if (
            ev.button() == QtCore.Qt.MouseButton.LeftButton
            and self.state["mouseMode"] == pg.ViewBox.PanMode
        ):
            ev.accept()
            return
        if ev.button() == QtCore.Qt.MouseButton.MiddleButton:
            ev.accept()
            pos = ev.pos()
            last_pos = ev.lastPos()
            diff = np.array(
                [pos.x() - last_pos.x(), pos.y() - last_pos.y()]
            ) * -1.0
            mouse_enabled = np.array(self.state["mouseEnabled"], dtype=float)
            transform = self.childGroup.transform().inverted()[0]
            p1 = transform.map(
                QtCore.QPointF(float(diff[0]), float(diff[1]))
            )
            p0 = transform.map(QtCore.QPointF(0.0, 0.0))
            moved = p1 - p0
            x = moved.x() if mouse_enabled[0] == 1 else None
            y = moved.y() if mouse_enabled[1] == 1 else None
            self._resetTarget()
            if x is not None or y is not None:
                self.translateBy(x=x, y=y)
            self.sigRangeChangedManually.emit(self.state["mouseEnabled"])
            return
        super().mouseDragEvent(ev, axis)





    def wheelEvent(self, ev, axis=None):
        """The scroll wheel clamps immediately after zooming (zooming cannot exceed the complete
        range).
        """
        self._wheel_zoom = True
        try:
            super().wheelEvent(ev, axis)
        finally:
            self._wheel_zoom = False
        self._clamp_view_range()

    def scaleBy(self, s=None, center=None, **kwargs):
        'Clamp immediately after scaling(roller/Zoom animation).'
        if (self._wheel_zoom and self.wheel_y_exponent != 1.0 and s is not None
                and s[0] is not None and s[1] is not None
                and not self.state['aspectLocked']):
            s = (s[0], s[1] ** self.wheel_y_exponent)
        super().scaleBy(s=s, center=center, **kwargs)
        self._clamp_view_range()

    def translateBy(self, t=None, **kwargs):
        'Clamp immediately after translation (spectrum cannot be moved out of view).'
        super().translateBy(t=t, **kwargs)
        self._clamp_view_range()

    def set_full_range(self, x_range, y_range, padding=0, min_span=None) -> None:
        """Restore the full view and update the zoom base (reset_view is exclusive). Update
        _min_rect first and then set the range to avoid being clamped by the old base; then the
        user's zoom view cannot exceed the full range.
        """
        self._min_rect = [
            (float(x_range[0]), float(x_range[1])),
            (float(y_range[0]), float(y_range[1])),
        ]
        self._min_span = min_span or (_MIN_VIEW_RANGE, _MIN_VIEW_RANGE)
        super().setRange(xRange=x_range, yRange=y_range, padding=padding)
        if self.wheel_y_exponent != 1.0 and self.state['aspectLocked']:
            self._clamp_locked_1d([x_range, y_range])

    def setRange(self, rect=None, **kwargs):
        """Restrictions narrowed/Translate boundaries (No constraints will be applied when the
        complete range is not recorded).
        """
        super().setRange(rect=rect, **kwargs)
        if getattr(self, "_min_rect", None) is not None:
            self._clamp_view_range()

    def _clamp_view_range(self) -> None:
        """The view cannot exceed the complete data range (recorded by set_full_range). The upper
        limit of reduction = the complete range (all long sides are exposed, that is, to the
        top); translation keeps the view within the complete range; single-axis minimum span
        protection (prevents over-zooming), and the overall translation keeps the span unchanged
        when close to the boundary.
        """
        if getattr(self, "_min_rect", None) is None:
            return
        vr = self.viewRange()
        if self.wheel_y_exponent != 1.0 and self.state['aspectLocked']:
            self._clamp_locked_1d(vr)
            return
        new_ranges = list(vr)
        changed = False
        for axis_idx in (0, 1):
            mlo, mhi = self._min_rect[axis_idx][0], self._min_rect[axis_idx][1]
            mspan = mhi - mlo
            lo, hi = vr[axis_idx]
            span = hi - lo
            if mspan <= 0:
                continue

            if span > mspan:
                center = (lo + hi) / 2.0
                lo, hi = center - mspan / 2.0, center + mspan / 2.0
                changed = True

            if lo < mlo:
                shift = mlo - lo
                hi = min(hi + shift, mhi)
                lo = mlo
                changed = True
            if hi > mhi:
                shift = hi - mhi
                lo = max(lo - shift, mlo)
                hi = mhi
                changed = True

            minimum = min(mspan, self._min_span[axis_idx])
            if span < minimum:
                center = (lo + hi) / 2.0
                half = minimum / 2.0
                lo, hi = center - half, center + half
                if lo < mlo:
                    lo = mlo
                    hi = mlo + minimum
                elif hi > mhi:
                    hi = mhi
                    lo = mhi - minimum
                changed = True
            new_ranges[axis_idx] = (lo, hi)
        if changed:
            super().setRange(
                xRange=new_ranges[0], yRange=new_ranges[1], padding=0
            )


    def _clamp_locked_1d(self, ranges) -> None:
        """Keep aspect while allowing both 1D axes to become fully visible."""
        bounds = self.rect()
        aspect = float(self.state['aspectLocked'])
        view_ratio = bounds.width() / max(bounds.height(), 1e-12) / aspect
        if view_ratio <= 0 or not np.isfinite(view_ratio):
            return
        full_x, full_y = self._min_rect
        maximum = max(full_x[1]-full_x[0], (full_y[1]-full_y[0])*view_ratio)
        minimum = min(maximum, max(self._min_span[0], self._min_span[1]*view_ratio))
        xspan = min(maximum, max(minimum, ranges[0][1]-ranges[0][0]))
        spans = (xspan, xspan/view_ratio)
        corrected = []
        for axis, span in enumerate(spans):
            lo, hi = self._min_rect[axis]
            # A smaller view stays inside the data; a larger view contains it.
            lower, upper = lo+span/2, hi-span/2
            if lower > upper:
                lower, upper = upper, lower
            center = min(upper, max(lower, sum(ranges[axis])/2))
            corrected.append((center-span/2, center+span/2))
        if not np.allclose(ranges, corrected, rtol=1e-10, atol=1e-12):
            super().setRange(xRange=corrected[0], yRange=corrected[1], padding=0)
