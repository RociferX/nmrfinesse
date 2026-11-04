"""Select project data by experiment and copy existing UCSF results."""

from __future__ import annotations

import threading
from pathlib import Path

from qtcompat.QtCore import Qt
from qtcompat.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from gui.dialogs import InfoDialog
from gui.file_dialogs import choose_directory
from gui.processing import ProcessingController
from gui.settings import spectrum_directory_path
from qtcompat import Signal
from ui_support.i18n import tr
from ui_support.title_layout import spectrum_tooltip


class UcsfExportDialog(QDialog):
    """Keep selection and asynchronous copying in one modal window."""

    _finished = Signal(object, object)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Export UCSF files"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(760, 560)
        self.controller = ProcessingController(manager)
        self._busy = False
        self._finished.connect(self._on_finished)
        layout = QVBoxLayout(self)
        description = QLabel(tr(
            "Select data under each experiment, then export its UCSF files. "
            "Missing UCSF files are unavailable; project originals are kept."
        ))
        description.setWordWrap(True)
        layout.addWidget(description)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Experiment / data"), tr("UCSF file")])
        self.tree.setColumnWidth(0, 380)
        groups = {}
        for entry in self.controller.ucsf_export_entries():
            group = groups.get(entry["exp_id"])
            if group is None:
                group = QTreeWidgetItem(self.tree, [entry["experiment"]])
                group.setFlags(group.flags() | Qt.ItemFlag.ItemIsAutoTristate
                               | Qt.ItemFlag.ItemIsUserCheckable)
                group.setCheckState(0, Qt.CheckState.Unchecked)
                groups[entry["exp_id"]] = group
            item = QTreeWidgetItem(group, [entry["data"],
                Path(entry["source"]).name if entry["source"] else tr("No UCSF file")])
            if entry["source"]:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setData(0, Qt.ItemDataRole.UserRole, entry)
                tooltip = spectrum_tooltip(Path(entry["source"]), manager)
                item.setToolTip(0, tooltip)
                item.setToolTip(1, tooltip)
            else:
                item.setDisabled(True)
        for group in groups.values():
            if not any(group.child(i).data(0, Qt.ItemDataRole.UserRole)
                       for i in range(group.childCount())):
                group.setDisabled(True)
        self.tree.expandAll()
        self.tree.itemChanged.connect(self._update_export_button)
        layout.addWidget(self.tree, 1)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        self.export_button = QPushButton(tr("Export"))
        self.export_button.setObjectName("PrimaryAction")
        self.buttons.addButton(self.export_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.export_button.clicked.connect(self._export)
        layout.addWidget(self.buttons)
        self._update_export_button()

    def selected_entries(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                entry = item.data(0, Qt.ItemDataRole.UserRole)
                if entry and item.checkState(0) == Qt.CheckState.Checked:
                    selected.append(entry)
        return selected

    def _update_export_button(self, *_args):
        self.export_button.setEnabled(not self._busy and bool(self.selected_entries()))

    def _export(self):
        entries = self.selected_entries()
        if self._busy or not entries:
            return
        folder = choose_directory(self, tr("Select the spectra export folder"),
                                  str(spectrum_directory_path()))
        if not folder:
            return
        self._busy = True
        self.tree.setEnabled(False)
        self.buttons.setEnabled(False)
        self.status_label.setText(tr("Exporting UCSF files…"))

        def copy_files():
            try:
                result = self.controller.transfer_ucsf_files(entries, folder)
                self._finished.emit(result, None)
            except Exception as exc:
                self._finished.emit(None, str(exc))

        threading.Thread(target=copy_files, daemon=True).start()

    def _on_finished(self, result, error):
        self._busy = False
        self.tree.setEnabled(True)
        self.buttons.setEnabled(True)
        self._update_export_button()
        if error:
            self.status_label.setText(tr("UCSF export failed: {p0}", p0=error))
            return
        text = tr("Exported {p0} UCSF file(s); failed: {p1}",
                  p0=len(result["copied"]), p1=len(result["errors"]))
        self.status_label.setText(text)
        InfoDialog.show_info(self, tr("Export UCSF files"),
                             "\n".join([text, *result["copied"], *result["errors"]]))

    def reject(self):
        if not self._busy:
            super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
        else:
            super().closeEvent(event)
