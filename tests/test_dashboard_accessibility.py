"""Accessible dashboard actions and compact large-font layouts."""

from __future__ import annotations

import pytest
from qtcompat.QtCore import Qt
from qtcompat.QtGui import QFont
from qtcompat.QtWidgets import QApplication, QLabel, QPushButton

from core.workspace import WorkspaceManager
from gui.center_panel import CenterPanel
from gui.dashboards import ExperimentDashboard, ProjectDashboard
from gui.group_panel import GroupBatchPanel
from gui.project_tree import ProjectTreePanel
from gui.welcome_page import WelcomePage


@pytest.mark.parametrize('language', ['en', 'zh'])
@pytest.mark.parametrize('size', [8, 18])
def test_tree_level_names_use_language_and_current_font(qapp, tmp_path, language, size):
    from qtcompat.QtWidgets import QStyleOptionViewItem

    from ui_support import i18n

    previous = i18n._language
    try:
        i18n.set_language(language)
        workspace = WorkspaceManager(tmp_path / 'workspace')
        manager = workspace.create_project('demo')
        experiment = manager.create_experiment('HSQC')
        manager.import_data(experiment.id, tmp_path / 'sample')
        panel = ProjectTreePanel(manager, workspace=workspace)
        font = QFont(qapp.font())
        font.setPointSize(size)
        panel.setFont(font)
        panel.resize(600, 500)
        panel.show()
        qapp.processEvents()
        delegate = panel.tree.itemDelegateForColumn(0)
        expected = (['Workspace', 'Project', 'Experiment', 'Data'] if language == 'en'
                    else ['工作区', '项目', '实验', '样品数据'])
        for kind, label in zip(('workspace', 'project', 'experiment', 'data'), expected):
            text, color = delegate.level(kind)
            assert text == label
            assert color.startswith('#')
            assert panel._icon(kind).isNull()
        item = panel.tree.topLevelItem(0)
        index = panel.tree.indexFromItem(item)
        opt = QStyleOptionViewItem()
        opt.initFrom(panel.tree)
        opt.font = panel.tree.font()
        opt.fontMetrics = panel.tree.fontMetrics()
        hint = delegate.sizeHint(opt, index)
        assert hint.height() >= panel.fontMetrics().height()
        # Exercise actual painting with the themed/current font, including selection.
        panel.tree.setCurrentItem(item)
        assert not panel.grab().isNull()
        panel.close()
    finally:
        i18n.set_language(previous)


def test_welcome_primary_action_and_inline_name_feedback(
    qapp: QApplication, tmp_path
) -> None:
    page = WelcomePage(workspace=WorkspaceManager(tmp_path / "workspace"))
    page.resize(420, 500)
    page.show()
    qapp.processEvents()

    assert page.new_button.objectName() == "PrimaryAction"
    assert page.new_button.y() < page.recent_list.y()
    page.begin_inline_name()
    assert page._name_edit.isVisible()
    assert page._name_prompt.isVisible()
    qapp.processEvents()
    assert page._name_edit.y() < page.recent_list.y()
    page._name_edit.setText("   ")
    page._commit_name()
    assert page._name_edit.isVisible()
    assert page._name_prompt.isVisible()
    assert page._name_prompt.text()

    created: list[str] = []
    page.new_project_requested.connect(created.append)
    page._name_edit.setText("My project")
    page._commit_name()
    assert created == ["My project"]
    assert not page._name_edit.isVisible()
    page.close()


def test_new_experiment_is_above_history_and_accepts_enter(qapp: QApplication) -> None:
    page = ProjectDashboard()
    page.resize(650, 800)
    page.show()
    qapp.processEvents()
    assert page.create_button.mapTo(page.page_content, page.create_button.rect().topLeft()).y() < (
        page.runs_table.y()
    )
    created = []
    page.create_experiment_requested.connect(created.append)
    page.title_edit.setText('HSQC')
    page.title_edit.returnPressed.emit()
    assert created == ['HSQC']
    page.close()


def test_dashboards_scroll_with_large_font_and_narrow_width(qapp: QApplication) -> None:
    font = QFont()
    font.setPointSize(18)
    for page in (ProjectDashboard(), ExperimentDashboard(), GroupBatchPanel()):
        page.setFont(font)
        page.resize(360, 300)
        page.show()
        qapp.processEvents()

        primary_actions = page.findChildren(QPushButton)
        assert any(button.objectName() == "PrimaryAction" for button in primary_actions)
        scroll = getattr(page, "scroll_area", None) or getattr(page, "_scroll", None)
        assert scroll is not None
        assert scroll.verticalScrollBar().maximum() > 0
        page.close()


def test_tree_level_selection_explains_the_center_panel_tools(
    qapp: QApplication, tmp_path
) -> None:
    from ui_support.i18n import tr

    workspace = WorkspaceManager(tmp_path / "workspace")
    manager = workspace.create_project("demo")
    experiment = manager.create_experiment("HSQC")
    manager.import_data(experiment.id, tmp_path / "sample")
    manager.create_data_group(experiment.id, title="Batch")
    tree = ProjectTreePanel(manager, workspace=workspace)
    center = CenterPanel(manager)
    assert center.selection_guide_label.text()
    assert center.edit_notes_button.isHidden()
    tree.selection_changed.connect(center.set_selection)

    def find_kind(item, kind):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, dict) and data.get("kind") == kind:
            return item
        for index in range(item.childCount()):
            found = find_kind(item.child(index), kind)
            if found is not None:
                return found
        return None

    root = tree.tree.topLevelItem(0)
    project_item = find_kind(root, "project")
    experiment_item = find_kind(root, "experiment")
    data_item = find_kind(root, "data")
    group_item = find_kind(root, "group")
    assert all(
        item is not None
        for item in (project_item, experiment_item, data_item, group_item)
    )

    expected = (
        (root, 0, "Workspace", "Create or open projects"),
        (project_item, 1, "Project", "Create experiments"),
        (experiment_item, 2, "Experiment", "Import sample data"),
        (data_item, 3, "Data", "Process sample data"),
        (group_item, 4, "Group", "Process group data in batches"),
    )
    for item, page_index, level, purpose in expected:
        tree.tree.setCurrentItem(item)
        qapp.processEvents()
        assert center.stack.currentIndex() == page_index
        assert tr(level) in center.selection_guide_label.text()
        assert tr(purpose) in center.selection_guide_label.text()

    assert tree.findChild(QLabel, "TreeSelectionHint").text()
    tree.close()
    center.close()
