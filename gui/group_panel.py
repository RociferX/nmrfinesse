"""The middle page of the data group: Batch processing of all data in the group (0.2.163). Two
modes: - Process the entire group according to reference data: select the data that has run
spectrum in the experiment, and take the valid parameters of the most recent successful spectrum
run and apply it to each data in the group (can be cut off to a certain step in the pipeline); -
optimise data in the group sequentially: perform a complete automatic processing process for
each data in the group in sequence (fid -> spectrum [unified automatic optimisation] -> peaks;
analysis step has been deleted, 2026-09-12). The actual execution is started by main_window and
the background thread is called ProcessingController.run_group_batch (workflow.batch.run_batch).
This panel is only responsible for parameter selection and signal issuance."""

from __future__ import annotations

from qtcompat.QtCore import Qt
from qtcompat.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from qtcompat import Signal
from ui_support.i18n import tr
from ui_support.theme import (
    fit_combo_width,
)

# Cutoff step options: value=BATCH_STEPS subset.
STOP_STEP_OPTIONS: list[tuple[str, str]] = [
    ("fid", tr("Generate FID")),
    ("spectrum", tr("Generate spectrum")),
    ("peaks", tr("Peak picking")),
]


class GroupBatchPanel(QWidget):
    """Data group batch processing panel (displayed when the group node is selected)."""

    log_message = Signal(str)
    context_changed = Signal(str)
    temperature_sort_changed = Signal(str, str)
    run_group_batch_requested = Signal(str, str, list, str, dict)
    # (exp_id, group_id, steps, reference_data_id)
    summary_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = None
        self._exp_id = ""
        self._group_id = ""
        self.temperature_sorts: dict[tuple, int] = {}
        self._notes_columns: list[tuple[str, str, dict[str, str]]] = []
        self.temperature_sort_button = QToolButton(self)
        self.temperature_sort_button.setAutoRaise(True)
        self.temperature_sort_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.temperature_sort_button.setStyleSheet("padding: 0 4px;")
        self.temperature_sort_button.setAccessibleName(tr("Sort by temperature"))
        self.temperature_sort_button.setToolTip(tr(
            "Sort columns by temperature: · original order, > low to high, < high to low."
        ))
        self.temperature_sort_button.clicked.connect(self._cycle_temperature_sort)
        self.temperature_sort_button.hide()

        # 0.2.199-patch29hd: The whole page can be scrolled up and down -- member/Contextual #
        # annotation content is no longer squashed when it is long.
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._content = QWidget()
        self._scroll.setWidget(self._content)
        _outer = QVBoxLayout(self)
        _outer.setContentsMargins(0, 0, 0, 0)
        _outer.addWidget(self._scroll)
        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self.notes_scroll = QScrollArea()
        self.notes_scroll.setWidgetResizable(True)
        self.notes_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.notes_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.notes_scroll.setVisible(False)
        layout.addWidget(self.notes_scroll)

        # ---- Mode A: Process the entire group according to reference data ----.
        ref_box = QGroupBox(tr("Process entire group by reference data"))
        ref_box.setObjectName("SectionTitle")
        ref_layout = QVBoxLayout(ref_box)
        ref_layout.setContentsMargins(8, 10, 8, 8)
        ref_layout.setSpacing(6)
        ref_hint = QLabel(
            tr(
                "Pick a data set of this experiment that already has a spectrum; its processing "
                "scripts are reused without automatic optimisation. You may also stop at a "
                "chosen step (for example, generate the FID "
                "only).",
            )
        )
        ref_hint.setWordWrap(True)
        ref_hint.setObjectName("MutedText")
        ref_layout.addWidget(ref_hint)

        reference_form = QGridLayout()
        reference_form.addWidget(QLabel(tr("Reference data:")), 0, 0)
        self.reference_combo = QComboBox()
        self.reference_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.reference_combo.setMinimumContentsLength(10)
        reference_form.addWidget(self.reference_combo, 0, 1)
        reference_form.addWidget(QLabel(tr("Processed to:")), 1, 0)
        self.stop_combo = QComboBox()
        for _value, label in STOP_STEP_OPTIONS:
            self.stop_combo.addItem(label)
        fit_combo_width(self.stop_combo)
        reference_form.addWidget(self.stop_combo, 1, 1)
        reference_form.setColumnStretch(1, 1)
        ref_layout.addLayout(reference_form)

        self.reference_data_options = {}
        self.reference_range_button = QPushButton(tr("direct dimension range"))
        self.reference_phase_button = QPushButton(tr("Phase"))
        self.reference_range_button.clicked.connect(lambda: self._edit_reference_options("range"))
        self.reference_phase_button.clicked.connect(lambda: self._edit_reference_options("phases"))
        self.run_ref_button = QPushButton(tr("Run"))
        self.run_ref_button.setToolTip(tr("Process entire group by reference data"))
        self.run_ref_button.setObjectName("PrimaryAction")
        self.run_ref_button.setEnabled(False)
        self.run_ref_button.clicked.connect(self._on_run_reference)
        self.reference_combo.currentIndexChanged.connect(self._refresh_reference_enabled)
        self.stop_combo.currentIndexChanged.connect(self._refresh_reference_enabled)
        self._refresh_reference_enabled()
        actions = QHBoxLayout()
        actions.addWidget(self.reference_range_button, 1)
        actions.addWidget(self.reference_phase_button, 1)
        actions.addWidget(self.run_ref_button, 1)
        ref_layout.addLayout(actions)
        layout.addWidget(ref_box)

        # ---- Mode B: optimise the data within the group in sequence ----.
        opt_box = QGroupBox(tr("Parallel optimisation of 2D data"))
        self.optimisation_box = opt_box
        opt_box.setObjectName("SectionTitle")
        opt_layout = QVBoxLayout(opt_box)
        opt_layout.setContentsMargins(8, 10, 8, 8)
        opt_layout.setSpacing(6)
        opt_hint = QLabel(
            tr(
                "2D data run in parallel up to the configured limit. 1D and 3D data run "
                "sequentially; one failure does not abort the group.",
            )
        )
        opt_hint.setWordWrap(True)
        opt_hint.setObjectName("MutedText")
        opt_layout.addWidget(opt_hint)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel(tr("Processed to:")))
        self.opt_stop_combo = QComboBox()
        for _value, _label in STOP_STEP_OPTIONS:
            self.opt_stop_combo.addItem(_label)
        fit_combo_width(self.opt_stop_combo)
        opt_row.addWidget(self.opt_stop_combo, 1)
        opt_layout.addLayout(opt_row)
        # Direct dimension range setting (displayed when processing to spectrum/peaks).
        self.ext_group = QGroupBox(tr("direct dimension range setting"))
        self.ext_group.setObjectName("SectionTitle")
        ext_row = QGridLayout(self.ext_group)
        ext_row.setContentsMargins(8, 10, 8, 8)
        self.ext_enable = QCheckBox(tr("Specify range"))
        ext_row.addWidget(self.ext_enable, 0, 0, 1, 2)
        ext_row.addWidget(QLabel(tr("Lower limit(ppm):")), 1, 0)
        self.ext_lo_edit = QLineEdit("10.5")
        self.ext_lo_edit.setMinimumWidth(0)
        ext_row.addWidget(self.ext_lo_edit, 1, 1)
        ext_row.addWidget(QLabel(tr("Upper limit(ppm):")), 2, 0)
        self.ext_hi_edit = QLineEdit("6.5")
        self.ext_hi_edit.setMinimumWidth(0)
        ext_row.addWidget(self.ext_hi_edit, 2, 1)
        opt_layout.addWidget(self.ext_group)
        # Peak picking threshold setting (displayed when peaks are processed).
        self.thresh_group = QGroupBox(tr("Peak picking threshold setting"))
        self.thresh_group.setObjectName("SectionTitle")
        thr_row = QVBoxLayout(self.thresh_group)
        thr_row.setContentsMargins(8, 10, 8, 8)
        thr_row.addWidget(QLabel(tr("Noise threshold (σ):")))
        self.thresh_edit = QLineEdit("")
        self.thresh_edit.setMinimumWidth(0)
        self.thresh_edit.setPlaceholderText(tr("Leave blank to use default"))
        thr_row.addWidget(self.thresh_edit)
        opt_layout.addWidget(self.thresh_group)
        self.opt_stop_combo.currentIndexChanged.connect(
            self._on_opt_stop_changed
        )
        # 0.2.199-patch29gp: Initially press the default cut-off step (generate FID)Hidden #
        # range/Threshold setting.
        self._on_opt_stop_changed()
        self.run_optimize_button = QPushButton(tr("optimise the data within the group in turn"))
        self.run_optimize_button.setObjectName("PrimaryAction")
        self.run_optimize_button.setEnabled(False)
        self.run_optimize_button.clicked.connect(self._on_run_optimize)
        opt_layout.addWidget(self.run_optimize_button)
        layout.addWidget(opt_box)

        self.progress_label = QLabel("")
        self.progress_label.setWordWrap(True)
        self.progress_label.setObjectName("MutedText")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    def set_context(
        self, manager, exp_id: str, group_id: str
    ) -> None:
        """Bind project context and refresh group information/Reference data drop-down."""
        if (manager, exp_id, group_id) != (self._manager, self._exp_id, self._group_id):
            self._notes_columns = []
        self._manager = manager
        self._exp_id = exp_id
        self._group_id = group_id
        self._refresh()

    def _refresh_notes(self, members) -> None:
        from gui.notes import data_note_fields

        columns = [
            (d.id, d.title or f"Data {d.id}", {
                key: str(value) for key, value in
                data_note_fields(self._manager.project, self._exp_id, d.id).items()
                if value is not None and str(value).strip()
            })
            for d in members
        ]
        if columns == self._notes_columns and self.notes_scroll.widget() is not None:
            self.notes_scroll.setVisible(any(fields for _, _, fields in columns))
            return
        self._notes_columns = columns
        self._render_notes()

    def _temperature_sort_context(self) -> tuple:
        return self._manager.root, self._exp_id, self._group_id

    def _cycle_temperature_sort(self) -> None:
        context = self._temperature_sort_context()
        mode = (self.temperature_sorts.get(context, 0) + 1) % 3
        if mode:
            self.temperature_sorts[context] = mode
        else:
            self.temperature_sorts.pop(context, None)
        self._render_notes()
        self.temperature_sort_changed.emit(self._exp_id, self._group_id)

    def _render_notes(self) -> None:
        from gui.notes import DATA_FIELDS, temperature_sort_key

        columns = self._notes_columns
        present = {key for _, _, fields in columns for key in fields}
        self.notes_scroll.setVisible(bool(present))
        if not present:
            return
        mode = self.temperature_sorts.get(self._temperature_sort_context(), 0)
        if mode:
            columns = sorted(columns, key=lambda column: temperature_sort_key(
                column[2].get("temperature"), mode
            ))
        display = dict(DATA_FIELDS)
        keys = ["notes", *(key for key in display if key != "notes")]
        keys.extend(sorted(present - display.keys()))
        row_keys = [key for key in keys if key in present]

        button = self.temperature_sort_button
        restore_focus = button.hasFocus()
        scroll_position = self.notes_scroll.verticalScrollBar().value()
        button.setParent(self)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(6, 4, 6, 4)
        grid.setSpacing(2)
        head0 = QLabel(tr("data"))
        head0.setObjectName("SectionTitle")
        grid.addWidget(head0, 0, 0)
        for ci, (_data_id, label_text, _f) in enumerate(columns, start=1):
            head = QLabel(f"◆ {label_text}")
            head.setWordWrap(True)
            head.setObjectName("SectionTitle")
            grid.addWidget(head, 0, ci)
        for ri, key in enumerate(row_keys, start=1):
            fname = QLabel(display.get(key, key))
            fname.setObjectName("SectionTitle")
            if key == "temperature":
                header = QHBoxLayout()
                header.setSpacing(3)
                header.addWidget(fname)
                button.setText(("·", ">", "<")[mode])
                header.addWidget(button)
                grid.addLayout(header, ri, 0)
                grid.setAlignment(header, Qt.AlignmentFlag.AlignLeft)
                button.show()
            else:
                grid.addWidget(fname, ri, 0)
            for ci, (_di, _lb, fields) in enumerate(columns, start=1):
                val_lb = QLabel(fields.get(key, "—"))
                val_lb.setWordWrap(True)
                val_lb.setObjectName("MutedText")
                grid.addWidget(val_lb, ri, ci)
        grid.setRowStretch(len(row_keys) + 1, 1)
        self.notes_scroll.setWidget(container)
        # Limit the viewport to two thirds of the previous full set of rows.
        margins = grid.contentsMargins()
        full_height = (len(DATA_FIELDS) + 1) * head0.sizeHint().height()
        full_height += len(DATA_FIELDS) * grid.verticalSpacing()
        full_height += margins.top() + margins.bottom() + 2 * self.notes_scroll.frameWidth()
        self.notes_scroll.setMaximumHeight(
            min(self.notes_scroll.sizeHint().height(), round(full_height * 2 / 3))
        )
        self.notes_scroll.verticalScrollBar().setValue(scroll_position)
        if restore_focus and "temperature" in present:
            button.setFocus()

    def _refresh(self) -> None:
        manager = self._manager
        exp_id, group_id = self._exp_id, self._group_id
        project = manager.project if manager is not None else None
        exp = project.experiment(exp_id) if project is not None else None
        group = manager.group(exp_id, group_id) if exp is not None else None
        if group is None:
            self.context_changed.emit(tr("Group {p0}(does not exist)", p0=group_id))
            self.notes_scroll.hide()
            self.run_ref_button.setEnabled(False)
            self.run_optimize_button.setEnabled(False)
            return
        member_ids = set(group.data_ids or [])
        members = [d for d in exp.data if not d.trashed and d.id in member_ids]
        context = tr(
            "experiment: {p0} · Group: {p1}",
            p0=exp.title or exp_id,
            p1=group.title or f"Group {group_id}",
        )
        count = tr("Group members: {p0}", p0=len(members))
        self.context_changed.emit(f"{context}  ·  {count}")
        by_id = {data.id: data for data in members}
        self._refresh_notes([by_id[key] for key in group.data_ids if key in by_id])
        self.run_optimize_button.setEnabled(bool(members))
        from core.project.grouping import data_ndim
        ndim = data_ndim(manager, exp_id, members[0].id) if members else 2
        text = (tr("Parallel optimisation of 2D data") if ndim == 2
                else tr("Sequential optimisation"))
        self.optimisation_box.setTitle(text)
        self.run_optimize_button.setText(text)
        self.opt_stop_combo.model().item(2).setEnabled(ndim != 1)
        self.stop_combo.model().item(2).setEnabled(ndim != 1)
        if ndim == 1:
            for combo in (self.opt_stop_combo, self.stop_combo):
                if combo.currentIndex() == 2:
                    combo.setCurrentIndex(1)
        self._refresh_reference_combo(exp, members)
        self._refresh_reference_enabled()

    def _refresh_reference_combo(self, exp, members) -> None:
        """Reference data drop-down: spectrum data generated in the experiment (including group
        members)."""
        token = (id(exp), self._group_id,
                 tuple((d.id, d.title, d.trashed, d.spectrum_path, d.fid_path) for d in exp.data),
                 tuple(d.id for d in members), len(self._manager.project.workflow_runs))
        if token == getattr(self, "_reference_token", None):
            self.run_ref_button.setEnabled(bool(self.reference_combo.currentData()))
            return
        self._reference_token = token
        previous = self.reference_combo.currentData()
        self.reference_combo.clear()
        candidates = []
        from core.project import ProjectError
        from workflow.reference_scripts import candidate_signature
        try:
            signatures = {candidate_signature(self._manager, self._exp_id, d.id) for d in members}
        except (OSError, ValueError, RuntimeError, ProjectError):
            signatures = set()
        for data in exp.data:
            if data.trashed or not data.spectrum_path:
                continue
            try:
                signature = candidate_signature(self._manager, self._exp_id, data.id)
                if signatures and signatures != {signature}:
                    continue
            except (OSError, ValueError, RuntimeError, ProjectError):
                continue
            label = data.title or f"Data {data.id}"
            candidates.append((data.id, f"{label} ({data.id})"))
        if not candidates:
            self.run_ref_button.setEnabled(False)
            self.reference_combo.addItem(tr("(No spectrum data has been generated)"))
            return
        for data_id, label in candidates:
            self.reference_combo.addItem(label, data_id)
        self.run_ref_button.setEnabled(True)
        index = self.reference_combo.findData(previous)
        if index >= 0:
            self.reference_combo.setCurrentIndex(index)

    def _stop_steps(self) -> list[str]:
        """BATCH_STEPS prefix subset (starting from fid) corresponding to the cutoff step."""
        value = STOP_STEP_OPTIONS[self.stop_combo.currentIndex()][0]
        order = ("fid", "spectrum", "peaks")
        return list(order[: order.index(value) + 1])

    def _refresh_reference_enabled(self, *args):
        ready = bool(self.reference_combo.currentData()) and self.run_ref_button.isEnabled()
        spectrum = self.stop_combo.currentIndex() > 0
        self.reference_range_button.setEnabled(ready and spectrum)
        self.reference_phase_button.setEnabled(ready and spectrum)

    def _edit_reference_options(self, kind):
        from core.project.grouping import active_members
        from gui.reference_phase_dialog import ReferenceOptionsDialog
        from workflow.reference_scripts import reference_defaults
        ref = self.reference_combo.currentData()
        if not ref:
            return
        key = (self._exp_id, self._group_id, ref)
        rows = [(d.id, d.title or d.id) for d in active_members(
            self._manager, self._exp_id, self._group_id)]
        try:
            defaults = reference_defaults(self._manager, self._exp_id, ref)
            dialog = ReferenceOptionsDialog(self, rows, defaults,
                self.reference_data_options.get(key, {}), kind)
            if dialog.exec():
                self.reference_data_options[key] = dialog.values()
        except Exception as exc:
            self.log_message.emit(str(exc))

    def _on_run_reference(self) -> None:
        ref_id = str(self.reference_combo.currentData() or "")
        if not ref_id:
            self.log_message.emit(tr("Please select reference data first"))
            return
        steps = self._stop_steps()
        self.run_group_batch_requested.emit(
            self._exp_id,
            self._group_id,
            steps,
            ref_id,
            {
                "_data_options": self.reference_data_options.get(
                    (self._exp_id, self._group_id, ref_id), {}
                )
            },
        )

    def _opt_steps(self) -> list[str]:
        """The cut-off steps of the optimisation mode (prefixed by fid) are followed in turn."""
        value = STOP_STEP_OPTIONS[self.opt_stop_combo.currentIndex()][0]
        order = ("fid", "spectrum", "peaks")
        return list(order[: order.index(value) + 1])

    def _on_opt_stop_changed(self) -> None:
        """Show and hide direct dimension by cutoff step scope/Peak threshold setting."""
        steps = self._opt_steps()
        self.ext_group.setVisible("spectrum" in steps)
        self.thresh_group.setVisible("peaks" in steps)

    def _collect_params(self) -> dict:
        """Collects the currently visible settings into the processing parameter."""
        params: dict = {}
        steps = self._opt_steps()
        if "spectrum" in steps and self.ext_enable.isChecked():
            lo = self.ext_lo_edit.text().strip()
            hi = self.ext_hi_edit.text().strip()
            if lo:
                params["ext_lo"] = lo
            if hi:
                params["ext_hi"] = hi
        if "peaks" in steps and self.thresh_edit.text().strip():
            params["sigma_multiplier"] = self.thresh_edit.text().strip()
        return params

    def _on_run_optimize(self) -> None:
        steps = self._opt_steps()
        self.run_group_batch_requested.emit(
            self._exp_id,
            self._group_id,
            steps,
            "",
            self._collect_params(),
        )

    @property
    def current_group_id(self) -> str:
        """Current data group id (empty string if not selected)."""
        return str(self._group_id or "")

    def refresh(self) -> None:
        """Refresh the group page (exposed package: _refresh, for center_panel call)."""
        self._refresh()

    def set_progress(self, text: str) -> None:
        """Batch progress prompt (main thread update)."""
        self.progress_label.setText(text)
        self.progress_label.setVisible(bool(text))
