"""Selection and background-result state for the raw NUS export dialog."""

from qtcompat.QtCore import Qt
from qtcompat.QtWidgets import QApplication

from gui.uniform_nus_dialog import UniformNusDialog


def test_auto_and_manual_selection_keep_grid_coordinates(qapp):
    dialog = UniformNusDialog()
    points = [
        dict(
            coordinate=[i, 2],
            raw_rows=[i * 4 + j for j in range(4)],
            reasons=["isolated_spike"] if i == 1 else [],
            advisory=[],
            auto_remove=i == 1,
        )
        for i in range(4)
    ]
    dialog._finished(dict(points=points, source={}), None, "scan")
    assert dialog.selected_coordinates() == [(1, 2)]
    assert dialog.export_button.isEnabled()
    dialog.manual.setChecked(True)
    dialog.tree.topLevelItem(1).setCheckState(0, Qt.CheckState.Unchecked)
    dialog.tree.topLevelItem(3).setCheckState(0, Qt.CheckState.Checked)
    assert dialog.selected_coordinates() == [(3, 2)]
    dialog.automatic.setChecked(True)
    assert dialog.selected_coordinates() == [(1, 2)]
    dialog.show()
    qapp.processEvents()
    dialog._busy = True
    dialog.reject()
    assert dialog.isVisible()
    dialog._busy = False
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()
