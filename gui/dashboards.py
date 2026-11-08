"""Dashboard panel: project/Experiment overview(GUI_ARCHITECTURE_VISION §11-12). -
ProjectDashboard: project statistics (experiment/sample data/Processing completion) + recent
runs + new experiment form; - ExperimentDashboard: sample data list (data status of each sample)
+ import sample data form. Data source: core.project(ProjectManager); running history comes from
workflow_runs.
"""

from __future__ import annotations

from pathlib import Path

from qtcompat.QtCore import QEvent, QSignalBlocker, Qt, QTimer
from qtcompat.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.project import ProjectManager
from gui.dialogs import InfoDialog
from gui.file_dialogs import choose_directory
from qtcompat import Signal
from ui_support.i18n import tr


def _active_data_of(exp) -> list:
    'Data entries that were not soft deleted under the experiment.'
    return [d for d in (getattr(exp, "data", None) or []) if not getattr(d, "trashed", False)]


def _data_count(project) -> int:
    return sum(
        len(_active_data_of(exp))
        for exp in project.experiments
        if not getattr(exp, "trashed", False)
    )


class ProjectDashboard(QWidget):
    'Project overview: statistics + processing completion + recent runs + new experiments.'

    create_experiment_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager: ProjectManager | None = None
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.page_content = QWidget()
        root_layout.addWidget(self.scroll_area)
        layout = QVBoxLayout(self.page_content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self.scroll_area.setWidget(self.page_content)

        title = QLabel(tr("project"))
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.context_label = QLabel("")
        self.context_label.setWordWrap(True)
        self.context_label.setObjectName("PanelSubtitle")
        layout.addWidget(self.context_label)

        self.stats_label = QLabel("")
        self.stats_label.setObjectName("MutedText")
        layout.addWidget(self.stats_label)

        recent_title = QLabel(tr("recently run"))
        recent_title.setObjectName("SectionTitle")
        layout.addWidget(recent_title)
        self.runs_table = QTableWidget(0, 4)
        self.runs_table.setHorizontalHeaderLabels(
            [tr("run"), tr("process"), tr("state"), tr("time")]
        )
        self.runs_table.horizontalHeader().setStretchLastSection(True)
        self.runs_table.setMinimumHeight(0)
        layout.addWidget(self.runs_table)
        layout.addSpacing(2)

        form = QHBoxLayout()
        form.setSpacing(6)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(tr("experiment title (can be left blank)"))
        self.title_edit.returnPressed.connect(self._on_create)
        form.addWidget(self.title_edit, 1)
        self.create_button = QPushButton(tr("New experiment"))
        self.create_button.setObjectName("PrimaryAction")
        self.create_button.clicked.connect(self._on_create)
        form.addWidget(self.create_button)
        layout.insertLayout(layout.indexOf(self.context_label) + 1, form)
        layout.addStretch(1)

    def set_context(self, manager: ProjectManager) -> None:
        self.manager = manager
        self.refresh()

    def resizeEvent(self, event) -> None:
        """Keep the compact project overview scrollable when its natural height exceeds the view."""
        super().resizeEvent(event)
        content_layout = self.page_content.layout()
        if content_layout is not None:
            content_layout.activate()
            self.page_content.setMinimumHeight(content_layout.sizeHint().height())

    def refresh(self) -> None:
        if self.manager is None or self.manager.project is None:
            return
        project = self.manager.project
        self.context_label.setText(project.name)
        exp_count = len(project.experiments)
        data_count = _data_count(project)
        self.stats_label.setText(tr("Experiments: {p0} | Data sets: {p1}",
                                    p0=exp_count, p1=data_count))

        self.runs_table.setRowCount(0)
        recent = list(project.workflow_runs)[-8:]
        for run in recent:
            row = self.runs_table.rowCount()
            self.runs_table.insertRow(row)
            self.runs_table.setItem(row, 0, QTableWidgetItem(run.run_id))
            self.runs_table.setItem(row, 1, QTableWidgetItem(run.workflow_ref))
            self.runs_table.setItem(row, 2, QTableWidgetItem(run.status))
            self.runs_table.setItem(
                row, 3, QTableWidgetItem((run.finished_at or run.started_at)[:19])
            )

    def _on_create(self) -> None:
        self.create_experiment_requested.emit(self.title_edit.text().strip())


class _ImportHint(QLabel):
    """Keep every wrapped instruction line visible at the actual column width."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._queue_height()

    def _queue_height(self):
        if not getattr(self, '_height_pending', False):
            self._height_pending = True
            QTimer.singleShot(0, self, self._fit_height)

    def _fit_height(self):
        self._height_pending = False
        # QLabel includes its explicit minimum height in heightForWidth().
        # Clear the previous constraint before measuring a wider column.
        previous = self.height()
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        needed = max(self.fontMetrics().height(), self.heightForWidth(max(1, self.width())))
        self.setFixedHeight(needed)
        if previous != needed:
            self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._queue_height()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._queue_height()


class ExperimentImportPanel(QWidget):
    'Persistent import form for single, segmented and batch datasets, with linking options.'

    import_options_requested = Signal(str, str, str, bool)  # (exp_id, name, source, copy)
    segmented_import_requested = Signal(str, str)
    batch_import_requested = Signal(str, list, bool)  # (exp_id, folders, group)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._exp_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.copy_check = QCheckBox(tr("Link raw data to project (read only, copy if necessary)"))
        self.copy_check.setObjectName("MutedText")
        self.copy_check.setChecked(True)
        self.copy_check.setToolTip(tr(
                'Checked: link raw data into the project, copying when '
                'needed. Unchecked: reference the source in place. Keep '
                'source paths accessible when links or references are used; '
                'generated processing files are separate.'
            ))
        layout.addWidget(self.copy_check)
        layout.addSpacing(4)

        import_columns = QHBoxLayout()
        import_columns.setSpacing(8)
        layout.addLayout(import_columns)
        self.single_group = QGroupBox(tr("single import"))
        self.single_group.setObjectName("SectionTitle")
        single_layout = QVBoxLayout(self.single_group)
        single_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        single_layout.setSpacing(6)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("sample data name (optional)"))
        form = QHBoxLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText(tr("Bruker dataset directory (including acqus)"))
        form.addWidget(self.source_edit, 1)
        self.source_edit.setMinimumWidth(0)
        browse = QPushButton(tr("Browse..."))
        browse.setObjectName("SubtleAction")
        self.browse_button = browse
        browse.clicked.connect(self._browse)
        form.addWidget(browse)
        single_layout.addLayout(form)
        self.import_button = QPushButton(tr("import sample data"))
        self.import_button.setObjectName("PrimaryAction")
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._on_import)
        single_layout.addWidget(self.import_button)
        single_layout.addWidget(self.name_edit)
        self.source_edit.textChanged.connect(
            lambda _t: self.import_button.setEnabled(bool(self.source_edit.text().strip()))
        )
        import_columns.addWidget(self.single_group, 1)

        self.segmented_group = QGroupBox(tr("Segments / repeats"))
        self.segmented_group.setToolTip(tr("segmented data or repeated experiment overlay import"))
        self.segmented_group.setObjectName("SectionTitle")
        segmented_layout = QVBoxLayout(self.segmented_group)
        segmented_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        segmented_layout.setSpacing(6)
        segmented_hint = _ImportHint(
            tr(
                "For one acquisition split into several segments (complementary NUS points "
                "completing the grid) or averaged repeat experiments (same parameters / sampling "
                "points, better SNR): pick the container directory (no acqus at the top level, at "
                "least 2 subdirectories each holding acqus). On import the segments are merged "
                "into a single sample data "
                "set.",
            )
        )
        segmented_hint.setWordWrap(True)
        segmented_hint.setObjectName("MutedText")
        segmented_form = QHBoxLayout()
        self.segmented_source_edit = QLineEdit()
        self.segmented_source_edit.setPlaceholderText(
            tr(
                "segmented/duplicate experiment container directory (containing multiple acqus "
                "subdirectories)",
            )
        )
        segmented_form.addWidget(self.segmented_source_edit, 1)
        self.segmented_source_edit.setMinimumWidth(0)
        segmented_browse = QPushButton(tr("Browse..."))
        segmented_browse.setObjectName("SubtleAction")
        self.segmented_browse_button = segmented_browse
        segmented_browse.clicked.connect(self._on_segmented_browse)
        segmented_form.addWidget(segmented_browse)
        segmented_layout.addLayout(segmented_form)
        self.segmented_import_button = QPushButton(tr("Import segments"))
        self.segmented_import_button.setToolTip(tr("segmented/repeated experiment overlay import"))
        self.segmented_import_button.setObjectName("PrimaryAction")
        self.segmented_import_button.setEnabled(False)
        self.segmented_import_button.clicked.connect(self._on_segmented_import)
        segmented_layout.addWidget(self.segmented_import_button)
        segmented_layout.addWidget(segmented_hint)
        self.segmented_source_edit.textChanged.connect(
            lambda _t: self.segmented_import_button.setEnabled(
                bool(self.segmented_source_edit.text().strip())
            )
        )
        import_columns.addWidget(self.segmented_group, 1)

        self.batch_group = QGroupBox(tr("Batch processing"))
        self.batch_group.setObjectName("SectionTitle")
        batch_layout = QVBoxLayout(self.batch_group)
        batch_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        batch_layout.setSpacing(6)
        batch_hint = _ImportHint(
            tr(
                "Browse to a top-level folder to detect Bruker data in its subfolders, then filter "
                "by dimensionality. Grouping creates separate groups for 1D, 2D and 3D data. "
                "2D groups can run in parallel; 3D groups run sequentially.",
            )
        )
        batch_hint.setWordWrap(True)
        batch_hint.setObjectName("MutedText")
        self._batch_candidates = {}
        self._batch_updating = False
        self.batch_list = QListWidget()
        self.batch_list.installEventFilter(self)
        self.batch_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.batch_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.batch_list.hide()
        model = self.batch_list.model()
        model.rowsInserted.connect(self._sync_batch_list)
        model.rowsRemoved.connect(self._sync_batch_list)
        model.modelReset.connect(self._sync_batch_list)
        self.batch_list.itemChanged.connect(self._on_batch_item_changed)
        self.batch_group_check = QCheckBox(tr("Group data by dimensionality"))
        self.batch_group_check.setToolTip(
            tr(
                "Checked: create one group per dimensionality for later processing. "
                "Unchecked: import separate data entries.",
            )
        )
        self.batch_group_check.setChecked(False)
        batch_buttons = QHBoxLayout()
        batch_buttons.setContentsMargins(0, 0, 0, 0)
        self.batch_add_button = QPushButton(tr("Browse..."))
        self.batch_add_button.setObjectName("SubtleAction")
        self.batch_add_button.clicked.connect(self._on_batch_add_folder)
        self.batch_clear_button = QPushButton(tr("Remove checked"))
        self.batch_clear_button.setObjectName("SubtleAction")
        self.batch_clear_button.clicked.connect(self._on_batch_clear)
        batch_buttons.addWidget(self.batch_clear_button)
        batch_buttons.addStretch(1)
        batch_buttons.addWidget(self.batch_add_button)
        batch_layout.addLayout(batch_buttons)
        self.batch_import_button = QPushButton(tr("Batch import"))
        self.batch_import_button.setObjectName("PrimaryAction")
        self.batch_import_button.setEnabled(False)
        self.batch_import_button.clicked.connect(self._on_batch_import)
        batch_layout.addWidget(self.batch_import_button)
        self.dimension_filter = QComboBox()
        for text, dimensions in (
            (tr("Import all"), (1,2,3)), (tr("Import 1D only"), (1,)), (tr("Import 2D only"), (2,)),
            (tr("Import 3D only"), (3,)), (tr("Import 1D/2D only"), (1,2)),
            (tr("Import 2D/3D only"), (2,3)), (tr("Import 1D/3D only"), (1,3)),
        ):
            self.dimension_filter.addItem(text, dimensions)
        self.dimension_filter.currentIndexChanged.connect(self._apply_batch_filter)
        batch_layout.addWidget(self.dimension_filter)
        batch_layout.addWidget(self.batch_list)
        batch_layout.addWidget(self.batch_group_check)
        batch_layout.addWidget(batch_hint)
        import_columns.addWidget(self.batch_group, 1)
        self._align_import_controls()
        layout.addStretch(1)

    def _align_import_controls(self):
        controls = [self.browse_button, self.segmented_browse_button,
                    self.batch_add_button, self.batch_clear_button]
        height = max(widget.sizeHint().height() for widget in
                     [*controls, self.source_edit, self.segmented_source_edit])
        for button in controls:
            button.setFixedHeight(height)

    def _batch_all_item(self) -> QListWidgetItem | None:
        first = self.batch_list.item(0)
        return first if first and first.data(Qt.ItemDataRole.UserRole) is True else None

    def _batch_path_items(self) -> list[QListWidgetItem]:
        first_path = int(self._batch_all_item() is not None)
        return [self.batch_list.item(index)
                for index in range(first_path, self.batch_list.count())]

    def _on_batch_item_changed(self, item: QListWidgetItem) -> None:
        if self._batch_updating:
            return
        if item is self._batch_all_item():
            self._set_batch_checks(item.checkState())
        else:
            self._sync_batch_all_state()

    def _set_batch_checks(self, state: Qt.CheckState) -> None:
        with QSignalBlocker(self.batch_list):
            for item in self._batch_path_items():
                item.setCheckState(state)
        self._sync_batch_all_state()

    def _sync_batch_all_state(self) -> None:
        item = self._batch_all_item()
        if item is None:
            return
        paths = self._batch_path_items()
        checked = sum(path.checkState() == Qt.CheckState.Checked for path in paths)
        state = Qt.CheckState.Unchecked
        if checked:
            state = (
                Qt.CheckState.Checked if checked == len(paths) else Qt.CheckState.PartiallyChecked
            )
        with QSignalBlocker(self.batch_list):
            item.setCheckState(state)

    def _sync_batch_list(self, *_args):
        if self._batch_updating:
            return
        count = len(self._batch_path_items())
        self.batch_list.setVisible(count > 0)
        self.batch_import_button.setEnabled(count > 0)
        if count:
            header = int(self._batch_all_item() is not None)
            row_height = max(self.fontMetrics().height(), self.batch_list.sizeHintForRow(0))
            self.batch_list.setFixedHeight(
                (min(count, 4) + header) * row_height + 2 * self.batch_list.frameWidth() + 4
            )
            self._sync_batch_all_state()

    def changeEvent(self, event):
        super().changeEvent(event)
        if (
            event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange)
            and hasattr(self, 'batch_list')
        ):
            QTimer.singleShot(0, self, self._sync_batch_list)
            QTimer.singleShot(0, self, self._align_import_controls)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def browse_single(self) -> None:
        'Select a single Bruker dataset directory.'
        self._browse()

    def add_batch_folder(self) -> None:
        'Add directory to the batch import list.'
        self._on_batch_add_folder()

    def clear_batch_list(self) -> None:
        'Clear the batch import list.'
        self._on_batch_clear()

    def import_batch(self) -> None:
        'Perform bulk import by list (or repeat experiment overlay).'
        self._on_batch_import()

    def import_single(self) -> None:
        'Import the currently selected single dataset.'
        self._on_import()

    def browse_segmented(self) -> None:
        'Select segmented data/Overlapping containers directory.'
        self._on_segmented_browse()

    def import_segmented(self) -> None:
        'Execute segmented data/Repeat overlay import.'
        self._on_segmented_import()

    def set_context(self, exp_id: str) -> None:
        self._exp_id = exp_id

    def _browse(self) -> None:

        from gui.settings import data_root_path

        start = self.source_edit.text().strip() or str(data_root_path())
        path = choose_directory(self, tr("Select Bruker dataset directory"), start)
        if path:
            self.source_edit.setText(path)

    def eventFilter(self, watched, event):
        if watched is self.batch_list and event.type() == QEvent.Type.KeyPress:
            if (event.key() == Qt.Key.Key_A
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._set_batch_checks(Qt.CheckState.Checked)
                return True
        return super().eventFilter(watched, event)

    def _on_batch_add_folder(self) -> None:
        """Add data file folders to the batch list (automatically check Bruker datasets in sub-file
        folders). 0.2.199-patch29gg: Browse starting point = data directory.
        """
        from gui.settings import data_root_path

        path = choose_directory(
            self, tr("Select Bruker Data Folder (Batch)"), str(data_root_path())
        )
        if not path:
            return
        self._add_batch_path(path)

    def _add_batch_path(self, path: str) -> None:
        found = self._bruker_datasets_under(Path(path))
        if not found:
            InfoDialog.show_info(
                self,
                tr("No data found"),
                tr(
                    "There is no Bruker dataset containing acqus in the selected directory and its "
                    "subfolders",
                ),
            )
            return
        from core.project.grouping import raw_ndim
        for path in found:
            self._batch_candidates[str(path)] = raw_ndim(path)
        self._apply_batch_filter()

    def _apply_batch_filter(self, *_args):
        previous = {item.text(): item.checkState() for item in self._batch_path_items()}
        dimensions = self.dimension_filter.currentData()
        paths = [path for path, ndim in self._batch_candidates.items() if ndim in dimensions]
        self._batch_updating = True
        self.batch_list.setUpdatesEnabled(False)
        self.batch_list.clear()
        if paths:
            header = QListWidgetItem(tr("All"))
            header.setData(Qt.ItemDataRole.UserRole, True)
            header.setFlags(header.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            header.setCheckState(Qt.CheckState.Unchecked)
            header.setToolTip(tr("Check or uncheck all paths shown by the current filter"))
            self.batch_list.addItem(header)
        for path in paths:
            item = QListWidgetItem(path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(previous.get(path, Qt.CheckState.Unchecked))
            item.setToolTip(path)
            self.batch_list.addItem(item)
        self._batch_updating = False
        self.batch_list.setUpdatesEnabled(True)
        self._sync_batch_list()

    @staticmethod
    def _bruker_datasets_under(root: Path) -> list[Path]:
        """All data sets containing acqus in the root and sub-file folders directory (sorting and
        deduplication).
        """
        datasets: set[Path] = set()
        try:
            candidates = [Path(p).parent for p in root.rglob("acqus") if p.is_file()]
            candidates.append(root)
        except OSError:
            candidates = [root]
        for cand in candidates:
            if (cand / "acqus").is_file():
                datasets.add(cand.resolve())
        return sorted(datasets)

    def _on_batch_clear(self) -> None:
        self._batch_updating = True
        for item in reversed(self._batch_path_items()):
            if item.checkState() == Qt.CheckState.Checked:
                removed = self.batch_list.takeItem(self.batch_list.row(item))
                self._batch_candidates.pop(removed.text(), None)
        if not self._batch_path_items():
            self.batch_list.clear()
        self._batch_updating = False
        self._sync_batch_list()

    def _on_batch_import(self) -> None:
        folders = [item.text() for item in self._batch_path_items()]
        if not self._exp_id or not folders:
            return
        self.batch_import_requested.emit(self._exp_id, folders, self.batch_group_check.isChecked())
        self.batch_list.clear()
        self._batch_candidates.clear()

    def _on_import(self) -> None:
        source = self.source_edit.text().strip()
        if not source:
            InfoDialog.show_info(
                self,
                tr("import sample data"),
                tr("Please select Bruker dataset directory (including acqus) first"),
            )
            return


        self.import_options_requested.emit(
            self._exp_id,
            self.name_edit.text().strip(),
            source,
            self.copy_check.isChecked(),
        )

    def clear_import_form(self) -> None:
        """After successful import, clear the single/The name and path of the segmented import
        form(0.2.112).
        """
        self.name_edit.clear()
        self.source_edit.clear()
        self.segmented_source_edit.clear()

    def _on_segmented_browse(self) -> None:
        """Select the segmented collection container directory (0.2.199-patch29gg: empty input
        starting point = total data directory).
        """
        from gui.settings import data_root_path

        path = choose_directory(
            self,
            tr("Select the segmented/duplicate experiment container directory"),
            self.segmented_source_edit.text().strip() or str(data_root_path()),
        )
        if path:
            self.segmented_source_edit.setText(path)

    def _on_segmented_import(self) -> None:
        """Segmented collection import: container directory (merge FID) directly send a request
        (with current experiment, 0.2.122).
        """
        source = self.segmented_source_edit.text().strip()
        if not source:
            InfoDialog.show_info(
                self,
                tr("segmented collection import"),
                tr("Please select the segmented collection container directory first"),
            )
            return
        self.segmented_import_requested.emit(self._exp_id, source)


class ExperimentDashboard(QWidget):
    'Experiment overview with dataset status, editable names and a persistent import form.'

    import_options_requested = Signal(str, str, str, bool)  # (exp_id, name, source, copy)
    data_rename_requested = Signal(str, str, str)  # (exp_id, data_id, new_name)
    segmented_import_requested = Signal(str, str)
    batch_import_requested = Signal(str, list, bool)  # (exp_id, folders, group)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager: ProjectManager | None = None
        self._exp_id = ""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.page_content = QWidget()
        layout = QVBoxLayout(self.page_content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self.scroll_area.setWidget(self.page_content)
        root_layout.addWidget(self.scroll_area)

        title = QLabel(tr("experiment"))
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.context_label = QLabel("")
        self.context_label.setWordWrap(True)
        self.context_label.setObjectName("PanelSubtitle")
        layout.addWidget(self.context_label)

        data_title = QLabel(tr("sample data"))
        data_title.setObjectName("SectionTitle")
        self.data_table = QTableWidget(0, 3)
        self.data_table.setHorizontalHeaderLabels([tr("sample data"), tr("name"), tr("state")])
        self.data_table.horizontalHeader().setStretchLastSection(True)
        self.data_table.setMinimumHeight(0)

        self.data_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.data_table.itemChanged.connect(self._on_data_name_edited)
        self._loading_table = False


        self.import_panel = ExperimentImportPanel(self.page_content)
        self.import_panel.import_options_requested.connect(self.import_options_requested.emit)
        self.import_panel.segmented_import_requested.connect(self.segmented_import_requested.emit)
        self.import_panel.batch_import_requested.connect(self.batch_import_requested.emit)

        self.copy_check = self.import_panel.copy_check
        self.single_group = self.import_panel.single_group
        self.name_edit = self.import_panel.name_edit
        self.source_edit = self.import_panel.source_edit
        self.import_button = self.import_panel.import_button
        self.segmented_group = self.import_panel.segmented_group
        self.segmented_source_edit = self.import_panel.segmented_source_edit
        self.segmented_import_button = self.import_panel.segmented_import_button
        self.batch_group = self.import_panel.batch_group
        self.batch_list = self.import_panel.batch_list
        self.batch_add_button = self.import_panel.batch_add_button
        self.batch_clear_button = self.import_panel.batch_clear_button
        self.batch_import_button = self.import_panel.batch_import_button
        layout.addWidget(self.import_panel)
        layout.addSpacing(8)
        layout.addWidget(data_title)
        layout.addWidget(self.data_table)
        layout.addStretch(1)

    def set_context(self, manager: ProjectManager, exp_id: str, label: str) -> None:
        self.manager = manager
        self._exp_id = exp_id
        self.import_panel.set_context(exp_id)
        self.context_label.setText(f"{label} ({exp_id})" if exp_id else "")
        self.refresh()

    def _on_data_name_edited(self, item) -> None:
        """Rename the sample data (0.2.162-patch13) after editing the "Name" column of the data
        table.
        """
        if item.column() != 1 or self._loading_table:
            return
        if self.manager is None or self.manager.project is None or not self._exp_id:
            return
        data_item = self.data_table.item(item.row(), 0)
        if data_item is None:
            return
        data_id = data_item.text()
        new_name = item.text().strip()
        entry = self.manager.project.experiment(self._exp_id)
        data_entry = next((d for d in entry.data if d.id == data_id), None) if entry else None
        if data_entry is None or new_name == (getattr(data_entry, "title", "") or ""):
            return
        self.data_rename_requested.emit(self._exp_id, data_id, new_name)
        self.refresh()

    def refresh(self) -> None:
        self.data_table.setRowCount(0)
        if self.manager is None or self.manager.project is None or not self._exp_id:
            return
        exp = self.manager.project.experiment(self._exp_id)
        if exp is None:
            return
        self._loading_table = True
        try:
            for data in _active_data_of(exp):
                row = self.data_table.rowCount()
                self.data_table.insertRow(row)
                self.data_table.setItem(row, 0, QTableWidgetItem(data.id))
                self.data_table.setItem(row, 1, QTableWidgetItem(getattr(data, "title", "") or ""))
                self.data_table.setItem(row, 2, QTableWidgetItem(getattr(data, "status", "") or ""))
        finally:
            self._loading_table = False

    def _browse(self) -> None:
        self.import_panel.browse_single()

    def _on_batch_add_folder(self) -> None:
        self.import_panel.add_batch_folder()

    @staticmethod
    def _bruker_datasets_under(root: Path) -> list[Path]:
        return ExperimentImportPanel._bruker_datasets_under(root)

    def _on_batch_clear(self) -> None:
        self.import_panel.clear_batch_list()

    def _on_batch_import(self) -> None:
        self.import_panel.set_context(self._exp_id)
        self.import_panel.import_batch()

    def _on_import(self) -> None:
        self.import_panel.set_context(self._exp_id)
        self.import_panel.import_single()

    def clear_import_form(self) -> None:
        'Clear the import form after successful import.'
        self.import_panel.clear_import_form()

    def _on_segmented_browse(self) -> None:
        self.import_panel.browse_segmented()

    def _on_segmented_import(self) -> None:
        self.import_panel.set_context(self._exp_id)
        self.import_panel.import_segmented()
