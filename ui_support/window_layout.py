"""Screen-aware window sizing and native dialog ownership for both Qt entry points."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from qtcompat.QtCore import QEvent, QObject, QRect, QSize, Qt, QTimer
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


def _vmware_virtual_mouse(input_root=Path('/sys/class/input')):
    """Identify the virtual mouse drivers exposed by the current Linux guest."""
    for path in input_root.glob('event*/device/name'):
        try:
            name = path.read_text().strip()
        except OSError:
            continue
        if ('VMware VMMouse' in name or 'VMware Virtual USB Mouse' in name):
            return True
    return False


def configure_native_file_dialogs():
    """Configure native pickers and Linux pointer input before QApplication."""
    if (sys.platform.startswith('linux')
            and os.environ.get('QT_QPA_PLATFORM', '') != 'offscreen'):
        gnome = ('GNOME' in os.environ.get('XDG_CURRENT_DESKTOP', '').upper()
                 and os.environ.get('DISPLAY'))
        # Older GNOME portals ignore current_folder for OpenFile. The GTK
        # helper sets that folder directly for both file and directory pickers.
        if gnome:
            os.environ.setdefault('QT_QPA_PLATFORMTHEME', 'gtk3')
        elif os.environ.get('WAYLAND_DISPLAY'):
            os.environ.setdefault('QT_QPA_PLATFORMTHEME', 'xdgdesktopportal')
        # Older GNOME exports xdg-foreign v1 only; Qt's Wayland portal helper
        # sends an empty handle there. XWayland provides a usable X11 owner.
        if gnome and os.environ.get('WAYLAND_DISPLAY'):
            os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
        if (os.environ.get('DISPLAY')
                and os.environ.get('QT_QPA_PLATFORM', '').split(':')[0] in ('', 'xcb')
                and _vmware_virtual_mouse()):
            # VMware switches absolute/relative XI2 devices while moving and
            # scrolling. Qt's scroll-baseline reset can swallow the first tick.
            # Core X11 wheel buttons avoid this on both X11 and XWayland.
            os.environ.setdefault('QT_XCB_NO_XI2', '1')


def available_geometry(widget=None):
    owner = widget.parentWidget() if widget is not None else None
    screen = (owner.window().screen() if owner is not None else
              widget.screen() if widget is not None else None)
    screen = screen or QApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QRect(0, 0, 1024, 768)


def initial_window_size(area, pixel_ratio=1.0):
    """Convert the physical 1080p cap to Qt coordinates while retaining desktop bounds."""
    return QSize(min(round(1920 / pixel_ratio), area.width()),
                 min(round(1080 / pixel_ratio), area.height()))


@lru_cache(maxsize=1)
def _gtk3_window_api():
    """Access the already-required GTK native picker without adding a binding."""
    import ctypes as c

    class Link(c.Structure):
        pass

    Link._fields_ = [('data', c.c_void_p), ('next', c.POINTER(Link)), ('prev', c.POINTER(Link))]

    class Rect(c.Structure):
        _fields_ = [(key, c.c_int) for key in ('x', 'y', 'width', 'height')]

    try:
        gtk = c.CDLL('libgtk-3.so.0')
        gdk = c.CDLL('libgdk-3.so.0')
        glib = c.CDLL('libglib-2.0.so.0')
        obj = c.CDLL('libgobject-2.0.so.0')
        signatures = [
            (gtk, 'gtk_window_list_toplevels', [], c.POINTER(Link)),
            (gtk, 'gtk_file_chooser_get_type', [], c.c_size_t),
            (gtk, 'gtk_widget_get_visible', [c.c_void_p], c.c_int),
            (gtk, 'gtk_widget_get_window', [c.c_void_p], c.c_void_p),
            (gtk, 'gtk_window_get_title', [c.c_void_p], c.c_char_p),
            (gtk, 'gtk_window_get_position', [c.c_void_p, c.POINTER(c.c_int),
                                             c.POINTER(c.c_int)], None),
            (gtk, 'gtk_window_move', [c.c_void_p, c.c_int, c.c_int], None),
            (gtk, 'gtk_window_set_keep_above', [c.c_void_p, c.c_int], None),
            (gdk, 'gdk_window_get_display', [c.c_void_p], c.c_void_p),
            (gdk, 'gdk_x11_window_foreign_new_for_display', [c.c_void_p, c.c_ulong], c.c_void_p),
            (gdk, 'gdk_window_get_frame_extents', [c.c_void_p, c.POINTER(Rect)], None),
            (gdk, 'gdk_display_get_monitor_at_window', [c.c_void_p, c.c_void_p], c.c_void_p),
            (gdk, 'gdk_monitor_get_workarea', [c.c_void_p, c.POINTER(Rect)], None),
            (glib, 'g_list_free', [c.c_void_p], None),
            (obj, 'g_type_check_instance_is_a', [c.c_void_p, c.c_size_t], c.c_int),
            (obj, 'g_object_unref', [c.c_void_p], None),
        ]
        for library, name, args, result in signatures:
            function = getattr(library, name)
            function.argtypes, function.restype = args, result
    except (OSError, AttributeError):
        return None
    return c, gtk, gdk, glib, obj, Rect


def _place_gtk_file_dialog(dialog):
    """Position the actual GTK window, leaving Qt's hidden proxy untouched."""
    if (not sys.platform.startswith('linux') or QApplication.platformName() != 'xcb'
            or os.environ.get('QT_QPA_PLATFORMTHEME') != 'gtk3'):
        return
    owner = dialog.parentWidget()
    if owner is None:
        return
    api = _gtk3_window_api()
    if api is None:
        return
    c, gtk, gdk, glib, obj, Rect = api
    windows = gtk.gtk_window_list_toplevels()
    item = windows
    try:
        while item:
            widget = item.contents.data
            item = item.contents.next
            if (not obj.g_type_check_instance_is_a(widget, gtk.gtk_file_chooser_get_type())
                    or not gtk.gtk_widget_get_visible(widget)
                    or gtk.gtk_window_get_title(widget) != dialog.windowTitle().encode('utf-8')):
                continue
            window = gtk.gtk_widget_get_window(widget)
            if not window:
                continue
            gtk.gtk_window_set_keep_above(widget, True)
            display = gdk.gdk_window_get_display(window)
            parent = gdk.gdk_x11_window_foreign_new_for_display(
                display, int(owner.window().winId()),
            )
            if not parent:
                continue
            try:
                frame, parent_frame, workarea = Rect(), Rect(), Rect()
                gdk.gdk_window_get_frame_extents(window, c.byref(frame))
                gdk.gdk_window_get_frame_extents(parent, c.byref(parent_frame))
                monitor = gdk.gdk_display_get_monitor_at_window(display, parent)
                gdk.gdk_monitor_get_workarea(monitor, c.byref(workarea))
                x = parent_frame.x + (parent_frame.width - frame.width) // 2
                y = parent_frame.y + (parent_frame.height - frame.height) // 2
                x = max(workarea.x, min(x, workarea.x + workarea.width - frame.width))
                y = max(workarea.y, min(y, workarea.y + workarea.height - frame.height))
                current_x, current_y = c.c_int(), c.c_int()
                gtk.gtk_window_get_position(widget, c.byref(current_x), c.byref(current_y))
                gtk.gtk_window_move(widget, current_x.value + x - frame.x,
                                    current_y.value + y - frame.y)
            finally:
                obj.g_object_unref(parent)
    finally:
        glib.g_list_free(windows)


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
    if isinstance(dialog, QFileDialog) and not dialog.testOption(
        QFileDialog.Option.DontUseNativeDialog
    ):
        _place_gtk_file_dialog(dialog)
        return
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
        if isinstance(obj, QDialog) and event.type() == QEvent.Type.Polish:
            obj.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            obj.setWindowModality(Qt.WindowModality.ApplicationModal)
        if isinstance(obj, QDialog) and event.type() == QEvent.Type.Show:
            fit_dialog(obj)
            place_dialog(obj)
            handle = obj.windowHandle()
            if handle is not None and not handle.flags() & Qt.WindowType.WindowStaysOnTopHint:
                # QMessageBox can reset QWidget flags after its early polish.
                # Updating the native window avoids hiding/remapping the dialog.
                handle.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            if not QApplication.platformName().startswith('wayland'):
                QTimer.singleShot(0, obj, lambda: self._after_show(obj))
        return super().eventFilter(obj, event)


def install_dialog_layout(app):
    if getattr(app, '_dialog_layout_filter', None) is None:
        app._dialog_layout_filter = _DialogLayoutFilter(app)
        app.installEventFilter(app._dialog_layout_filter)
