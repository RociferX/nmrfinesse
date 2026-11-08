"""Middle context panel: Switch with the tree selection level on the left. - Workspace selected ->
New project/Open project/Recent projects (embedded welcome page); - Project selected -> New
experiment type (embedded form); - Experiment type selected -> Import sample data (embedded
form); - Data / subdirectory selected -> Pipeline processing step (generate FID -> Peak
selection; New/The import form is embedded directly in the middle, independent window does not
pop up.
"""

from __future__ import annotations

from pathlib import Path

from qtcompat.QtCore import QRect, QSize, Qt
from qtcompat.QtWidgets import (
    QBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.dashboards import ExperimentDashboard, ProjectDashboard
from gui.group_panel import GroupBatchPanel
from gui.pipeline_panel import PipelinePanel
from gui.welcome_page import WelcomePage
from qtcompat import Signal
from ui_support.i18n import tr
from ui_support.title_layout import TitleLabel


class _NotesFlow(QLayout):
    """Wrap complete fields; explicit lines start a separate block."""

    def __init__(self, parent):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, max(1, width), 0), measure=True)

    def sizeHint(self):
        return QSize(400, self.heightForWidth(400))

    def minimumSize(self):
        return QSize(0, self.parentWidget().fontMetrics().height())

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, measure=False)

    def _arrange(self, rect, *, measure):
        left, x, y, height = rect.x(), rect.x(), rect.y(), 0
        for item in self._items:
            label = item.widget()
            natural = (label.natural_width() if isinstance(label, TitleLabel) else
                       label.fontMetrics().horizontalAdvance(label.text()) + 2)
            width = min(max(1, rect.width()), natural)
            if height and (label.property('notesBlockStart') or x + width > rect.right() + 1):
                x, y, height = left, y + height, 0
            needed = label.heightForWidth(width)
            needed = max(needed, label.fontMetrics().height())
            if not measure:
                item.setGeometry(QRect(x, y, width, needed))
            x += width + 8
            height = max(height, needed)
        return y + height - rect.y()


class _NotesLabel(QWidget):
    """Plain-text notes with one flow item per compact field."""

    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self._flow = _NotesFlow(self)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setText(text)

    def setText(self, text, *, title=""):
        self._plain_text = text
        while self._flow.count():
            old = self._flow.takeAt(0).widget()
            old.hide()
            old.deleteLater()
        blocks = [(False, text)]
        if title and title in text:
            before, _match, after = text.partition(title)
            head, separator, prefix = before.rpartition('\n')
            blocks = [(False, head if separator else ''), (True, prefix + title),
                      (False, after.lstrip('\n'))]
        for is_title, block in blocks:
            if is_title:
                label = TitleLabel(block, self)
                label.setObjectName('MutedText')
                label.setProperty('notesBlockStart', True)
                self._flow.addWidget(label)
                label.show()
                continue
            for line in block.split('\n') if block else []:
                for index, field in enumerate(line.split('  ·  ')):
                    label = QLabel(('·  ' if index else '') + field, self)
                    label.setObjectName('MutedText')
                    label.setTextFormat(Qt.TextFormat.PlainText)
                    label.setWordWrap(True)
                    label.setProperty('notesBlockStart', index == 0)
                    self._flow.addWidget(label)
                    label.show()
        self._flow.invalidate()
        self.updateGeometry()

    def text(self):
        return self._plain_text

    def textFormat(self):
        return Qt.TextFormat.PlainText

    def wordWrap(self):
        return True

    def heightForWidth(self, width):
        return self._flow.heightForWidth(width)


