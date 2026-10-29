"""Screen-aware window sizing and native dialog ownership for both Qt entry points."""

from __future__ import annotations

from qtcompat.QtCore import QEvent, QObject, QRect, QSize, QTimer
from qtcompat.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLayout,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def available_geometry(widget=None):
    owner = widget.parentWidget() if widget is not None else None
    screen = (owner.window().screen() if owner is not None else
              widget.screen() if widget is not None else None)
    screen = screen or QApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QRect(0, 0, 1024, 768)


def initial_window_size(area):
    """Use the available logical desktop rather than a fixed pixel canvas."""
    return QSize(round(area.width() * .96), round(area.height() * .94))


def _scroll_long_dialog(dialog, maximum_height):
    layout = dialog.layout()
    if (not isinstance(layout, QVBoxLayout) or dialog.property('adaptiveScroll')
            or dialog.findChild(QScrollArea) is not None
            or dialog.minimumSizeHint().height() <= maximum_height):
        return
    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    buttons = None
    while layout.count():
        item = layout.takeAt(0)
        if isinstance(item.widget(), QDialogButtonBox):
            buttons = item.widget()
        else:
            body_layout.addItem(item)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(body)
    layout.addWidget(scroll, 1)
    if buttons is not None:
        layout.addWidget(buttons)
    dialog.setProperty('adaptiveScroll', True)


def fit_dialog(dialog):
    """Fit content to the current screen, keeping confirmation controls reachable."""
    if isinstance(dialog, QFileDialog):
        return
    area = available_geometry(dialog)
    maximum = QSize(max(1, round(area.width() * .94)), max(1, round(area.height() * .9)))
    if dialog.isVisible():
        frame = dialog.frameGeometry().size() - dialog.size()
        maximum.setWidth(min(maximum.width(), max(1, area.width() - frame.width())))
        maximum.setHeight(min(maximum.height(), max(1, area.height() - frame.height())))
    _scroll_long_dialog(dialog, maximum.height())
    if dialog.layout() is not None:
        dialog.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
    minimum = dialog.minimumSize()
    dialog.setMinimumSize(min(minimum.width(), maximum.width()),
                          min(minimum.height(), maximum.height()))
    if not dialog.property('adaptiveSized'):
        metrics = dialog.fontMetrics()
        wide = (dialog.property('wideDialog') or dialog.findChild(QPlainTextEdit)
                or dialog.findChild(QTableWidget) or dialog.findChild(QTextBrowser))
        hint = dialog.sizeHint()
        scroll_height = (round(area.height() * .75)
                         if dialog.findChild(QScrollArea) is not None else 0)
        preferred = (QSize(max(hint.width(), metrics.horizontalAdvance('M') * 72),
                           max(metrics.height() * 24, hint.height())) if wide else
                     QSize(max(hint.width(), metrics.horizontalAdvance('M') * 45),
                           max(hint.height(), metrics.height() * 10, scroll_height)))
        dialog.resize(preferred.boundedTo(maximum))
        dialog.setProperty('adaptiveSized', True)
    else:
        dialog.resize(dialog.size().boundedTo(maximum))


def place_dialog(dialog):
    """Set native transient ownership before mapping; position manually only on X11."""
    owner = dialog.parentWidget()
    owner = owner.window() if owner is not None else QApplication.activeWindow()
    if owner is dialog or (owner is not None and not owner.isWindow()):
        owner = None
    if owner is not None:
        owner.winId()
        dialog.winId()
        handle = dialog.windowHandle()
        if handle is not None:
            handle.setTransientParent(owner.windowHandle())
    if QApplication.platformName().startswith('wayland'):
        return
    area = available_geometry(dialog)
    center = owner.frameGeometry().center() if owner is not None else area.center()
    frame = dialog.frameGeometry().size()
    x = max(area.left(), min(center.x() - frame.width() // 2,
                             area.right() - frame.width() + 1))
    y = max(area.top(), min(center.y() - frame.height() // 2,
                            area.bottom() - frame.height() + 1))
    dialog.move(x, y)


class _DialogLayoutFilter(QObject):
    def _after_show(self, dialog):
        if dialog.isVisible():
            fit_dialog(dialog)
            place_dialog(dialog)

    def eventFilter(self, obj, event):
        if isinstance(obj, QDialog) and event.type() == QEvent.Type.Show:
            fit_dialog(obj)
            place_dialog(obj)
            if not QApplication.platformName().startswith('wayland'):
                QTimer.singleShot(0, obj, lambda: self._after_show(obj))
        return super().eventFilter(obj, event)


def install_dialog_layout(app):
    if getattr(app, '_dialog_layout_filter', None) is None:
        app._dialog_layout_filter = _DialogLayoutFilter(app)
        app.installEventFilter(app._dialog_layout_filter)
