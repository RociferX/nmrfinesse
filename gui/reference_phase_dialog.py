"""Reference defaults and per-data range/phase tables."""

from __future__ import annotations

import math

from qtcompat.QtCore import QEvent, Qt, QTimer
from qtcompat.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui_support.i18n import tr


class WrappedHintLabel(QLabel):
    """Measure wrapped text at its actual narrow-card width."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setMinimumWidth(0)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._pending = False
        self.queue_height()

    def queue_height(self):
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self, self._fit)

    def _fit(self):
        self._pending = False
        # QLabel includes its explicit minimum height when measuring wrapped text.
        self.setMinimumHeight(0)
        height = self.heightForWidth(max(1, self.width())) if self.text() else 0
        self.setFixedHeight(height)

    def setText(self, text):
        super().setText(text)
        self.queue_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.queue_height()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.queue_height()


class ReferenceOptionsDialog(QDialog):
    """One row per active data; unchanged reference values are not overrides."""

    def __init__(self, parent, rows, defaults, current, kind):
        super().__init__(parent)
        self.kind = kind
        self.rows = rows
        self.defaults = defaults
        self.current = current
        self._changing = False
        phase_help = tr(
            "Unchecked by default: use the phases in the table, initially copied from the "
            "reference. "
            "Checked: after FID conversion, automatically search p0/p1 for each dimension of the "
            "current data and apply the results to this run. Other processing settings follow the "
            "reference script and your selected direct-axis range."
        )
        self.setWindowTitle(tr("direct dimension range") if kind == "range" else tr("Phase"))
        self.resize(720 if kind == "range" else 1050, min(650, 220 + len(rows) * 32))
        layout = QVBoxLayout(self)
        self.auto_all = QCheckBox(
            tr("Automatically optimise phases for all data after FID conversion")
        )
        self.auto_all.setChecked(False)
        self.auto_all.setToolTip(phase_help)
        self.auto_all.setVisible(kind == "phases" and len(rows) > 1)
        layout.addWidget(self.auto_all)
        self.axes = sorted(defaults.get("phases", {}))
        headers = (
            [tr("data"), "EXT -x1 (ppm)", "EXT -xn (ppm)"]
            if kind == "range"
            else [
                tr("data"),
                *[f"{axis} p{order} (°)" for axis in self.axes for order in (0, 1)],
                tr("Automatic phase"),
            ]
        )
        self.table = QTableWidget(len(rows), len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        for row, (key, title) in enumerate(rows):
            name = QTableWidgetItem(title)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name)
            options = current.get(key, {})
            values = (
                options.get("range", defaults["range"])
                if kind == "range"
                else [
                    value
                    for axis in self.axes
                    for value in options.get("phases", defaults["phases"])[axis]
                ]
            )
            for column, value in enumerate(values, 1):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
            if kind == "phases":
                auto = QTableWidgetItem()
                auto.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                auto.setToolTip(phase_help)
                auto.setCheckState(
                    Qt.CheckState.Checked if options.get("auto_phase") else Qt.CheckState.Unchecked
                )
                self.table.setItem(row, len(headers) - 1, auto)
        self.table.resizeRowsToContents()
        self.note = WrappedHintLabel(
            tr("Edit range values directly. Unchanged values use the reference.")
            if kind == "range"
            else phase_help
        )
        layout.addWidget(self.note)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.table.itemChanged.connect(self._changed)
        self.auto_all.toggled.connect(self._set_all)
        self._changed()

    def _set_all(self, checked):
        if self._changing or self.kind != "phases":
            return
        self._changing = True
        for row in range(self.table.rowCount()):
            self.table.item(row, self.table.columnCount() - 1).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
        self._changing = False
        self._changed()

    def _changed(self, *args):
        if self._changing or self.kind != "phases":
            return
        self._changing = True
        states = []
        for row in range(self.table.rowCount()):
            auto = (
                self.table.item(row, self.table.columnCount() - 1).checkState()
                == Qt.CheckState.Checked
            )
            states.append(auto)
            for column in range(1, self.table.columnCount() - 1):
                item = self.table.item(row, column)
                flags = item.flags()
                item.setFlags(
                    flags & ~Qt.ItemFlag.ItemIsEditable
                    if auto
                    else flags | Qt.ItemFlag.ItemIsEditable
                )
        self.auto_all.setChecked(bool(states) and all(states))
        self._changing = False

    def values(self):
        result = {}
        for row, (key, _) in enumerate(self.rows):
            options = dict(self.current.get(key, {}))
            count = 2 if self.kind == "range" else len(self.axes) * 2
            values = tuple(
                float(self.table.item(row, column).text()) for column in range(1, count + 1)
            )
            if not all(math.isfinite(value) for value in values):
                raise ValueError()
            if self.kind == "range":
                if values[0] == values[1]:
                    raise ValueError()
                default = tuple(self.defaults["range"])
                if values == default:
                    options.pop("range", None)
                else:
                    options["range"] = values
            else:
                phases = {axis: values[2 * i : 2 * i + 2] for i, axis in enumerate(self.axes)}
                if phases == self.defaults["phases"]:
                    options.pop("phases", None)
                else:
                    options["phases"] = phases
                options.pop("phase", None)
                options["auto_phase"] = (
                    self.table.item(row, count + 1).checkState() == Qt.CheckState.Checked
                )
            result[key] = options
        return result

    def _accept(self):
        try:
            self.values()
        except ValueError:
            self.note.setText(tr("Enter finite numbers and two different range endpoints"))
            self.note.queue_height()
            return
        self.accept()
