"""Editable, explained carrier choices for the manual conversion script."""
from __future__ import annotations

import math

from qtcompat.QtCore import QEvent, Qt, QTimer
from qtcompat.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui_support.i18n import tr


class FidCarrierPanel(QWidget):
    def __init__(self, editor, choices, read_values, replace_value):
        super().__init__()
        self.editor = editor
        self.read_values = read_values
        self.replace_value = replace_value
        self.combos = {}
        self.descriptions = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout = QGridLayout()
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setHorizontalSpacing(12)
        self._row_layout.setVerticalSpacing(6)
        layout.addLayout(self._row_layout)
        self._carrier_boxes = []
        self._carrier_columns = 0
        self.description = QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        values = read_values(editor.toPlainText())
        self.last_values = values
        metadata = {row['key']: row for row in choices}
        for key, current in values.items():
            row = metadata.get(key, {})
            box = QWidget()
            column = QVBoxLayout(box)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.setMinimumContentsLength(8)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            keep = tr("Current script value. Keep it unless you intentionally want a different "
                      "reference; opening this list does not change the script.")
            options = [{"value": float(current), "label": tr("Current script"),
                        "description": keep},
                       *row.get('options', [])]
            for option in options:
                combo.addItem(f"{option['value']:.6f} — {option['label']}", option)
                combo.setItemData(combo.count() - 1, option['description'],
                                  Qt.ItemDataRole.ToolTipRole)
            combo.setEditText(current)
            combo.setToolTip(tr("CAR in ppm: type a value and press Enter, "
                                "or choose an explained reference below."))
            self.combos[key] = combo
            combo.lineEdit().installEventFilter(self)
            combo.installEventFilter(self)
            self.descriptions[key] = keep
            label = f"{key} (ppm)"
            if row:
                label += f" · {row['axis']} {row['nucleus']}"
            column.addWidget(QLabel(label))
            column.addWidget(combo)
            self._carrier_boxes.append(box)
            combo.activated.connect(lambda index, k=key: self._choose(k, index))
            combo.lineEdit().returnPressed.connect(lambda k=key: self._typed(k))
        editor.textChanged.connect(self._sync_from_script)
        if self.combos:
            self._show_description(next(iter(self.combos)))
        self.setVisible(bool(self.combos))
        self._reflow_carriers()

    def _reflow_carriers(self):
        if not self._carrier_boxes:
            return
        gap = self._row_layout.horizontalSpacing()
        min_width = max(box.minimumSizeHint().width() for box in self._carrier_boxes)
        columns = max(1, min(len(self._carrier_boxes), (self.width() + gap) // (min_width + gap)))
        columns = int(columns)
        if columns == self._carrier_columns:
            return
        self._carrier_columns = columns
        while self._row_layout.count():
            item = self._row_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._row_layout.removeWidget(widget)
        for index, box in enumerate(self._carrier_boxes):
            self._row_layout.addWidget(box, index // columns, index % columns)
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_carriers()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange and hasattr(self, '_carrier_boxes'):
            QTimer.singleShot(0, self, self._reflow_carriers)

    def _show_description(self, key, text=None):
        if text is not None:
            self.descriptions[key] = text
        self.description.setText(f"{key}: {self.descriptions[key]}")

    def eventFilter(self, obj, event):
        for key, combo in self.combos.items():
            if obj is not combo.lineEdit() and obj is not combo:
                continue
            if event.type() == QEvent.Type.FocusIn:
                self._show_description(key)
            if (event.type() == QEvent.Type.KeyPress
                    and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
                self._typed(key)
                return True
            cancel = event.type() == QEvent.Type.FocusOut or (
                event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape
            )
            if cancel:
                current = self.read_values(self.editor.toPlainText()).get(key)
                if current is not None:
                    combo.setEditText(current)
                return event.type() == QEvent.Type.KeyPress
        return super().eventFilter(obj, event)

    def _choose(self, key, index):
        option = self.combos[key].itemData(index)
        value = f"{option['value']:.6f}"
        self.combos[key].setEditText(value)
        self._apply(key, value, option['description'])

    def _typed(self, key):
        text = self.combos[key].currentText().strip()
        # A popup label is not a user-entered number; activation handles it.
        if ' — ' in text:
            return
        try:
            if not math.isfinite(float(text)):
                raise ValueError
        except ValueError:
            self._show_description(key, tr("Enter a finite CAR value in ppm. "
                                           "The script has not been changed."))
            return
        current = self.read_values(self.editor.toPlainText()).get(key)
        if current is not None and float(current) == float(text):
            return
        self._apply(key, text, tr("Custom CAR in ppm, explicitly entered by the user."))

    def _apply(self, key, value, description):
        try:
            content = self.replace_value(self.editor.toPlainText(), key, value)
        except ValueError:
            self._show_description(key, tr("This CAR parameter is absent or invalid in the "
                                           "script. Restore it in the editor before "
                                           "changing its value here."))
            return
        if content != self.editor.toPlainText():
            cursor = self.editor.textCursor()
            cursor.beginEditBlock()
            cursor.select(cursor.SelectionType.Document)
            cursor.insertText(content)
            cursor.endEditBlock()
        self._show_description(key, description)

    def _sync_from_script(self):
        values = self.read_values(self.editor.toPlainText())
        for key, combo in self.combos.items():
            combo.setEnabled(key in values)
            if key in values and not combo.lineEdit().hasFocus():
                combo.setEditText(values[key])
                if values[key] != self.last_values.get(key):
                    self._show_description(key, tr("Current value read from the script editor. "
                                                   "Choose a reference to see its explanation."))
        self.last_values = values
