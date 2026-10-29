"""The Qt-bound half of the shared UI support: palette, stylesheet, icon, combo width.

The Qt-free halves live next door: :mod:`ui_support.colors` (semantic colours) and
:mod:`ui_support.assets` (icon and image locations). Both are re-exported below, so a caller can
keep importing everything from one module if it prefers.

Qt names come from :mod:`qtcompat`, never from a binding directly - that is what makes the same
source run on PyQt6 and on PySide6.

Called at startup by the main window (``gui/main_window.py``) and by the standalone viewer
(``viewer/app.py``): the dark theme is applied to the ``QApplication`` and the window/taskbar icon
is set from ``ui_support.assets.app_icon_path()``.
"""

from __future__ import annotations

from qtcompat.QtGui import QColor, QIcon, QPalette
from qtcompat.QtWidgets import (
    QApplication,
    QComboBox,
    QProxyStyle,
    QStyle,
    QStyleOptionComboBox,
)

from ui_support.assets import app_icon_path, theme_images_dir
from ui_support.colors import (
    PANEL_BACKGROUND,
    PANEL_BORDER,
    STATUS_COLORS,
    SURFACE_ALT,
    TEXT_MUTED,
    TEXT_ON_LIGHT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WINDOW_BACKGROUND,
)

__all__ = [
    "PANEL_BACKGROUND",
    "PANEL_BORDER",
    "STATUS_COLORS",
    "SURFACE_ALT",
    "TEXT_MUTED",
    "TEXT_ON_LIGHT",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "WINDOW_BACKGROUND",
    "app_icon",
    "app_icon_path",
    "apply_dark_theme",
    "fit_combo_width",
    "theme_images_dir",
]

def fit_combo_width(combo: QComboBox, extra: int = 18) -> None:
    """Set the minimum width of the drop-down box according to "the longest item text + drop-down
    arrow + margin" to avoid ellipses. user 2026-09-11: "The content of the drop-down box with
    optimised degree and sorting has many ellipses" -- The sizeHint of QComboBox under the
    system/QSS style does not include arrows and padding, and only 2~3 px margin is left in the
    text area (measured "Net True Peak Priority" 60 px Text / 62 px text area), if there is a
    slight difference in font rendering, it will be truncated by Qt ellipses. Just set the
    minimum width (the fluid layout will not be pushed back), and synchronize the minimum width
    of the pop-up list to avoid the list items being truncated."""
    metrics = combo.fontMetrics()
    text_width = 0
    for index in range(combo.count()):
        text_width = max(
            text_width, metrics.horizontalAdvance(combo.itemText(index))
        )
    arrow = 20
    try:
        option = QStyleOptionComboBox()
        option.initFrom(combo)
        arrow = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            combo,
        ).width()
    except Exception:
        pass
    width = text_width + arrow + max(0, int(extra))
    if width > combo.minimumWidth():
        combo.setMinimumWidth(width)
    view = combo.view()
    if view is not None and width > view.minimumWidth():
        view.setMinimumWidth(width)

def app_icon() -> QIcon | None:
    """Application icon (window and taskbar), or None when the asset is missing.

    The path logic lives in :func:`ui_support.assets.app_icon_path` so that it can be tested without
    a Qt binding.
    """
    path = app_icon_path()
    return QIcon(str(path)) if path is not None else None


class _FastTooltipStyle(QProxyStyle):
    """29ed: shorten tooltip delay so button hover hints appear quickly."""

    def styleHint(
        self,
        hint,
        option=None,
        widget=None,
        returnData=None,
    ):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 120
        if hint == QStyle.StyleHint.SH_ToolTip_FallAsleepDelay:
            return 120
        return super().styleHint(hint, option, widget, returnData)


