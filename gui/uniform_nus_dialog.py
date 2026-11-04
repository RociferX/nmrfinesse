"""Inspect uniform raw FIDs and select complete increments for NUS export."""

from __future__ import annotations

import threading
from pathlib import Path

from qtcompat.QtCore import Qt
from qtcompat.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from gui.file_dialogs import choose_directory
from qtcompat import Signal
from ui_support.i18n import tr
from workflow.uniform_nus import export_nus, inspect_uniform


class UniformNusDialog(QDialog):
    """Keep acquisition selection, diagnosis and non-destructive export together."""

    finished_work = Signal(object, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Remove abnormal FIDs and export NUS"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setProperty("wideDialog", True)
        self.resize(1000, 700)
        self._busy = False
        self._report = None
        self._source = None
        self.finished_work.connect(self._finished)
        layout = QVBoxLayout(self)
        note = QLabel(
            tr(
                "Select uniform Bruker 2D/3D raw data. "
                "Checked increments will be removed as complete "
                "phase groups. Coordinates are zero-based, in acqu2s / acqu3s order. "
                "Original data is kept; no processed spectra are copied."
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)
        self.browse = QPushButton(tr("Browse…"))
        self.browse.clicked.connect(self._choose_source)
        self.scan_button = QPushButton(tr("Detect FIDs"))
        self.scan_button.clicked.connect(self._scan)
        row.addWidget(self.source_edit, 1)
        row.addWidget(self.browse)
        row.addWidget(self.scan_button)
        layout.addLayout(row)
        mode = QHBoxLayout()
        self.automatic = QRadioButton(tr("Automatically select abnormal increments"))
        self.manual = QRadioButton(tr("Manually select increments"))
        self.automatic.setChecked(True)
        self.automatic.toggled.connect(self._mode_changed)
        mode.addWidget(self.automatic)
        mode.addWidget(self.manual)
        layout.addLayout(mode)
        policy = QLabel(
            tr(
                "Automatic selection: nonfinite data, entirely zero increments and isolated spikes "
                "(existing 12-MAD detector). Zero phase components and "
                "high energy are advisory only. "
                "Review findings before export."
            )
        )
        policy.setWordWrap(True)
        layout.addWidget(policy)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [tr("Remove / coordinate"), tr("Raw FID rows (zero-based)"), tr("Findings")]
        )
        self.tree.setColumnWidth(0, 240)
        self.tree.setColumnWidth(1, 260)
        self.tree.itemChanged.connect(self._selection_changed)
        layout.addWidget(self.tree, 1)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(tr("Output directory")))
        self.output_edit = QLineEdit()
        self.output_browse = QPushButton(tr("Browse…"))
        self.output_browse.clicked.connect(self._choose_output)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(self.output_browse)
        layout.addLayout(out_row)
        self.status = QLabel(tr("Choose a raw dataset to begin."))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Close"))
        self.buttons.rejected.connect(self.reject)
        self.export_button = QPushButton(tr("Export NUS directory"))
        self.buttons.addButton(self.export_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.export_button.clicked.connect(self._export)
        layout.addWidget(self.buttons)
        self.export_button.setEnabled(False)

    def _choose_source(self):
        folder = choose_directory(
            self, tr("Select uniform Bruker raw data"), self.source_edit.text() or str(Path.home())
        )
        if not folder:
            return
        self._source = Path(folder)
        self.source_edit.setText(folder)
        self.output_edit.setText(str(self._source.with_name(self._source.name + "_nus")))
        self._report = None
        self.tree.clear()
        self.export_button.setEnabled(False)
        self._scan()

    def _choose_output(self):
        parent = choose_directory(
            self,
            tr("Select output parent directory"),
            str(self._source.parent if self._source else Path.home()),
        )
        if parent:
            self.output_edit.setText(
                str(Path(parent) / (self._source.name + "_nus" if self._source else "repaired_nus"))
            )

    def _work(self, kind, call):
        if self._busy:
            return
        self._busy = True
        for widget in (
            self.browse,
            self.scan_button,
            self.tree,
            self.automatic,
            self.manual,
            self.output_edit,
            self.output_browse,
            self.buttons,
        ):
            widget.setEnabled(False)
        self.status.setText(
            tr("Inspecting raw FIDs…") if kind == "scan" else tr("Exporting NUS data…")
        )

        def run():
            try:
                self.finished_work.emit(call(), None, kind)
            except Exception as exc:
                self.finished_work.emit(None, str(exc), kind)

        threading.Thread(target=run, daemon=True).start()

    def _scan(self):
        if self._source:
            source = self._source
            self._report = None
            self.tree.clear()
            self._work("scan", lambda: inspect_uniform(source))

    def selected_coordinates(self):
        return [
            tuple(self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)["coordinate"])
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        ]

    def _mode_changed(self, *_):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            point = item.data(0, Qt.ItemDataRole.UserRole)
            flags = item.flags()
            item.setFlags(
                flags & ~Qt.ItemFlag.ItemIsUserCheckable
                if self.automatic.isChecked()
                else flags | Qt.ItemFlag.ItemIsUserCheckable
            )
            if self.automatic.isChecked():
                item.setCheckState(
                    0, Qt.CheckState.Checked if point["auto_remove"] else Qt.CheckState.Unchecked
                )
        self.tree.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self, *_):
        count = len(self.selected_coordinates())
        total = self.tree.topLevelItemCount()
        self.export_button.setEnabled(not self._busy and 0 < count <= total - 2)
        if self._report and not self._busy:
            self.status.setText(
                tr(
                    "Delete {p0} of {p1} increments; retain {p2:.2f}%.",
                    p0=count,
                    p1=total,
                    p2=100 * (total - count) / total,
                )
            )

    def _export(self):
        if self._busy or not self._report:
            return
        source = self._source
        text = self.output_edit.text().strip()
        if not text:
            self.status.setText(tr("Choose an output directory."))
            return
        destination = Path(text).expanduser()
        coordinates = self.selected_coordinates()
        expected = self._report["source"]
        automatic = self.automatic.isChecked()
        self._work(
            "export",
            lambda: export_nus(
                source,
                destination,
                automatic=automatic,
                excluded=None if automatic else coordinates,
                expected_source=expected,
            ),
        )

    def _finished(self, result, error, kind):
        self._busy = False
        for widget in (
            self.browse,
            self.scan_button,
            self.tree,
            self.automatic,
            self.manual,
            self.output_edit,
            self.output_browse,
            self.buttons,
        ):
            widget.setEnabled(True)
        if error:
            self.status.setText(tr("Operation failed: {p0}", p0=error))
            self.export_button.setEnabled(bool(self._report and self.selected_coordinates()))
            return
        if kind == "scan":
            self._report = result
            labels = {
                "nonfinite": tr("NaN/Inf"),
                "all_zero_increment": tr("All-zero increment"),
                "isolated_spike": tr("Isolated spike"),
                "zero_phase_component": tr("Zero phase component (review)"),
                "high_energy_over_100x_median": tr("Energy >100× median (review)"),
            }
            self.tree.blockSignals(True)
            for point in result["points"]:
                item = QTreeWidgetItem(
                    self.tree,
                    [
                        ", ".join(map(str, point["coordinate"])),
                        ", ".join(map(str, point["raw_rows"])),
                        "; ".join(labels[k] for k in point["reasons"] + point["advisory"])
                        or tr("No issue detected"),
                    ],
                )
                item.setData(0, Qt.ItemDataRole.UserRole, point)
                for column in range(3):
                    item.setToolTip(column, item.text(column))
                item.setCheckState(0, Qt.CheckState.Unchecked)
            self.tree.resizeColumnToContents(0)
            self.tree.resizeColumnToContents(1)
            self.tree.blockSignals(False)
            self._mode_changed()
        else:
            self._selection_changed()
            self.status.setText(
                tr(
                    "Export complete: {p0} increments retained. {p1}",
                    p0=result["sample_count"],
                    p1=result["destination"],
                )
            )

    def reject(self):
        if not self._busy:
            super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
        else:
            super().closeEvent(event)
