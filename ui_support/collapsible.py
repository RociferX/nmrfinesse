"""Compact, accessible collapsible sections shared by viewer panels."""

from __future__ import annotations

from qtcompat.QtCore import QEvent, Qt, QTimer
from qtcompat.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qtcompat import Signal
from ui_support.i18n import tr


class _SectionHeader(QPushButton):
    """A checkable full-row button whose title wraps when space is limited."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ViewerSectionHeader")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._arrow = QLabel("▾", self)
        self._arrow.setObjectName("ViewerSectionArrow")
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._title = QLabel(title, self)
        self._title.setObjectName("ViewerSectionTitle")
        self._title.setWordWrap(True)
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._state = QLabel(tr("Expanded"), self)
        self._state.setObjectName("ViewerSectionState")
        self._state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._state.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self._state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(7)
        layout.addWidget(self._arrow, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._title, 1)
        layout.addWidget(self._state, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_expanded(self, expanded: bool) -> None:
        self.setChecked(expanded)
        self._arrow.setText("▾" if expanded else "▸")
        self._state.setText(tr("Expanded") if expanded else tr("Collapsed"))
        self.setAccessibleName(self._title.text())
        self.setAccessibleDescription(self._state.text())
        self.updateGeometry()

    def set_title(self, title: str) -> None:
        self._title.setText(title)
        self.setAccessibleName(title)
        self.updateGeometry()

    def sizeHint(self):  # noqa: N802 - Qt API name
        return self.layout().sizeHint()

    def minimumSizeHint(self):  # noqa: N802 - Qt API name
        return self.layout().minimumSize()

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API name
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API name
        return self.layout().heightForWidth(max(1, width))


class CollapsibleSection(QFrame):
    """A titled section with a persistent clickable header and hideable body.

    ``body`` is an empty QWidget for the caller to populate with its own layout.
    The whole body is hidden when collapsed, preserving child visibility state.
    """

    toggled = Signal(bool)
    geometry_changed = Signal()

    def __init__(
        self, title: str, parent: QWidget | None = None, *, expanded: bool = True
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._geometry_pending = False
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = _SectionHeader(title, self)
        self.body = QWidget(self)
        self.body.setObjectName("ViewerSectionBody")
        self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.header)
        layout.addWidget(self.body)

        self.header.clicked.connect(self.set_expanded)
        self.body.installEventFilter(self)
        self.header.installEventFilter(self)
        self.set_expanded(expanded)

    def set_title(self, title: str) -> None:
        self.header.set_title(title)
        self._schedule_geometry_changed()

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        changed = expanded != self._expanded
        self._expanded = expanded
        self.header.set_expanded(expanded)
        self.body.setVisible(expanded)
        if expanded:
            self.setMaximumHeight(16_777_215)
        else:
            self.setMaximumHeight(self._collapsed_height())
        self.updateGeometry()
        if changed:
            self.toggled.emit(expanded)
        self._schedule_geometry_changed()

    def is_expanded(self) -> bool:
        return self._expanded

    def natural_height(self) -> int:
        if not self.is_expanded():
            return self._collapsed_height()
        width = max(1, self.contentsRect().width())
        header_height = self.header.heightForWidth(width)
        body_height = (
            self.body.heightForWidth(width)
            if self.body.hasHeightForWidth()
            else self.body.sizeHint().height()
        )
        body_height = min(body_height, self.body.maximumHeight())
        margins = self.layout().contentsMargins()
        return (
            margins.top()
            + header_height
            + self.layout().spacing()
            + body_height
            + margins.bottom()
        )

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API name
        if event.type() in (
            QEvent.Type.LayoutRequest,
            QEvent.Type.FontChange,
            QEvent.Type.Resize,
        ):
            self._schedule_geometry_changed()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        if not hasattr(self, "_expanded"):
            return
        if not self.is_expanded():
            self.setMaximumHeight(self._collapsed_height())
        self._schedule_geometry_changed()

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().changeEvent(event)
        if not hasattr(self, "_expanded"):
            return
        if event.type() == QEvent.Type.FontChange:
            if not self.is_expanded():
                self.setMaximumHeight(self._collapsed_height())
            self._schedule_geometry_changed()

    def _collapsed_height(self) -> int:
        width = max(1, self.contentsRect().width())
        return max(self.header.minimumSizeHint().height(), self.header.heightForWidth(width))

    def _schedule_geometry_changed(self) -> None:
        if not hasattr(self, "_geometry_pending"):
            return
        if self._geometry_pending:
            return
        self._geometry_pending = True
        QTimer.singleShot(0, self, self._emit_geometry_changed)

    def _emit_geometry_changed(self) -> None:
        self._geometry_pending = False
        self.geometry_changed.emit()


__all__ = ["CollapsibleSection"]