def apply_dark_theme(app: QApplication) -> None:
    """Force the dark theme and pick up the system language (see ui_support/i18n.py)."""
    from ui_support.i18n_qt import install_qt_language

    install_qt_language()
    app.setStyle("Fusion")
    app.setStyle(_FastTooltipStyle(app.style()))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8e8e8"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#252526"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2d2d30"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8e8e8"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3c3c3c"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8e8e8"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d2d30"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8e8e8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0e639c"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9e9e9e"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#4fc1ff"))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor("#6e6e6e"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#6e6e6e"),
    )
    app.setPalette(palette)
    _arrow_qss = ""
    _assets = theme_images_dir()
    if _assets is not None:
        _up = (_assets / "spin_up.png").as_posix()
        _down = (_assets / "spin_down.png").as_posix()
        _arrow_qss = (
            f'QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{'
            f' image: url("{_up}"); width: 12px; height: 12px; }}\n'
            f'QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{'
            f' image: url("{_down}"); width: 12px; height: 12px; }}\n'
        )
    app.setStyleSheet(
        # i18n: keep - CSS comments are not interface messages.
        """
        QToolTip { color: #e8e8e8; background-color: #2d2d30;
                   border: 1px solid #3c3c3c; }
        QMenuBar { background-color: #1e1e1e; color: #e8e8e8; padding: 2px; }
        QMenuBar::item { padding: 4px 8px; border-radius: 4px; }
        QMenuBar::item:selected { background-color: #293746; }
        QMenu { background-color: #252526; color: #e8e8e8;
                border: 1px solid #3c3c3c; }
        QMenu::item { padding: 6px 22px 6px 12px; }
        QMenu::item:selected { background-color: #244663; }
        QMenu::separator { height: 1px; background: #39424e; margin: 5px 8px; }
        QStatusBar { background-color: #1e1e1e; color: #e8e8e8; }
        QTreeView, QListView, QTableView, QTableWidget, QTreeWidget {
            background-color: #252526; color: #e8e8e8;
            alternate-background-color: #232326; }
        QHeaderView::section { background-color: #2d2d30; color: #e8e8e8;
                               border: none;
                               border-bottom: 1px solid #3c3c3c;
                               padding: 4px 6px; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit,
        QTextEdit, QDateEdit, QTimeEdit {
            background-color: #1e1e1e; color: #e8e8e8;
            border: 1px solid #3c3c3c; border-radius: 4px; }
        /* Dark spinbox buttons keep their white arrows visible. */
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            background-color: #3c3c3c; border: none; width: 16px; }
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: #4a4a4a; }
        QPushButton { background-color: #2b313a; color: #e8e8e8;
                      border: 1px solid #424b58; padding: 5px 10px;
                      border-radius: 4px; }
        QPushButton:hover { background-color: #354150; border-color: #5a718b; }
        QPushButton:disabled { color: #6e6e6e; }
        QPushButton#PrimaryAction { background-color: #12669e; border: 1px solid #3286be;
                                   color: white; font-weight: bold; padding: 6px 12px; }
        QPushButton#PrimaryAction:hover { background-color: #197bb7; }
        QPushButton#PrimaryAction:pressed { background-color: #094771; }
        QPushButton#PrimaryAction:disabled { background-color: #303840; color: #909090;
                                           border-color: #555555; }
        QTabWidget::pane { border: 1px solid #3c3c3c; }
        QTabBar::tab { background-color: #252526; color: #e8e8e8;
                       padding: 4px 8px; }
        QTabBar::tab:selected { background-color: #0e639c; }
        QSplitter::handle { background-color: #3a3d42; }
        QSplitter::handle:horizontal { width: 6px; }
        QSplitter::handle:vertical { height: 6px; }
        QSplitter::handle:hover { background-color: #0e639c; }
        QSplitter::handle:pressed { background-color: #1177bb; }
        QScrollBar { background-color: #252526; }
        QScrollBar::handle { background-color: #3c3c3c; }
        QLabel { color: #e8e8e8; }
        /* Leave room above custom group borders for the title. */
        QGroupBox { border: 1px solid #3c3c3c; margin-top: 1.4em;
                    border-radius: 5px; padding-top: 5px;
                    color: #e8e8e8; }
        QGroupBox::title { subcontrol-origin: margin;
                           subcontrol-position: top left;
                           left: 8px; padding: 0 4px;
                           color: #4fc1ff; }
        QProgressBar { background-color: #252526; border: 1px solid #3c3c3c;
                       color: #e8e8e8; }
        QProgressBar::chunk { background-color: #0e639c; }
        QCheckBox, QRadioButton { color: #e8e8e8; }
        QListWidget { background-color: #252526; color: #e8e8e8; }
        QStackedWidget { background-color: #1e1e1e; }
        /* Section cards and headings. */
        QWidget#PanelCard { background-color: #202124;
                            border: 1px solid #33363b;
                            border-radius: 6px; }
        QLabel#PanelTitle { font-weight: bold;
                            color: #e8e8e8; }
        QLabel#PanelSubtitle { color: #b0b0b0; }
        /* Step rows: bottom separators and hover highlighting. */
        QWidget#StepRow { border-bottom: 1px solid #2d2d30; }
        QWidget#StepRow:hover { background-color: #26282b; }
        /* Consistent selection and hover states. */
        QTreeView::item:selected, QListView::item:selected,
        QTableView::item:selected, QTableWidget::item:selected {
            background-color: #0e639c; color: #ffffff; }
        QTreeView::item:hover, QListView::item:hover,
        QTableView::item:hover, QTableWidget::item:hover {
            background-color: #2a2d2e; }
        /* Input focus. */
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {
            border: 1px solid #0e639c; }
        /* Button states. */
        QPushButton:pressed { background-color: #2f2f2f; }
        QPushButton:checked { background-color: #0e639c;
                              border-color: #1177bb; }
        /* Slim rounded scrollbars. */
        QScrollBar:vertical { background: transparent; width: 10px;
                              margin: 2px 0 2px 0; }
        QScrollBar:horizontal { background: transparent; height: 10px;
                                margin: 0 2px 0 2px; }
        QScrollBar::handle { background-color: #3c3c3c;
                             border-radius: 4px;
                             min-height: 28px; min-width: 28px; }
        QScrollBar::handle:hover { background-color: #4d4d4d; }
        QScrollBar::add-line, QScrollBar::sub-line {
            width: 0; height: 0; background: transparent; }
        QScrollBar::add-page, QScrollBar::sub-page {
            background: transparent; }
        QToolTip { padding: 4px 6px; border-radius: 4px; }
        QPushButton#SubtleAction, QToolButton {
            background: transparent; border: 1px solid transparent;
            color: #b7c5d6; padding: 3px 7px; border-radius: 4px; }
        QPushButton#SubtleAction:hover, QToolButton:hover {
            color: #e8f1ff; background: #2c3744; border-color: #40566b; }
        QPushButton#SubtleAction:checked, QPushButton#PrimaryAction:checked {
            background: #224d6a; color: #e3f2ff; border-color: #7abbe3; }
        QToolButton#ReportToggle { color: #80b7df; padding: 2px 5px; }
        QToolButton#ReportToggle:checked { background: #233c50; color: #b5dbf6; }
        QPushButton:focus, QToolButton:focus { border-color: #4a9fd5; }
        QLabel#SectionTitle { color: #d4dce7; font-weight: bold; padding: 5px 0 2px; }
        QLabel#MutedText, QLabel#TreeSelectionHint { color: #9faab8; }
        QLabel#SelectionGuide { color: #c6d9ea; background: #252e39;
            border: none; border-left: 3px solid #447fa9; padding: 6px 10px; }
        QPushButton#ViewerSectionHeader {
            background: #35332b; border: none; border-left: 3px solid #cfab68;
            border-radius: 4px; padding: 0; }
        QPushButton#ViewerSectionHeader:checked {
            background: #283746; border-left-color: #4a9fd5; }
        QPushButton#ViewerSectionHeader:hover { background: #364452; }
        QLabel#ViewerSectionArrow, QLabel#ViewerSectionTitle, QLabel#ViewerSectionState {
            background: transparent; border: none; color: #dbe6f2; font-weight: bold; }
        QLabel#ViewerSectionState { color: #c1cfde; }
        QLabel#ViewerPlotHeader {
            color: #dbe6f2; background: #283746; border-left: 3px solid #4a9fd5;
            padding: 4px 8px; font-weight: bold; }
        QTabBar::tab { border-bottom: 2px solid transparent; padding: 6px 12px; }
        QTabBar::tab:selected { background: #283746; border-bottom-color: #4a9fd5; }
        QSlider::groove:horizontal { height: 3px; background: #3b444e; }
        QSlider::sub-page:horizontal { background: #337eb1; }
        QSlider::handle:horizontal { background: #8fbfdf; border: 1px solid #477fa6;
            width: 12px; margin: -5px 0; border-radius: 6px; }
        /* Use the card background throughout each section so content widgets do not fragment it. */
        QWidget#PanelCard QTreeWidget, QWidget#PanelCard QTableWidget,
        QWidget#PanelCard QListWidget, QWidget#PanelCard QPlainTextEdit,
        QWidget#PanelCard QTextEdit, QWidget#PanelCard QStackedWidget,
        QWidget#PanelCard QScrollArea, QWidget#PanelCard QScrollArea > QWidget,
        QWidget#PanelCard QScrollArea > QWidget > QWidget {
            background-color: #202124; border: none; }
        """
        + _arrow_qss
    )