class CenterPanel(QWidget):
    'Middle panel container: switch pages according to the selected level.'

    log_message = Signal(str)
    log_scoped = Signal(str, str)
    memory_guard_requested = Signal(str)
    manual_open_requested = Signal(str)
    import_data_requested = Signal(str)
    import_options_requested = Signal(str, str, str, bool)  # (exp_id, name, source, copy)
    data_rename_requested = Signal(str, str, str)  # (exp_id, data_id, new_name)
    batch_import_requested = Signal(str, list, bool)  # (exp_id, folders, group)
    segmented_import_requested = Signal(str, str)
    create_experiment_requested = Signal(str)
    edit_notes_requested = Signal(str, str, str)  # (kind, exp_id, data_id)
    group_run_requested = Signal(str, str, list, str, dict)
    # (exp_id, group_id, steps, reference_data_id)
    new_project_requested = Signal(str)
    open_project_requested = Signal(str)

    def __init__(
        self,
        manager=None,
        controller=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("PanelCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._manager = manager

        self.welcome_page = WelcomePage()
        self.welcome_page.new_project_requested.connect(self.new_project_requested.emit)
        self.welcome_page.open_project_requested.connect(self.open_project_requested.emit)

        self.pipeline = PipelinePanel(manager, controller)
        self.pipeline.header_widget.hide()
        self.pipeline.log_message.connect(self.log_message.emit)
        self.pipeline.log_scoped.connect(self.log_scoped.emit)
        self.pipeline.memory_guard_requested.connect(
            self.memory_guard_requested.emit
        )
        self.pipeline.manual_open_requested.connect(self.manual_open_requested.emit)

        self.project_page = ProjectDashboard()
        self.project_page.create_experiment_requested.connect(
            self.create_experiment_requested.emit
        )

        self.experiment_page = ExperimentDashboard()
        self.experiment_page.data_rename_requested.connect(
            self.data_rename_requested.emit
        )
        self.experiment_page.import_options_requested.connect(
            self.import_options_requested.emit
        )
        self.experiment_page.batch_import_requested.connect(
            self.batch_import_requested.emit
        )
        self.experiment_page.segmented_import_requested.connect(
            self.segmented_import_requested.emit
        )

        self.group_page = GroupBatchPanel()
        self.group_page.context_changed.connect(self._set_group_guide)
        self.group_page.log_message.connect(self.log_message.emit)
        self.group_page.run_group_batch_requested.connect(
            self.group_run_requested.emit
        )
        self.group_page.summary_requested.connect(self._on_group_summary)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome_page)  # index 0: Workspace
        self.stack.addWidget(self.project_page)  # index 1: Project
        self.stack.addWidget(self.experiment_page)  # index 2: Experiment
        self.stack.addWidget(self.pipeline)  # index 3: Data / folder
        self.stack.addWidget(self.group_page)


        self.notes_header = QVBoxLayout()
        self.selection_guide_label = QLabel()
        self.selection_guide_label.setObjectName("SelectionGuide")
        self.selection_guide_label.setWordWrap(True)
        self.notes_header.addWidget(self.selection_guide_label)
        self.notes_label = _NotesLabel("")
        self.notes_label.setObjectName("MutedText")

        self.edit_notes_button = QPushButton(tr("Editor's note"))
        self.edit_notes_button.setObjectName("SubtleAction")
        self.edit_notes_button.setToolTip(
            tr("Add or edit the note for the current project, experiment type or sample data")
        )
        self.edit_notes_button.clicked.connect(self._on_edit_notes)
        self.notes_area = QWidget()
        self._notes_actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._notes_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._notes_actions_layout.setSpacing(4)
        self._notes_actions_layout.addWidget(self.notes_label, 1)
        self._notes_actions_layout.addWidget(self.edit_notes_button, 0, Qt.AlignmentFlag.AlignRight)
        self.notes_area.setLayout(self._notes_actions_layout)
        self.notes_area.setVisible(False)
        self.notes_header.insertWidget(1, self.notes_area)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.notes_header)
        layout.addWidget(self.stack, 1)
        self._update_selection_guide('workspace')
        self._update_notes('workspace', '', '')

    def resizeEvent(self, event) -> None:
        'Move the notes editor below the notes in narrow columns.'
        super().resizeEvent(event)
        direction = (
            QBoxLayout.Direction.LeftToRight
            if self.width() >= 520
            else QBoxLayout.Direction.TopToBottom
        )
        if self._notes_actions_layout.direction() != direction:
            self._notes_actions_layout.setDirection(direction)
        self._notes_actions_layout.setAlignment(
            self.edit_notes_button, Qt.AlignmentFlag.AlignRight
        )

    # ------------------------------------------------------------------
    def set_selection(
        self, kind: str, exp_id: str, data_id: str = "", group_id: str = ""
    ) -> None:
        """Press the tree selection level to switch to the middle page and refresh the top comment
        bar.
        """
        if kind != "group":
            self._update_selection_guide(kind, exp_id)
        self._update_notes(kind, exp_id, data_id, group_id)
        if kind == "workspace":
            self.stack.setCurrentIndex(0)
            self.welcome_page.refresh()
        elif kind == "project":
            self.stack.setCurrentIndex(1)
            if self._manager is not None and self._manager.project is not None:
                self.project_page.set_context(self._manager)
        elif kind == "experiment":
            self.stack.setCurrentIndex(2)
            if self._manager is not None and self._manager.project is not None:
                exp = self._manager.project.experiment(exp_id)
                label = exp.title if exp is not None else exp_id
                self.experiment_page.set_context(self._manager, exp_id, label)
        elif kind == "group":
            self.stack.setCurrentIndex(4)
            self.group_page.set_context(self._manager, exp_id, group_id)
        else:
            self.stack.setCurrentIndex(3)
            self.pipeline.set_selection(kind, exp_id, data_id)

    def _update_selection_guide(self, kind: str, exp_id: str = "") -> None:
        'Show a short action hint for the selected tree level.'
        guide = {
            "workspace": (tr("Workspace"), tr("Create or open projects")),
            "project": (tr("Project"), tr("Create experiments")),
            "experiment": (tr("Experiment"), tr("Import sample data")),
        }
        if kind in ("data", "folder"):
            project = self._manager.project if self._manager is not None else None
            experiment = project.experiment(exp_id) if project is not None else None
            context = (f"{project.name} / {experiment.title or exp_id}"
                       if project is not None and experiment is not None else exp_id)
            flow = tr('Flow: {p0}', p0=tr('import -> FID -> spectrum -> peak selection'))
            text = f"{tr('Process sample data')}  ·  {flow}"
            if context:
                text += f"  ·  {context}"
            self.selection_guide_label.setText(text)
            self.selection_guide_label.setToolTip(text)
            return
        else:
            level, purpose = guide.get(
                kind, (tr("Workspace"), tr("Create or open projects"))
            )
        self.selection_guide_label.setText(f"{level}  ·  {purpose}")
        self.selection_guide_label.setToolTip("")

    # ------------------------------------------------------------------
    def _set_group_guide(self, context: str) -> None:
        text = f"{tr('Group')}  ·  {tr('Process group data in batches')}  ·  {context}"
        self.selection_guide_label.setText(text)
        self.selection_guide_label.setToolTip(text)

    def set_manager(self, manager) -> None:
        'Binding/renew ProjectManager (called by the main window when switching projects).'
        self._manager = manager

    def update_notes(self, *args, **kwargs) -> None:
        'Refresh the comments page (public packaging: _update_notes).'
        self._update_notes(*args, **kwargs)

    def _update_notes(
        self, kind: str, exp_id: str, data_id: str = "", group_id: str = ""
    ) -> None:
        """Display the project/experiment type/sample data/Data group annotation according to the
        selected level (the top of the middle area).
        """
        from gui.notes import data_note, data_note_fields, experiment_note, sample_note

        self._notes_kind = kind if kind in (
            "project", "experiment", "data", "folder", "group"
        ) else ""
        self._notes_exp_id = exp_id
        self._notes_data_id = data_id if kind in ("data", "folder") else ""
        self._notes_group_id = group_id if kind == "group" else ""
        show = bool(self._notes_kind)



        self.notes_label.setVisible(show and kind != "group")
        self.notes_area.setVisible(show and kind != "group")
        self.edit_notes_button.setVisible(show and kind != "group")
        if not show or kind == "group":
            return
        project = self._manager.project if self._manager is not None else None
        if project is None:
            return
        text = ""
        title = ""
        if kind == "project":
            text = sample_note(project)
        elif kind == "experiment":
            text = experiment_note(project, exp_id)
        elif kind in ("data", "folder"):
            text = data_note(project, exp_id, data_id)
            title = str(data_note_fields(project, exp_id, data_id).get("notes", "") or "")
            if not data_id:
                self.notes_label.setText(text, title=title)
                return
            try:
                entry = self._manager.data(exp_id, data_id)
                source = str(getattr(entry, "source", "") or "").strip()
                if not source:
                    segments = getattr(entry, "segments", None) or []
                    source = str(segments[0] if segments else "").strip()
                if source:
                    path = Path(source).expanduser()
                    if not path.is_absolute() and getattr(self._manager, "root", None):
                        path = Path(self._manager.root) / path
                    source_path = str(path.resolve())
                    source_line = tr("Source path: {p0}", p0=source_path)
                    text = f"{text}\n{source_line}" if text else source_line
            except (AttributeError, OSError, RuntimeError, ValueError):

                pass
        self.notes_label.setText(text, title=title)

    def _on_group_summary(self, summary: dict) -> None:
        'Summary of group batch processing completion: log output + panel clearing progress.'
        scope = str(summary.get("log_scope") or "")

        def emit_log(message: str) -> None:
            if scope:
                self.log_scoped.emit(message, scope)
            else:
                self.log_message.emit(message)

        info = str(summary.get("info", ""))
        if info:
            emit_log(info)
        for item in summary.get("items") or []:
            data_id = item.get("data_id", "")
            if item.get("skipped"):
                emit_log(
                    tr(
                        "  Skipped {p0}: "
                        "{p1}",
                        p0=data_id,
                        p1=item.get("error", ""),
                    )
                )
            elif item.get("failed"):
                emit_log(
                    tr(
                        "  Failed {p0}: "
                        "{p1}",
                        p0=data_id,
                        p1=item.get("error", ""),
                    )
                )
            elif item.get("cancelled"):
                emit_log(
                    tr(
                        "  Cancelled {p0}: "
                        "{p1}",
                        p0=data_id,
                        p1=item.get("error", ""),
                    )
                )
            elif item.get("ok"):
                emit_log(
                    tr(
                        "  Done {p0}: "
                        "{p1}",
                        p0=data_id,
                        p1=item.get("message", ""),
                    )
                )
            else:
                emit_log(
                    tr(
                        "  Failed {p0}: "
                        "{p1}",
                        p0=data_id,
                        p1=item.get("error", ""),
                    )
                )
        self.group_page.set_progress("")

    def _on_edit_notes(self) -> None:
        """Click "Edit Comment": Send an edit request (the main window opens the comment dialog
        box).
        """
        self.edit_notes_requested.emit(
            self._notes_kind, self._notes_exp_id, self._notes_data_id
        )

    def refresh(self) -> None:
        self.welcome_page.refresh()
        self.pipeline.refresh()
        self.project_page.refresh()
        self.experiment_page.refresh()
        if self._exp_group_context():
            self.group_page.refresh()

    def _exp_group_context(self) -> bool:
        'Whether you are currently staying on the data group page (for refresh).'
        return bool(
            self.stack.currentWidget() is self.group_page
            and self.group_page.current_group_id
        )

    def run_step(self, step_id: str, data_id: str | None = None) -> None:
        self.pipeline.run_step(step_id, data_id=data_id)

    def current_experiment_id(self) -> str:
        return self.pipeline.current_experiment_id()
